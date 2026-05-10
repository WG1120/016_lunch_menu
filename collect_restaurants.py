"""
서울 시청 근처 맛집 데이터 수집 스크립트
지정된 44개 식당을 네이버 지역 검색 API로 개별 검색하여 정보를 수집합니다.
"""

import os
import re
import json
import math
import time
import requests
from dotenv import load_dotenv

# .env 파일에서 환경변수 로드
load_dotenv()

# 네이버 API 인증 정보 (여러 키 형식 호환)
CLIENT_ID = (
    os.environ.get("NAVER_CLIENT_ID")
    or os.environ.get("X-Naver-Client-Id")
)
CLIENT_SECRET = (
    os.environ.get("NAVER_CLIENT_SECRET")
    or os.environ.get("X-Naver-Client-Secret")
)

# 기준 위치: 서울 중구 세종대로 67 (서울시청)
BASE_LAT = 37.5663
BASE_LNG = 126.9779

# 도보 속도: 80m/분
WALK_SPEED = 80

# 수집 대상 식당 목록 (44개)
RESTAURANT_LIST = [
    "술술돼지", "누나홀닭", "함평집", "전주다대기", "담원순대",
    "명동순대국", "우림정", "오늘통닭", "슬로우캘리", "교동전선생",
    "십원집", "신의주찹쌀순대", "가배도", "당당", "완백부대찌개",
    "오한수 우육면가", "고래카레", "유브유부", "서평옥", "브라운돈까스",
    "아이엠티", "뱃남미식", "포항집", "멘츠루", "도우보이즈클럽",
    "정동칼국수", "유방녕의웍", "승환네 닭한마리", "정원레스토랑 어반가든",
    "방일해장국", "카츠하이드", "리나스 숭례문", "이여곰탕", "백채김치찌개",
    "달인명동칼국수보쌈", "쪽삼상회", "멘무샤", "송원스키야키샤브샤브",
    "남경", "굽돌집", "김명자굴국밥", "북창동개성칼만두", "무교동북어국집",
    "이타마에스시 광화문디타워점",
]


def haversine(lat1, lng1, lat2, lng2):
    """두 좌표 간 직선 거리를 미터 단위로 계산 (하버사인 공식)"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def clean_html(text):
    """HTML 태그 및 HTML 엔티티 제거"""
    import html
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def katec_to_wgs84(mapx, mapy):
    """네이버 API의 KATEC 좌표를 WGS84 위경도로 근사 변환"""
    try:
        x = int(mapx)
        y = int(mapy)
    except (ValueError, TypeError):
        return None, None

    # KATEC → WGS84 근사 변환 공식
    lng = (x / 10000000.0)
    lat = (y / 10000000.0)

    # 대한민국 범위 확인
    if 33 <= lat <= 43 and 124 <= lng <= 132:
        return lat, lng
    return None, None


def classify_category(category_str):
    """네이버 카테고리 문자열을 대분류로 매핑"""
    if not category_str:
        return "기타"
    mapping = [
        ("한식", "한식"), ("한정식", "한식"), ("백반", "한식"), ("국밥", "한식"),
        ("냉면", "한식"), ("삼겹살", "한식"), ("갈비", "한식"), ("찌개", "한식"),
        ("전골", "한식"), ("비빔밥", "한식"), ("칼국수", "한식"), ("설렁탕", "한식"),
        ("감자탕", "한식"), ("곱창", "한식"), ("순대", "한식"), ("족발", "한식"),
        ("보쌈", "한식"), ("삼계탕", "한식"), ("해장국", "한식"), ("죽", "한식"),
        ("국수", "한식"), ("육류", "한식"), ("곰탕", "한식"), ("만두", "한식"),
        ("북어", "한식"), ("굴국밥", "한식"), ("닭한마리", "한식"), ("부대찌개", "한식"),
        ("김치", "한식"), ("돼지", "한식"),
        ("분식", "분식"), ("떡볶이", "분식"), ("김밥", "분식"),
        ("중식", "중식"), ("중국", "중식"), ("짜장", "중식"), ("짬뽕", "중식"), ("마라", "중식"),
        ("일식", "일식"), ("일본", "일식"), ("초밥", "일식"), ("스시", "일식"),
        ("라멘", "일식"), ("우동", "일식"), ("돈카츠", "일식"), ("돈까스", "일식"),
        ("덮밥", "일식"), ("카레", "일식"), ("스키야키", "일식"), ("샤브", "일식"),
        ("양식", "양식"), ("파스타", "양식"), ("피자", "양식"), ("이탈리", "양식"),
        ("햄버거", "양식"), ("버거", "양식"), ("샌드위치", "양식"), ("브런치", "양식"),
        ("베트남", "아시안"), ("쌀국수", "아시안"), ("태국", "아시안"),
        ("인도", "아시안"), ("커리", "아시안"), ("아시아", "아시안"),
        ("치킨", "치킨"), ("닭", "치킨"),
    ]
    for keyword, label in mapping:
        if keyword in category_str:
            return label
    return "기타"


def search_restaurant(name):
    """네이버 지역 검색 API로 식당 1건 검색"""
    url = "https://openapi.naver.com/v1/search/local.json"
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET,
    }
    params = {
        "query": f"{name} 중구",
        "display": 1,
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("items"):
            return data["items"][0]
    except requests.RequestException as e:
        print(f"  [API 오류] {name}: {e}")
    return None


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("[오류] API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.")
        return

    print("=" * 55)
    print(" 서울 시청 근처 맛집 데이터 수집 시작")
    print(f" 대상: {len(RESTAURANT_LIST)}개 식당")
    print("=" * 55)

    results = []
    not_found = []

    for i, name in enumerate(RESTAURANT_LIST, 1):
        print(f"[{i:2d}/{len(RESTAURANT_LIST)}] 검색 중: {name}", end=" ... ")

        item = search_restaurant(name)
        if not item:
            print("검색 결과 없음")
            not_found.append(name)
            time.sleep(0.3)
            continue

        title = clean_html(item.get("title", ""))
        category = item.get("category", "")
        address = item.get("address", "")
        link = item.get("link", "")
        mapx = item.get("mapx", "")
        mapy = item.get("mapy", "")

        # 좌표 변환 및 거리 계산
        lat, lng = katec_to_wgs84(mapx, mapy)
        if lat and lng:
            distance_m = haversine(BASE_LAT, BASE_LNG, lat, lng)
            walk_min = max(1, round(distance_m / WALK_SPEED))
        else:
            distance_m = 0
            walk_min = 0

        main_cat = classify_category(category)

        results.append({
            "name": title,
            "category": main_cat,
            "category_detail": category,
            "address": address,
            "link": link,
            "distance_m": round(distance_m),
            "walk_minutes": walk_min,
            "walk_display": f"약 {walk_min}분" if walk_min > 0 else "정보없음",
        })

        print(f"OK → {title} ({main_cat}, {results[-1]['walk_display']})")
        time.sleep(0.3)

    # 중복 제거 (식당명 기준)
    seen = {}
    unique = []
    for r in results:
        if r["name"] not in seen:
            seen[r["name"]] = True
            unique.append(r)

    # 도보 소요시간 오름차순 정렬
    unique.sort(key=lambda x: x["walk_minutes"])

    # JSON 저장
    output = os.path.join(os.path.dirname(os.path.abspath(__file__)), "restaurants.json")
    with open(output, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 55)
    print(f" 수집 완료: {len(unique)}개 식당")
    if not_found:
        print(f" 검색 실패: {len(not_found)}개 → {', '.join(not_found)}")
    print(f" 저장: {output}")
    print("=" * 55)


if __name__ == "__main__":
    main()
