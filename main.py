"""
OnBid ValueUp — 온비드 공매 적정가 산출기
사용법:
  python main.py S-3068          # 샘플 매물 분석
  python main.py DEMO-001        # 리스크 없는 매물 비교
  python main.py --list          # 샘플 목록
"""

import os
import sys
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from api.molit import get_market_price
from api.onbid import get_sample, list_samples
from analyzer import PropertyInput, analyze

load_dotenv()
console = Console()

MOLIT_KEY = os.getenv("MOLIT_API_KEY", "")
ONBID_KEY = os.getenv("ONBID_API_KEY", "")


def fmt_won(n: int) -> str:
    if n >= 100_000_000:
        eok = n // 100_000_000
        rem = (n % 100_000_000) // 10_000
        if rem:
            return f"{eok}억 {rem:,}만원"
        return f"{eok}억원"
    return f"{n // 10_000:,}만원"


def _show_trust_warning(prop: "PropertyInput", data: dict, result: dict):
    """우선수익금액 미확인 → 계산 불가 경고 출력"""
    console.print()
    console.print(Panel(
        f"[bold]{prop.name}[/bold]\n"
        f"[dim]{prop.region} | {prop.area_m2}㎡ ({prop.area_m2 / 3.305:.1f}평) | "
        f"{prop.property_type} | {prop.sale_type}[/dim]\n"
        f"[dim]{data.get('note', '')}[/dim]",
        title="📍 OnBid ValueUp — 신탁 매물 경고",
        border_style="red",
    ))

    console.print(Panel(
        f"[bold red]⚠  적정 입찰가 산출 불가 (BLOCKED)[/bold red]\n\n"
        f"  {result['block_detail']}\n\n"
        f"[bold]  우선수익자[/bold]  {result['trust_beneficiaries']}\n\n"
        f"[yellow]  ▶ 신탁원부(영구보존문서)를 별도 열람하여\n"
        f"    우선수익금액 확인 후 입찰 여부를 판단하십시오.\n"
        f"    (온비드 공고 내 '신탁원부 열람 안내' 또는 관할 등기소 방문)[/yellow]",
        title="🔒 신탁 우선수익금액 미공개",
        border_style="red",
    ))

    console.print(f"\n[bold]■ 참고 정보[/bold]")
    console.print(f"  감정가              {fmt_won(prop.appraisal_value)}")
    console.print(f"  현재 최저입찰가     [cyan]{fmt_won(prop.min_bid)}[/cyan]")
    console.print(f"  최저입찰가 / 감정가  {prop.min_bid / prop.appraisal_value * 100:.1f}%")
    if prop.is_pre_sale:
        console.print(f"  [dim]실거래가: 미분양 신축 — 등록된 실거래 데이터 없음[/dim]")

    console.print()
    console.print("[dim]  ※ 담보신탁 을구가 비어 있더라도 신탁원부에 선순위 채무가 존재할 수 있습니다.[/dim]")
    console.print("[dim]  ※ 우선수익금액 > 낙찰가인 경우 매수자에게 실익이 없거나 손실이 발생할 수 있습니다.[/dim]")
    console.print()


def run(object_no: str):
    data = get_sample(object_no)
    if not data:
        console.print(f"[red]매물 '{object_no}'을 찾을 수 없습니다.[/red]")
        console.print(f"사용 가능한 샘플: {', '.join(list_samples())}")
        return

    prop = PropertyInput(
        name=data["name"],
        region=data["region"],
        area_m2=data["area_m2"],
        property_type=data["property_type"],
        sale_type=data["sale_type"],
        min_bid=data["min_bid"],
        appraisal_value=data["appraisal_value"],
        has_tenant=data["has_tenant"],
        has_tax_clause=data["has_tax_clause"],
        has_mgmt_clause=data["has_mgmt_clause"],
        trust_unconfirmed=data.get("trust_unconfirmed", False),
        trust_beneficiaries=data.get("trust_beneficiaries", ""),
        is_pre_sale=data.get("is_pre_sale", False),
    )

    market = get_market_price(prop.region, prop.area_m2, MOLIT_KEY)
    result = analyze(prop, market)

    # 신탁 우선수익금액 미확인 → 경고 출력 후 종료
    if result.get("blocked"):
        _show_trust_warning(prop, data, result)
        return

    # ── 헤더 ──────────────────────────────────────────────────
    console.print()
    console.print(Panel(
        f"[bold cyan]{prop.name}[/bold cyan]\n"
        f"[dim]{prop.region} | {prop.area_m2}㎡ ({prop.area_m2 / 3.305:.1f}평) | "
        f"{prop.property_type} | {prop.sale_type}[/dim]\n"
        f"[dim]{data.get('note', '')}[/dim]",
        title="📍 OnBid ValueUp 분석 리포트",
        border_style="cyan",
    ))

    # ── 시세 정보 ──────────────────────────────────────────────
    m = result["market"]
    console.print(f"\n[bold]■ 시세 분석[/bold]  [dim]({m['source']})[/dim]")
    console.print(f"  최근 실거래가 평균   {fmt_won(m['avg_price'])}")
    console.print(f"  실거래가 범위        {fmt_won(m['min_price'])} ~ {fmt_won(m['max_price'])}")
    console.print(f"  감정가              {fmt_won(prop.appraisal_value)}")

    # ── 리스크 차감 테이블 ─────────────────────────────────────
    console.print(f"\n[bold]■ 리스크 비용 차감[/bold]")
    rtable = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    rtable.add_column("항목", style="yellow")
    rtable.add_column("비용", justify="right")
    rtable.add_column("근거", style="dim")

    for r in result["risks"]:
        rtable.add_row(r.name, f"- {fmt_won(r.cost)}", r.reason)

    rtable.add_row(
        "[bold]안전마진 (5%)[/bold]",
        f"- {fmt_won(result['safety_margin'])}",
        "불확실성 버퍼",
    )
    console.print(rtable)

    # ── 결론 패널 ─────────────────────────────────────────────
    stars = "★" * result["stars"] + "☆" * (5 - result["stars"])
    upside = result["upside"]
    upside_str = fmt_won(abs(upside))
    color = "green" if upside > 0 else "red"
    direction = "여유" if upside > 0 else "초과"

    console.print(Panel(
        f"  실거래 시세          [white]{fmt_won(m['avg_price'])}[/white]\n"
        f"  리스크 비용 합산   [red]- {fmt_won(result['total_risk_cost'])}[/red]\n"
        f"  안전마진           [red]- {fmt_won(result['safety_margin'])}[/red]\n"
        f"  ─────────────────────────────────\n"
        f"  적정 입찰가    [bold white]{fmt_won(result['fair_value'])}[/bold white]\n"
        f"  현재 최저입찰가    [cyan]{fmt_won(prop.min_bid)}[/cyan]\n\n"
        f"  차이   [{color}]{'+' if upside > 0 else '-'}{upside_str} ({result['upside_rate']*100:.1f}%)[/{color}]\n"
        f"  꿀매물 지수   [yellow]{stars}[/yellow]  ({result['stars']}/5)",
        title="💰 밸류에이션 결과",
        border_style="green" if upside > 0 else "red",
    ))

    if result["stars"] >= 4:
        console.print("[bold green]  → 적정가 대비 낙찰가 여유 충분. 입찰 검토 가능.[/bold green]\n")
    elif result["stars"] >= 2:
        console.print("[yellow]  → 리스크 해소 확인 후 입찰 고려.[/yellow]\n")
    else:
        console.print("[red]  → 현재 입찰가로는 적정가 대비 메리트 부족.[/red]\n")


def main():
    if len(sys.argv) < 2 or sys.argv[1] == "--list":
        console.print("\n[bold]사용법:[/bold]  python main.py <물건번호>")
        console.print("[bold]샘플 목록:[/bold]")
        for s in list_samples():
            d = get_sample(s)
            console.print(f"  [cyan]{s}[/cyan]  {d['name']}")
        console.print()
        return

    run(sys.argv[1])


if __name__ == "__main__":
    main()
