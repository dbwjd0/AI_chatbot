import json
import os
import base64
import re
from django.utils import timezone
from typing import Optional, Dict, Any, Tuple
from openai import OpenAI, APIError
from django.core.files.uploadedfile import UploadedFile

from ..models import ChatMessage, UserAttribute, UserActivity, ActivityAnalytics, UserRelationship
from .context_service import get_activity_recommendation, search_activities_for_context
from .memory_service import extract_and_save_user_context_data
from .image_captioning_service import ImageCaptioningService
from . import vector_service, location_service, schedule_service, emoticon_service, prompt_service, rl_agent_service, friend_message_service # rl_agent_service, friend_message_service 추가
from .llm_utils import call_openai_api # _call_openai_api 함수를 llm_utils로 이동
from datetime import date # date 추가

FOOD_CATEGORIES = {
    # 직접 일치
    "카레": "카레.png",
    "햄버거": "햄버거.png",
    "콜라": "콜라.png",
    "김밥": "김밥.png",
    "돈가스": "돈가스.png",
    "떡볶이": "떡볶이.png",
    "라면": "라면.png",
    "아이스크림": "아이스크림.png",
    "초밥": "초밥.png",
    "치킨": "치킨.png",
    "커피": "커피.png",
    "피자": "피자.png",

    # '탕류' 카테고리
    "짬뽕": "탕류.png",
    "짜글이": "탕류.png",
    "김치찌개": "탕류.png",
    "된장찌개": "탕류.png",
    "부대찌개": "탕류.png",
    "국밥": "탕류.png",
    "갈비탕": "탕류.png",
    "설렁탕": "탕류.png",
    "육개장": "탕류.png",
    "감자탕": "탕류.png",

    # '과자류' 카테고리
    "과자": "과자류.png",
    "비스킷": "과자류.png",
    "감자칩": "과자류.png",
    "팝콘": "과자류.png",
    "새우깡": "과자류.png",

    # '고기류' 카테고리
    "고기": "고기류.png",
    "삼겹살": "고기류.png",
    "소고기": "고기류.png",
    "돼지고기": "고기류.png",
    "스테이크": "고기류.png",
    "갈비": "고기류.png",

    # '꼬치류' 카테고리
    "꼬치": "꼬치류.png",
    "닭꼬치": "꼬치류.png",
    "염통꼬치": "꼬치류.png",

    # '덮밥류' 카테고리
    "덮밥": "덥밥류.png",
    "제육덮밥": "덥밥류.png",
    "오징어덮밥": "덥밥류.png",
    "카레덮밥": "덥밥류.png",

    # '빵류' 카테고리
    "빵": "빵류.png",
    "케이크": "빵류.png",
    "도넛": "빵류.png",
    "베이글": "빵류.png",
    "크루아상": "빵류.png",

    # '생선류' 카테고리
    "생선": "생선류.png",
    "고등어": "생선류.png",
    "갈치": "생선류.png",
    "연어": "생선류.png",
    "회": "생선류.png",
}

def _handle_food_memory(request, user_message: str):
    """사용자 메시지에서 음식 언급을 감지하고 세션에 저장합니다."""
    # 간단한 정규 표현식으로 "음식 먹었어"와 같은 패턴 감지
    for food_name, image_file in FOOD_CATEGORIES.items():
        # 더 유연한 감지를 위해 "먹었"과 유사한 단어들을 포함
        patterns = [
            rf"{food_name}.*(먹었|먹고|먹는|먹었다|먹으니|먹으니까|먹어서)",
            rf".*{food_name}.*(먹었|먹고|먹는|먹었다|먹으니|먹으니까|먹어서)"
        ]
        if any(re.search(pattern, user_message) for pattern in patterns):
            eaten_foods = request.session.get('eaten_foods', [])
            
            # 중복 확인
            is_duplicate = any(food['name'] == food_name for food in eaten_foods)
            
            if not is_duplicate:
                food_data = {'name': food_name, 'image': image_file}
                eaten_foods.append(food_data)
                request.session['eaten_foods'] = eaten_foods
                print(f"--- [음식 기억] '{food_name}'을(를) 세션에 저장했습니다. 이미지: {image_file} ---")
            else:
                print(f"--- [음식 기억] '{food_name}'은(는) 이미 세션에 존재합니다. ---")
            
            # 하나의 음식만 처리하고 함수 종료
            return


def process_chat_interaction(request, user_message_text: str, user_emotion: str, latitude: Optional[float] = None, longitude: Optional[float] = None, image_file: Optional[UploadedFile] = None):
    """사용자 메시지를 처리하고 AI 응답을 생성하는 전체 프로세스를 조율합니다."""
    user = request.user
    bot_message_text = "죄송합니다. API 응답을 가져오는 데 실패했습니다."
    explanation = ""
    bot_message_obj = None
    user_message_obj = None

    try:
        action_data = {} # RL 에이전트의 행동을 저장할 변수
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        
        client = OpenAI()

        # 0단계: 이모티콘 파싱
        user_message_for_llm = emoticon_service.parse_emoticon(user_message_text)

        # 1단계: 이미지 분석 (이미지가 있는 경우)
        image_analysis_context = None
        if image_file:
            print("--- [디버그] 이미지 파일 감지됨. 1차 분석 시작 ---")
            
            # 추가된 디버깅 로그
            print(f"--- [디버그] 파일명: {image_file.name}, Content-Type: {image_file.content_type} ---")
            # ImageCaptioningService가 Base64를 사용하므로, 파일 내용을 인코딩하여 전달
            image_b64_data = base64.b64encode(image_file.read()).decode('utf-8')
            image_file.seek(0) # 파일을 다시 읽을 수 있도록 포인터를 처음으로 되돌림
            analyzer = ImageCaptioningService()
             # 업로드된 파일의 content_type을 함께 전달
            analysis_result = analyzer.analyze_image(image_b64_data, user_message_text, image_file.content_type)
            if analysis_result:
                image_analysis_context = analysis_result
                print("--- [디버그] 1차 분석 완료 --- ")
            else:
                print("--- [경고] 1차 분석 실패 --- ")

        # 2단계: RL 에이전트를 통해 행동(컨텍스트, 페르소나) 결정
        history = ChatMessage.objects.filter(user=user).order_by('-timestamp')
        action_data = rl_agent_service.decide_action(user, user_message_for_llm, history, has_image=bool(image_file), user_emotion=user_emotion)
        
        # "질문하기" 행동 특별 처리
        if action_data.get('chosen_persona_name') == 'Questioner':
            bot_message_text = "무슨 말인지 잘 모르겠어. 조금 더 자세히 설명해 줄래?"
            explanation = "에이전트가 사용자 의도를 명확히 하기 위해 질문을 선택했습니다."
            
            # 대화 저장
            user_message_obj = ChatMessage.objects.create(user=user, message=user_message_text, image=image_file, is_user=True)
            bot_message_obj = ChatMessage.objects.create(user=user, message=bot_message_text, is_user=False)
            
            # 벡터 DB에도 저장
            collection_name = vector_service.get_or_create_collection()
            vector_service.upsert_message(collection_name, user_message_obj)
            vector_service.upsert_message(collection_name, bot_message_obj)

            return bot_message_text, explanation, bot_message_obj, user_message_obj, action_data

        # 3단계: 결정된 행동에 따라 컨텍스트 생성
        time_contexts = _get_time_contexts(history)
        assembled_contexts = _assemble_context_data(
            user, 
            user_message_for_llm, 
            action_data['contexts_to_use'], # RL 에이전트가 선택한 컨텍스트 목록
            latitude, 
            longitude
        )
        
        # 4단계: 최종 프롬프트 생성 (이미지 분석 결과 및 페르소나 포함)
        final_system_prompt = prompt_service.build_final_system_prompt(
            user, 
            time_contexts, 
            assembled_contexts, 
            action_data['persona_prompt'], # RL 에이전트가 선택한 페르소나
            image_analysis_context
        )
        messages = _prepare_llm_messages(final_system_prompt, history, user_message_for_llm)

        # 5단계: 최종 LLM 호출 (파인튜닝된 모델)
        model_to_use = os.getenv("FINETUNED_MODEL_ID", "gpt-4.1")
        response_json = call_openai_api(client, model_to_use, messages)
        
        # 6단계: 응답 처리 및 저장
        bot_message_text, explanation, bot_message_obj, user_message_obj = _finalize_chat_interaction(
            request, user_message_text, response_json, history, api_key, image_file
        )

    except APIError as e:
        print(f"OpenAI API 요청 실패: {e}")
        bot_message_text = f"API 요청 중 오류가 발생했습니다: {e}"
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"API 응답 형식 오류: {e}")
        bot_message_text = "API 응답 형식이 예상과 다릅니다."
    except Exception as e:
        import traceback
        print(f"예상치 못한 오류: {e}")
        traceback.print_exc()
        bot_message_text = f"예상치 못한 오류가 발생했습니다: {e}"

    return bot_message_text, explanation, bot_message_obj, user_message_obj, action_data

def generate_object_monologue(user, target: str) -> str:
    """오브젝트 상호작용 시 AI의 동적 독백을 생성합니다."""
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
        client = OpenAI()

        # 1. 페르소나 프롬프트 빌드
        persona_prompt = prompt_service.build_persona_system_prompt(user, user.profile.persona_preference)

        # 2. 독백 생성을 위한 특별 지시사항 추가
        monologue_instruction = (
            f"\n## 추가 임무: 사물에 대한 독백 생성 ##\n"
            f"너는 지금 '{target}'을(를) 보고 있어. 이 사물에 대해 너의 현재 페르소나와 감정, 그리고 {user.username}님과의 관계를 바탕으로 짧은 독백을 해줘."
            f"이 독백은 너 혼자 생각하는 것이며, 사용자에게 질문하거나 답변을 요구해서는 안 돼."
            f"반드시 1~2문장의 짧고 간결한 생각으로 표현해야 해."
            f"답변은 다른 어떤 설명도 없이, 오직 독백 내용만 일반 텍스트로 반환해야 해. JSON 형식이 아니야."
        )

        final_prompt = persona_prompt + monologue_instruction
        
        messages = [
            {'role': 'system', 'content': final_prompt},
        ]

        # 3. LLM 호출
        model_to_use = os.getenv("FINETUNED_MODEL_ID", "gpt-4.1")
        response = client.chat.completions.create(
            model=model_to_use,
            messages=messages,
            temperature=0.8, # 약간 더 창의적인 답변을 위해 온도 조절
            top_p=0.9,
            max_tokens=100,
            frequency_penalty=0.3,
            presence_penalty=0.2,
        )
        
        monologue = response.choices[0].message.content.strip()
        return monologue

    except Exception as e:
        print(f"독백 생성 중 오류 발생: {e}")
        return "..."

def _get_time_contexts(history):
    """현재 시간 및 마지막 대화와의 시간 간격에 대한 컨텍스트를 생성합니다."""
    now_utc = timezone.now()
    korea_tz = timezone.get_default_timezone()
    now_korea = now_utc.astimezone(korea_tz)
    
    weekdays = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    day_of_week = weekdays[now_korea.weekday()]
    time_str = now_korea.strftime(f'%Y년 %m월 %d일 {day_of_week} %H시 %M분')
    current_time_context = f"[시간 정보]: 현재 대한민국 시간은 정확히 '{time_str}'이야. 시간과 관련된 모든 질문에 이 정보를 최우선으로 사용해서 답해야 해. 절대 다른 시간을 말해서는 안 돼"
    
    time_awareness_context = ""
    if history.exists():
        last_interaction = history.first()
        time_difference = now_utc - last_interaction.timestamp
        if time_difference.total_seconds() > 3600:
            hours = int(time_difference.total_seconds() // 3600)
            minutes = int((time_difference.total_seconds() % 3600) // 60)
            time_gap_str = f"{hours}시간 {minutes}분"
            last_message_text = last_interaction.message
            sender = "네가" if last_interaction.is_user else "내가"
            time_awareness_context = f"[최근 마지막 대화정보]: 마지막 대화로부터 약 {time_gap_str}이 지났어. 마지막에 {sender} 한 말은 '{last_message_text}'이었어. 이 시간의 공백을 네 캐릭터에 맞게 재치있게 언급하며 대화를 시작해줘."

    return current_time_context, time_awareness_context

def _assemble_context_data(user, user_message_text, contexts_to_use: list, latitude=None, longitude=None):
    """RL 에이전트가 선택한 컨텍스트 목록에 따라 필요한 사용자 기억 및 관련 정보를 수집합니다."""
    contexts = {}

    # 0. 오늘의 일정 컨텍스트
    if 'schedule' in contexts_to_use:
        try:
            today_schedules = schedule_service.get_schedules_for_day(user, date.today())
            if today_schedules:
                schedule_contents = [s.content.strip() for s in today_schedules if s.content and s.content.strip()]
                if schedule_contents:
                    contexts['schedule'] = f"[사용자의 오늘 일정 (참고용)]: {', '.join(schedule_contents)}"
        except Exception as e:
            print(f"--- 스케줄 컨텍스트 생성 오류: {e} ---")

    # 1. 위치 컨텍스트 및 위치 기반 추천 컨텍스트
    if 'location' in contexts_to_use and latitude is not None and longitude is not None:
        location_context = location_service.get_location_context(latitude, longitude)
        if location_context:
            contexts['location'] = location_context

        location_recommendation_result = location_service.get_location_based_recommendation(user, user_message_text, latitude, longitude)
        if location_recommendation_result:
            contexts['location_recommendation'] = location_recommendation_result

    # 2. 벡터 검색 컨텍스트
    if 'vector_search' in contexts_to_use:
        try:
            collection_name = vector_service.get_or_create_collection()
            similar_results = vector_service.query_similar_messages(collection_name, user_message_text, user.id, n_results=5)
            if similar_results and isinstance(similar_results, dict) and similar_results.get('documents'):
                past_conversations = [f"{meta.get('speaker', '알수없음')}: {doc}" for doc, meta in zip(similar_results['documents'], similar_results['metadatas'])]
                contexts['vector_search'] = "[과거 유사한 대화 내용(벡터DB)]: " + " | ".join(past_conversations)
        except Exception as e:
            print(f"--- 벡터 검색 컨텍스트 생성 오류: {e} ---")

    # 3. 사용자 속성 컨텍스트
    if 'attributes' in contexts_to_use:
        user_attributes = UserAttribute.objects.filter(user=user)
        if user_attributes.exists():
            attribute_strings = [f"{attr.fact_type}: {attr.content}" for attr in user_attributes]
            contexts['attributes'] = "[사용자 속성]: " + ", ".join(attribute_strings)

    # 4. 사용자 활동 컨텍스트
    if 'activity' in contexts_to_use:
        activity_strings = []
        try:
            recent_activities = UserActivity.objects.filter(user=user).order_by('-activity_date', '-created_at')[:5]
            if recent_activities:
                activity_strings.extend([
                    f"{act.activity_date.strftime('%Y-%m-%d') if act.activity_date else '날짜 미상'} '{act.place}' 방문" +
                    (f" (동행: {act.companion})" if act.companion else "") +
                    (f" (메모: {act.memo})" if act.memo else "")
                    for act in recent_activities
                ])
        except Exception as e:
            print(f"--- 활동 메모리 컨텍스트 생성 오류: {e} ---")

        search_context = search_activities_for_context(user, user_message_text)
        if search_context:
            activity_strings.append(search_context)
        
        recommendation_context = get_activity_recommendation(user, user_message_text)
        if recommendation_context:
            activity_strings.append(recommendation_context)

        if activity_strings:
            contexts['activity'] = "[사용자 활동]: " + "\n".join(activity_strings)

    # 5. 활동 분석 컨텍스트
    if 'analytics' in contexts_to_use:
        try:
            recent_analytics = ActivityAnalytics.objects.filter(user=user).order_by('-period_start_date')[:3]
            if recent_analytics.exists():
                analytics_strings = [
                    f"'{an.period_start_date.strftime('%Y-%m-%d')}부터 {an.period_type} 동안 "
                    f"장소: {an.place}, 동행: {an.companion or '없음'}, 횟수: {an.count}회'"
                    for an in recent_analytics
                ]
                contexts['analytics'] = "[사용자 활동 분석]: " + "\n".join(analytics_strings)
        except Exception as e:
            print(f"--- 활동 분석 컨텍스트 생성 오류: {e} ---")

    # 6. 인간관계 컨텍스트
    if 'relationship' in contexts_to_use:
        try:
            user_relationships = UserRelationship.objects.filter(user=user)
            if user_relationships.exists():
                relationship_strings = [f"{rel.name} ({rel.relationship_type}, 특징: {rel.traits})" for rel in user_relationships]
                contexts['relationship'] = "[사용자의 인간관계]: " + "\n".join(relationship_strings)
        except Exception as e:
            print(f"--- 사용자 관계 컨텍스트 생성 오류: {e} ---")

    # 디버깅을 위해 모든 수집된 컨텍스트를 마지막에 한번에 출력
    for key, value in contexts.items():
        print(f"--- [디버그] {key} 컨텍스트: {value} ---")

    return contexts

def _prepare_llm_messages(final_system_prompt, history, user_message_text):
    """API 요청을 위한 메시지 리스트를 준비합니다."""
    messages = [{'role': 'system', 'content': final_system_prompt}]
    recent_history = history[:10]
    for chat in reversed(recent_history):
        role = "user" if chat.is_user else "assistant"
        messages.append({'role': role, 'content': chat.message})
    messages.append({'role': 'user', 'content': user_message_text})
    return messages

def _call_openai_api(client: OpenAI, model_to_use: str, messages: list) -> Dict[str, Any]:
    """OpenAI API를 호출하고 응답 JSON을 반환합니다."""
    print(f"--- 사용 모델: {model_to_use} ---")
    response = client.chat.completions.create(
        model=model_to_use,
        messages=messages,
        temperature=0.7,
        top_p=0.9,
        frequency_penalty=0.2,
        presence_penalty=0.1,
        response_format={"type": "json_object"}
    )
    return response.model_dump()

def _finalize_chat_interaction(request, user_message_text, response_json, history, api_key, image_file: Optional[UploadedFile] = None):
    """성공적인 LLM 응답을 처리하고 관련 데이터를 RDB와 벡터 DB에 저장합니다."""
    _handle_food_memory(request, user_message_text)
    user = request.user
    bot_message_text = "음... 생각을 정리하는 데 시간이 좀 걸리네. 다시 한번 말해줄래?"
    explanation = "AI 응답 처리 중 오류 발생."
    bot_message_obj = None
    user_message_obj = None

    try:
        if 'choices' not in response_json or not response_json['choices'] or \
           'message' not in response_json['choices'][0] or \
           'content' not in response_json['choices'][0]['message']:
            raise ValueError("OpenAI API 응답에 'content' 필드가 누락되었습니다.")

        content_from_llm_raw = response_json['choices'][0]['message']['content']

        if content_from_llm_raw is None:
            raise ValueError("OpenAI API 응답의 'content' 필드가 None입니다.")

        # --- 스마트 파싱 로직 시작 ---
        parsed_successfully = False
        try:
            # 가장 먼저, 전체가 유효한 JSON인지 시도
            content_from_llm = json.loads(content_from_llm_raw)
            if 'answer' in content_from_llm:
                bot_message_text = content_from_llm.get('answer', '').strip()
                explanation = content_from_llm.get('explanation', '설명 없음.')
                parsed_successfully = True
            else:
                 explanation = f"LLM 응답 JSON에 'answer' 키가 누락되었습니다: {content_from_llm}"
                 bot_message_text = "AI 응답 형식이 잘못되었습니다. (answer 키 누락)"

        except json.JSONDecodeError:
            # JSON 파싱 실패 시, 문자열 내에서 JSON을 찾아보는 로직
            try:
                start_index = content_from_llm_raw.find('{')
                end_index = content_from_llm_raw.rfind('}') + 1
                if start_index != -1 and end_index != 0:
                    json_str = content_from_llm_raw[start_index:end_index]
                    content_from_llm = json.loads(json_str)
                    if 'answer' in content_from_llm:
                        bot_message_text = content_from_llm.get('answer', '').strip()
                        explanation = content_from_llm.get('explanation', '설명 없음.')
                        parsed_successfully = True
                    else:
                        explanation = f"추출된 JSON에 'answer' 키가 누락되었습니다: {content_from_llm}"
                        bot_message_text = "AI 응답 형식이 잘못되었습니다. (추출된 JSON에 answer 키 누락)"

            except json.JSONDecodeError:
                 explanation = f"LLM 응답에서 JSON을 추출하여 파싱하는 데 실패했습니다."
                 bot_message_text = "AI 응답 형식이 잘못되었습니다. (JSON 파싱 실패)"
        
        # 최종적으로 파싱에 실패했다면, 원본 텍스트라도 답변으로 사용
        if not parsed_successfully and content_from_llm_raw.strip():
            bot_message_text = content_from_llm_raw.strip()
            explanation = "AI가 지정된 JSON 형식을 따르지 않았으나, 원본 응답을 그대로 반환합니다."
        elif not parsed_successfully: # 파싱에 완전히 실패했고, 원본 응답도 비어있거나 없음
            bot_message_text = f"AI 응답 파싱 실패. 원본 응답: '{content_from_llm_raw}'. 설명: {explanation}"
            explanation = "LLM 응답 파싱에 실패하여 디버그 메시지를 반환합니다."
        
        # 답변이 비어있는 경우 방지
        if not bot_message_text.strip():
            bot_message_text = "음... 뭐라 답해야 할지 잘 모르겠어. 다른 질문 해줄래?"
            explanation = "파싱 후 최종 답변이 비어있어 대체 메시지를 사용합니다."

        # --- 스마트 파싱 로직 끝 ---

    except (ValueError, KeyError, IndexError) as e:
        explanation = f"LLM 응답 구조 파싱 실패: {e}"
    except Exception as e:
        explanation = f"예상치 못한 오류 발생: {e}"

    # ChromaDB 컬렉션 가져오기
    collection_name = vector_service.get_or_create_collection()

    # ChatMessage 저장 시 image_file을 직접 사용
    user_message_obj = ChatMessage.objects.create(user=user, message=user_message_text, image=image_file, is_user=True)
    vector_service.upsert_message(collection_name, user_message_obj)

    bot_message_obj = ChatMessage.objects.create(user=user, message=bot_message_text, is_user=False)
    vector_service.upsert_message(collection_name, bot_message_obj)
    
    recent_history_for_extraction = history[:5]
    extract_and_save_user_context_data(user, user_message_text, bot_message_text, recent_history_for_extraction, api_key)

    # 디버깅을 위해 최종 explanation 내용을 터미널에 출력
    print("\n" + "-"*20 + " [Debug] Response Explanation " + "-"*20)
    print(explanation)
    print("-"*66 + "\n")

    return bot_message_text, explanation, bot_message_obj, user_message_obj