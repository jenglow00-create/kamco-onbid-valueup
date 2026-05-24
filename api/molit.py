"""
국토교통부 오피스텔 실거래가 API
data.go.kr → 국토교통부_오피스텔매매 실거래자료
"""

import httpx
import os
from datetime import datetime, timedelta


MOLIT_BASE = "http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcOffiTrade"

# 법정동 코드 주요 지역 (앞 5자리: 시군구)
LAWD_CD = {
    "성남시 분당구": "41135",
    "성남시 중원구": "41113",
    "수원시 영통구": "41117",
    "수원시 팔달구": "41115",
    "용인시 수지구": "41465",
    "안양시 동안구": "41173",
    "고양시 일산동구": "41285",
    "부천시": "41190",
    "서울 강남구": "11680",
    "서울 마포구": "11440",
}


def get_recent_months(n: int = 6) -> list[str]:
    months = []
    now = datetime.now()
    for i in range(n):
        d = now - timedelta(days=30 * i)
        months.append(d.strftime("%Y%m"))
    return months


def fetch_trade_data(lawd_cd: str, deal_ymd: str, api_key: str) -> list[dict]:
    params = {
        "serviceKey": api_key,
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": deal_ymd,
        "numOfRows": "100",
        "pageNo": "1",
    }
    try:
        r = httpx.get(MOLIT_BASE, params=params, timeout=10)
        r.raise_for_status()
        from xml.etree import ElementTree as ET
        root = ET.fromstring(r.text)
        items = root.findall(".//item")
        return [
            {
                "area": float(item.findtext("excluUseAr", "0").strip()),
                "price": int(item.findtext("dealAmount", "0").replace(",", "").strip()),
                "floor": item.findtext("floor", "").strip(),
                "year": item.findtext("dealYear", "").strip(),
                "month": item.findtext("dealMonth", "").strip(),
                "name": item.findtext("aptNm", "").strip(),
            }
            for item in items
            if item.findtext("excluUseAr")
        ]
    except Exception:
        return []


def get_market_price(region: str, area_m2: float, api_key: str) -> dict:
    """
    지역+면적으로 최근 6개월 실거래가 평균 산출.
    API 키 없거나 실패 시 샘플 데이터 반환 (데모용).
    """
    lawd_cd = LAWD_CD.get(region)

    if not api_key or api_key == "your_key_here" or not lawd_cd:
        return _sample_price(region, area_m2)

    trades = []
    for ym in get_recent_months(6):
        trades.extend(fetch_trade_data(lawd_cd, ym, api_key))

    # 면적 ±5㎡ 필터
    matched = [t for t in trades if abs(t["area"] - area_m2) <= 5]

    if not matched:
        return _sample_price(region, area_m2)

    prices = [t["price"] * 10000 for t in matched]  # 만원 → 원
    return {
        "source": "국토부 실거래가 API",
        "count": len(prices),
        "avg_price": int(sum(prices) / len(prices)),
        "min_price": min(prices),
        "max_price": max(prices),
        "region": region,
        "area_m2": area_m2,
    }


def _sample_price(region: str, area_m2: float) -> dict:
    """API 키 없을 때 사용하는 데모 시세 (단위: 원)"""
    # 지역별 오피스텔 평당 시세 (만원/㎡, 2025년 기준 추정치)
    price_per_m2 = {
        "성남시 분당구": 4_200_000,
        "성남시 중원구": 9_500_000,  # 신축 아파트 추정 (미분양, 실거래가 없음 — 신뢰도 낮음)
        "수원시 영통구": 3_100_000,
        "수원시 팔달구": 2_800_000,
        "용인시 수지구": 3_500_000,
        "서울 강남구": 8_000_000,
        "서울 마포구": 5_500_000,
    }.get(region, 3_000_000)

    avg = int(price_per_m2 * area_m2)
    return {
        "source": "추정 시세 (데모 — API 키 필요)",
        "count": 0,
        "avg_price": avg,
        "min_price": int(avg * 0.85),
        "max_price": int(avg * 1.15),
        "region": region,
        "area_m2": area_m2,
    }
