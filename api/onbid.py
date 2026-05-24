"""
온비드 공매정보 API (공공데이터포털)
API 키 없을 때는 샘플 데이터로 대체 (데모용)
"""

import httpx

ONBID_BASE = "https://apis.data.go.kr/B502007/publicPropertyInfoSvc"


def fetch_property(object_no: str, api_key: str) -> dict | None:
    """온비드 물건번호로 공매 정보 조회"""
    if not api_key or api_key == "your_key_here":
        return None

    params = {
        "serviceKey": api_key,
        "pbctNo": object_no,
        "numOfRows": "1",
        "pageNo": "1",
    }
    try:
        r = httpx.get(f"{ONBID_BASE}/getPbctInfo", params=params, timeout=10)
        r.raise_for_status()
        from xml.etree import ElementTree as ET
        root = ET.fromstring(r.text)
        item = root.find(".//item")
        if item is None:
            return None
        return {
            "name": item.findtext("pbctNm", "").strip(),
            "min_bid": int(item.findtext("lwstBdPrc", "0").replace(",", "")),
            "appraisal": int(item.findtext("aprvPrc", "0").replace(",", "")),
            "area": item.findtext("pblctnStle", "").strip(),
            "status": item.findtext("pbctProgSttus", "").strip(),
        }
    except Exception:
        return None


# ── 데모용 샘플 매물 (분당풍림아이원플러스 실제 데이터 기반) ──────

SAMPLE_PROPERTIES = {
    "S-3068": {
        "name": "분당풍림아이원플러스오피스텔 S-3068",
        "region": "성남시 분당구",
        "area_m2": 35.055,
        "property_type": "업무시설",
        "sale_type": "담보신탁",
        "min_bid": 73_896_000,
        "appraisal_value": 208_800_000,
        "has_tenant": True,
        "has_tax_clause": True,
        "has_mgmt_clause": True,
        "note": "11차 공매 (2026.05.20~21) | 우선수익자: 수원화성오산축산업협동조합",
    },
    "DEMO-001": {
        "name": "수원영통오피스텔 401호 (데모)",
        "region": "수원시 영통구",
        "area_m2": 40.0,
        "property_type": "업무시설",
        "sale_type": "캠코공매",
        "min_bid": 95_000_000,
        "appraisal_value": 160_000_000,
        "has_tenant": False,
        "has_tax_clause": False,
        "has_mgmt_clause": False,
        "note": "임차인 없음, 즉시 명도 가능",
    },
    # ── 신탁 우선수익금액 미공개 사례 (정보 비대칭 경고 데모) ────────────────
    "MORAN-401": {
        "name": "이안모란센트럴파크아파트 102동 401호",
        "region": "성남시 중원구",
        "area_m2": 51.5067,
        "property_type": "주거",
        "sale_type": "담보신탁",
        "min_bid": 560_400_000,        # 6차 공매 최저입찰가 (2026.05.11 유찰)
        "appraisal_value": 850_000_000, # 1차 공매 시작가 = 감정가
        "has_tenant": False,
        "has_tax_clause": True,         # 공고 특약: 세금체납 시 등기 불가 매수자 책임
        "has_mgmt_clause": True,        # 공고 특약: 관리비 전액 매수자 부담
        "trust_unconfirmed": True,      # 우선수익금액 신탁원부에만 기재 — 미확인
        "trust_beneficiaries": "부안수협·인천수협·죽변수협·포항수협·군산시수협",
        "is_pre_sale": True,            # 미분양 신축 — 실거래가 없음
        "note": "6차 공매 2026.05.11 유찰 | KB부동산신탁 담보신탁 | 우선수익금액 미공개 → 적정가 산출 불가 사례",
    },
}


def get_sample(object_no: str) -> dict | None:
    return SAMPLE_PROPERTIES.get(object_no)


def list_samples() -> list[str]:
    return list(SAMPLE_PROPERTIES.keys())
