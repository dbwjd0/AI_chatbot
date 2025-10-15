import os
import requests

def get_location_context(latitude, longitude):
    """
    좌표를 사용하여 현재 위치에 대한 컨텍스트 문자열을 생성합니다.
    (예: '[현재 위치: 스타벅스 강남점]')
    """
    api_key = os.environ.get("KAKAO_API_KEY")
    if not api_key:
        return ""

    headers = {"Authorization": f"KakaoAK {api_key}"}
    
    try:
        # 1. 좌표를 주소로 변환하여 주소 및 건물명 획득
        coord_params = {"x": longitude, "y": latitude}
        response = requests.get("https://dapi.kakao.com/v2/local/geo/coord2address.json", headers=headers, params=coord_params)
        response.raise_for_status()
        address_data = response.json()

        if not address_data['documents']:
            return ""

        address_doc = address_data['documents'][0]
        road_address = address_doc.get('road_address')
        address_name = address_doc['address']['address_name']

        # 2. 건물명이 있으면 우선적으로 사용
        if road_address and road_address.get('building_name'):
            return f"[현재 위치: {road_address['building_name']}]"

        # 3. 건물명이 없는 경우, 주소를 키워드로 주변 장소 검색
        keyword_params = {
            'query': address_name,
            'x': longitude,
            'y': latitude,
            'radius': 20,
            'sort': 'distance'
        }
        response = requests.get("https://dapi.kakao.com/v2/local/search/keyword.json", headers=headers, params=keyword_params)
        response.raise_for_status()
        places_data = response.json()

        if places_data['documents']:
            return f"[현재 위치: {places_data['documents'][0]['place_name']}]"
        
        # 4. 모든 검색에 실패한 경우, 주소 자체를 컨텍스트로 사용
        if address_name:
            return f"[현재 위치: {address_name} 부근]"

    except (requests.exceptions.RequestException, KeyError, IndexError) as e:
        print(f"Kakao API 호출 오류: {e}")
    
    return ""

def find_nearby_restaurants(latitude, longitude):
    """
    주변 음식점을 검색하여 추천 목록 문자열을 생성합니다.
    """
    api_key = os.environ.get("KAKAO_API_KEY")
    if not api_key:
        return ""

    headers = {"Authorization": f"KakaoAK {api_key}"}
    params = {
        "category_group_code": "FD6", # 음식점
        "x": longitude,
        "y": latitude,
        "radius": 500,  # 500미터 반경
        "sort": "accuracy", # 정확도 순
    }

    try:
        response = requests.get("https://dapi.kakao.com/v2/local/search/category.json", headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        if not data['documents']:
            return ""

        restaurant_list = []
        for place in data['documents'][:5]: # 최대 5개
            restaurant_list.append(f"{place['place_name']} ({place['category_name'].split(' > ')[-1].strip()})")
        
        return "[주변 맛집 정보: " + ", ".join(restaurant_list) + "]"

    except (requests.exceptions.RequestException, KeyError) as e:
        print(f"Kakao API 주변 검색 오류: {e}")
        return ""
