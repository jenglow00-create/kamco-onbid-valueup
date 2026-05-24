"""
리스크 비용 테이블 + 적정가 산출 엔진

금융 모델 관점:
  적정 입찰가 = 실거래 시세 - Σ 리스크 비용 - 안전마진
  꿀매물 지수 = (적정 입찰가 - 최저 입찰가) / 적정 입찰가
"""

from dataclasses import dataclass, field


# ── 리스크 항목 정의 ──────────────────────────────────────────

@dataclass
class RiskItem:
    name: str
    cost: int          # 원 단위 평균 비용
    applied: bool
    reason: str        # 적용 근거


RISK_TABLE = {
    # key: (name, avg_cost_won, reason)
    "eviction": (
        "명도 소송 비용",
        3_000_000,
        "임차인 잔류 시 법원 명도소송 평균 비용 (변호사비 포함)",
    ),
    "mgmt_arrears": (
        "체납 관리비 인수",
        2_000_000,
        "담보신탁 공매 특약상 매수인 인수 — 평균 6개월치",
    ),
    "tax_arrears": (
        "위탁자 조세체납 인수",
        5_000_000,
        "공고 특약 '2021년 이후 조세 미납 시 매수인 책임' — 평균 추정",
    ),
    "acquisition_tax_premium": (
        "취득세 추가 부담",
        0,          # 동적 계산
        "업무시설 4.6% vs 주거 1~3% — 차액 기준",
    ),
    "defect_discount": (
        "담보신탁 하자 할인",
        0,          # 동적 계산
        "하자담보 책임 없음 — 감정가 3% 안전 할인",
    ),
    "registration_risk": (
        "등기 불가 리스크",
        3_000_000,
        "조세체납 시 등기접수 거부 가능 — 해결 비용 평균",
    ),
}

SAFETY_MARGIN_RATE = 0.05  # 적정가의 5% 안전마진


# ── 입찰 조건 데이터 클래스 ────────────────────────────────────

@dataclass
class PropertyInput:
    name: str
    region: str
    area_m2: float
    property_type: str          # "업무시설" | "주거"
    sale_type: str              # "담보신탁" | "캠코공매" | "일반경매"
    min_bid: int                # 최저입찰가 (원)
    appraisal_value: int        # 감정가 (원)
    has_tenant: bool = True     # 임차인 존재 여부
    has_tax_clause: bool = True # 조세체납 특약 여부
    has_mgmt_clause: bool = True  # 관리비 체납 특약 여부
    # 담보신탁 추가 정보
    trust_unconfirmed: bool = False   # 우선수익금액 미확인 여부 (신탁원부 미열람)
    trust_beneficiaries: str = ""     # 우선수익자 목록
    is_pre_sale: bool = False         # 미분양 여부 (실거래가 없음)


# ── 밸류에이션 엔진 ────────────────────────────────────────────

def analyze(prop: PropertyInput, market: dict) -> dict:
    # ── 신탁 우선수익금액 미확인 → 계산 자체를 차단 ───────────────────────
    if prop.trust_unconfirmed:
        return {
            "blocked": True,
            "block_reason": "trust_unconfirmed",
            "block_detail": (
                "담보신탁 우선수익금액이 신탁원부에만 기재되어 있으며\n"
                "  공매 공고문·등기부등본 어디에도 공개되지 않습니다.\n"
                "  선순위 채무 규모를 확인하지 않으면 낙찰 후\n"
                "  실제 취득 비용을 산정할 수 없어 적정 입찰가 계산이 불가합니다."
            ),
            "trust_beneficiaries": prop.trust_beneficiaries,
            "property": prop,
            "market": market,
        }

    risks: list[RiskItem] = []
    market_price = market["avg_price"]

    # 1. 명도 소송
    if prop.has_tenant:
        k, cost, reason = "eviction", *RISK_TABLE["eviction"][1:]
        risks.append(RiskItem("명도 소송 비용", cost, True, reason))

    # 2. 체납 관리비
    if prop.has_mgmt_clause:
        _, cost, reason = RISK_TABLE["mgmt_arrears"]
        risks.append(RiskItem("체납 관리비 인수", cost, True, reason))

    # 3. 조세체납
    if prop.has_tax_clause:
        _, cost, reason = RISK_TABLE["tax_arrears"]
        risks.append(RiskItem("위탁자 조세체납 인수", cost, True, reason))
        _, reg_cost, reg_reason = RISK_TABLE["registration_risk"]
        risks.append(RiskItem("등기 불가 리스크", reg_cost, True, reg_reason))

    # 4. 취득세 추가 부담 (업무시설 4.6% vs 주거 1.1%)
    if prop.property_type == "업무시설":
        base_rate = 0.011
        actual_rate = 0.046
        tax_diff = int(prop.min_bid * (actual_rate - base_rate))
        _, _, reason = RISK_TABLE["acquisition_tax_premium"]
        risks.append(RiskItem("취득세 추가 부담", tax_diff, True, reason))

    # 5. 담보신탁 하자 할인
    if prop.sale_type == "담보신탁":
        defect_cost = int(prop.appraisal_value * 0.03)
        _, _, reason = RISK_TABLE["defect_discount"]
        risks.append(RiskItem("담보신탁 하자 할인", defect_cost, True, reason))

    total_risk_cost = sum(r.cost for r in risks)
    fair_value_before_margin = market_price - total_risk_cost
    safety_margin = int(fair_value_before_margin * SAFETY_MARGIN_RATE)
    fair_value = fair_value_before_margin - safety_margin

    upside = fair_value - prop.min_bid
    upside_rate = upside / fair_value if fair_value > 0 else 0

    # 꿀매물 지수 (★ 0~5)
    if upside_rate >= 0.40:
        stars = 5
    elif upside_rate >= 0.25:
        stars = 4
    elif upside_rate >= 0.10:
        stars = 3
    elif upside_rate >= 0.0:
        stars = 2
    elif upside_rate >= -0.10:
        stars = 1
    else:
        stars = 0

    return {
        "property": prop,
        "market": market,
        "risks": risks,
        "total_risk_cost": total_risk_cost,
        "safety_margin": safety_margin,
        "fair_value": fair_value,
        "min_bid": prop.min_bid,
        "upside": upside,
        "upside_rate": upside_rate,
        "stars": stars,
    }
