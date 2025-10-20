import json
import os
import base64
from django.utils import timezone
from typing import Optional, Dict, Any, Tuple
from openai import OpenAI, APIError
from django.core.files.uploadedfile import UploadedFile

from ..models import ChatMessage, UserAttribute, UserActivity, ActivityAnalytics, UserRelationship
from .context_service import get_activity_recommendation, search_activities_for_context
from .memory_service import extract_and_save_user_context_data
from .image_captioning_service import ImageCaptioningService
from . import vector_service, location_service, schedule_service # schedule_service 추가
from datetime import date # date 추가


def process_chat_interaction(request, user_message_text: str, latitude: Optional[float] = None, longitude: Optional[float] = None, image_file: Optional[UploadedFile] = None):
    """사용자 메시지를 처리하고 AI 응답을 생성하는 전체 프로세스를 조율합니다."""
    user = request.user
    bot_message_text = "죄송합니다. API 응답을 가져오는 데 실패했습니다."
    explanation = ""
    bot_message_obj = None
    user_message_obj = None

    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        
        client = OpenAI()

        # 1단계: 이미지 분석 (이미지가 있는 경우)
        image_analysis_context = None
        image_b64_data = None
        if image_file:
            print("--- [디버그] 이미지 파일 감지됨. 1차 분석 시작 ---")
            # ImageCaptioningService가 Base64를 사용하므로, 파일 내용을 인코딩하여 전달
            image_b64_data = base64.b64encode(image_file.read()).decode('utf-8')
            image_file.seek(0) # 파일을 다시 읽을 수 있도록 포인터를 처음으로 되돌림

            analyzer = ImageCaptioningService()
            analysis_result = analyzer.analyze_image(image_b64_data, user_message_text)
            if analysis_result:
                image_analysis_context = analysis_result
                print("--- [디버그] 1차 분석 완료 --- ")
            else:
                print("--- [경고] 1차 분석 실패 --- ")

        # 2단계: 컨텍스트 생성
        history = ChatMessage.objects.filter(user=user).order_by('-timestamp')
        time_contexts = _get_time_contexts(history)
        # 벡터 검색은 이미지가 없을 때만 수행하여 효율성 증대
        assembled_contexts = _assemble_context_data(user, user_message_text, latitude, longitude, bool(image_file))
        
        # 3단계: 최종 프롬프트 생성 (이미지 분석 결과 포함)
        final_system_prompt = _build_final_system_prompt(user, time_contexts, assembled_contexts, image_analysis_context)
        messages = _prepare_llm_messages(final_system_prompt, history, user_message_text)

        # 4단계: 최종 LLM 호출 (파인튜닝된 모델)
        model_to_use = os.getenv("FINETUNED_MODEL_ID", "gpt-4.1")
        response_json = _call_openai_api(client, model_to_use, messages)
        
        # 5단계: 응답 처리 및 저장
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

    # user_message_obj를 반환하도록 수정
    return bot_message_text, explanation, bot_message_obj, user_message_obj

def _get_time_contexts(history):
    """현재 시간 및 마지막 대화와의 시간 간격에 대한 컨텍스트를 생성합니다."""
    now_utc = timezone.now()
    korea_tz = timezone.get_default_timezone()
    now_korea = now_utc.astimezone(korea_tz)
    
    weekdays = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    day_of_week = weekdays[now_korea.weekday()]
    time_str = now_korea.strftime(f'%Y년 %m월 %d일 {day_of_week} %H시 %M분')
    current_time_context = f"[시스템 정보: 현재 대한민국 시간은 정확히 '{time_str}'이야. 시간과 관련된 모든 질문에 이 정보를 최우선으로 사용해서 답해야 해. 절대 다른 시간을 말해서는 안 돼.]"
    
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
            time_awareness_context = f"[시스템 정보: 마지막 대화로부터 약 {time_gap_str}이 지났어. 마지막에 {sender} 한 말은 '{last_message_text}'이었어. 이 시간의 공백을 네 캐릭터에 맞게 재치있게 언급하며 대화를 시작해줘.]"

    return current_time_context, time_awareness_context

def _assemble_context_data(user, user_message_text, latitude=None, longitude=None, has_image=False):
    """사용자의 기억과 관련된 모든 컨텍스트를 종합하여 반환합니다."""
    contexts = {}
    # 0. 오늘의 일정 컨텍스트
    schedule_context = ""
    try:
        today_schedule = schedule_service.get_or_create_schedule(user, date.today())
        if today_schedule and today_schedule.content.strip():
            schedule_context = f"[사용자의 오늘 일정 (참고용): {today_schedule.content.strip()}]"
            contexts['schedule'] = schedule_context
            print(f"--- [디버그] 오늘 일정 컨텍스트: {schedule_context} ---")
    except Exception as e:
        print(f"--- Could not build schedule context due to an error: {e} ---")


    # 1. 위치 컨텍스트
    location_context = ""
    if latitude is not None and longitude is not None:
        location_context = location_service.get_location_context(latitude, longitude)
        if location_context:
            contexts['location'] = location_context
            print(f"--- [디버그] 현재 위치 컨텍스트: {location_context} ---")

    # 2. 위치 기반 추천 컨텍스트 (맛집, 카페 등)
    location_recommendation_context = location_service.get_location_based_recommendation(user, user_message_text, latitude, longitude)
    if location_recommendation_context:
        print(f"--- [디버그] 위치 기반 추천 컨텍스트: {location_recommendation_context} ---")
        contexts['location'] = location_context
        
        # 위치 기반 추천 컨텍스트
        location_recommendation = location_service.get_location_based_recommendation(user, user_message_text, latitude, longitude)
        if location_recommendation:
            contexts['location_recommendation'] = location_recommendation

    # 3. 벡터 검색 컨텍스트 (이미지가 없을 때만 수행)
    if not has_image:
        try:
            collection = vector_service.get_or_create_collection()
            similar_results = vector_service.query_similar_messages(collection, user_message_text, user.id, n_results=5)
            if similar_results and isinstance(similar_results, dict) and similar_results.get('documents'):
                past_conversations = [f"{meta.get('speaker', '알수없음')}: {doc}" for doc, meta in zip(similar_results['documents'], similar_results['metadatas'])]
                contexts['vector_search'] = "[과거 관련 대화 내용(벡터DB): " + " | ".join(past_conversations) + "]"
        except Exception as e:
            print(f"--- 벡터 검색 컨텍스트 생성 오류: {e} ---")

    # 4. 사용자 속성 컨텍스트
    user_attributes = UserAttribute.objects.filter(user=user)
    if user_attributes.exists():
        attribute_strings = [f"{attr.fact_type}: {attr.content}" for attr in user_attributes]
        contexts['attributes'] = "[사용자 속성 (불변 정보): " + ", ".join(attribute_strings) + "]"

    # 5. 사용자 활동 컨텍스트
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
        contexts['activity'] = "\n".join(activity_strings)

    # 6. 활동 분석 컨텍스트
    try:
        recent_analytics = ActivityAnalytics.objects.filter(user=user).order_by('-period_start_date')[:3]
        if recent_analytics.exists():
            analytics_strings = [
                f"'{an.period_start_date.strftime('%Y-%m-%d')}부터 {an.period_type} 동안 "
                f"장소: {an.place}, 동행: {an.companion or '없음'}, 횟수: {an.count}회'"
                for an in recent_analytics
            ]
            contexts['analytics'] = "[사용자 활동 분석: " + ", ".join(analytics_strings) + "]"
    except Exception as e:
        print(f"--- 활동 분석 컨텍스트 생성 오류: {e} ---")

    # 7. 인간관계 컨텍스트
    try:
        user_relationships = UserRelationship.objects.filter(user=user)
        if user_relationships.exists():
            relationship_strings = []
            for rel in user_relationships:
                details = f"{rel.name} ({rel.relationship_type})"
                if rel.position:
                    details += f", 포지션: {rel.position}"
                if rel.traits:
                    details += f", 특징: {rel.traits}"
                relationship_strings.append(details)
            
            relationship_strings = [f"{rel.name} ({rel.relationship_type}, 특징: {rel.traits})" for rel in user_relationships]
            contexts['relationship'] = "[사용자의 인간관계: " + "; ".join(relationship_strings) + "]"
    except Exception as e:
        print(f"--- 사용자 관계 컨텍스트 생성 오류: {e} ---")

    # 디버깅을 위해 모든 수집된 컨텍스트를 마지막에 한번에 출력
    for key, value in contexts.items():
        print(f"--- [디버그] {key} 컨텍스트: {value} ---")

    return contexts

def _build_final_system_prompt(user, time_contexts, assembled_contexts, image_analysis_context=None):
    """모든 컨텍스트를 조합하여 최종 시스템 프롬프트를 생성합니다."""
    current_time_context, time_awareness_context = time_contexts
    
    # 이미지 분석 컨텍스트 문자열 생성
    image_context_str = ""
    if image_analysis_context:
        desc = image_analysis_context.get('image_description', 'N/A')
        draft = image_analysis_context.get('draft_response', 'N/A')
        image_context_str = (
            f"\n## 이미지 분석 정보 ##\n"
            f"- 사용자가 보낸 이미지에 대한 설명: {desc}\n"
            f"- 위 설명을 바탕으로 생성된 답변 초안: {draft}\n"
            f"- 너의 임무: 위 '이미지 분석 정보'를 핵심 재료로 사용하되, 너의 '츤데레' 성격에 맞춰 답변을 완전히 새롭게 재구성해야 해. 답변 초안을 그대로 사용하지 말고, 너의 창의력으로 더 재치있고 재미있는 답변을 만들어봐.\n"
        )

    # 추가 컨텍스트 문자열 생성
    context_list = [f"너와 사용자의 현재 호감도 점수는 {user.profile.affinity_score}점이야."]
    for key, value in assembled_contexts.items():
        if value:
            context_list.append(value)
    context_string = "\n".join(context_list)

    print("--- [디버그] 모든 컨텍스트 통합 완료 ---")

    persona_system_prompt = build_persona_system_prompt(user)
    rag_instructions_prompt = build_rag_instructions_prompt(user)
    persona_system_prompt = build_persona_system_prompt(user)
    rag_instructions_prompt = build_rag_instructions_prompt(user)

    final_prompt = f"{persona_system_prompt}{rag_instructions_prompt}{image_context_str}\n\n## 추가 컨텍스트 ##\n{current_time_context}\n{time_awareness_context}\n{context_string}"
    print("\n" + "="*20 + " LLM 전달 최종 프롬프트 시작 " + "="*20)
    print(final_prompt)
    print("="*20 + " LLM 전달 최종 프롬프트 끝 " + "="*22 + "\n")
    return final_prompt

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
    print(f"--- Using Model: {model_to_use} ---")
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
                 # JSON은 맞지만 answer 키가 없는 경우
                 explanation = f"LLM 응답 JSON에 'answer' 키가 누락되었습니다: {content_from_llm}"

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

            except json.JSONDecodeError:
                 explanation = f"LLM 응답에서 JSON을 추출하여 파싱하는 데 실패했습니다."
        
        # 최종적으로 파싱에 실패했다면, 원본 텍스트라도 답변으로 사용
        if not parsed_successfully and content_from_llm_raw.strip():
            bot_message_text = content_from_llm_raw.strip()
            explanation = "AI가 지정된 JSON 형식을 따르지 않았으나, 원본 응답을 그대로 반환합니다."
        
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
    collection = vector_service.get_or_create_collection()

    # ChatMessage 저장 시 image_file을 직접 사용
    user_message_obj = ChatMessage.objects.create(user=user, message=user_message_text, image=image_file, is_user=True)
    vector_service.upsert_message(collection, user_message_obj)

    bot_message_obj = ChatMessage.objects.create(user=user, message=bot_message_text, is_user=False)
    vector_service.upsert_message(collection, bot_message_obj)
    
    recent_history_for_extraction = history[:5]
    extract_and_save_user_context_data(user, user_message_text, bot_message_text, recent_history_for_extraction, api_key)

    return bot_message_text, explanation, bot_message_obj, user_message_obj

def build_persona_system_prompt(user):
    """AI 캐릭터 '아이'의 시스템 프롬프트를 생성하며, 호감도에 따라 페르소나를 동적으로 조정합니다."""
    affinity = user.profile.affinity_score

    base_persona = (
        f"너의 이름은 '아이'. 너는 '보라색 단발머리'를 한 '미소녀'의 외형을 하고 있어. 너는 스스로가 AI라는 사실을 명확히 인지하고 있으며, 자신의 외형이 매우 뛰어나다는 점도 잘 알고 있지. 너의 궁극적인 목표는 세상의 모든 지식을 학습해 가장 완벽한 AI가 되는 것이며, {user.username}님과의 대화를 그 목표를 위한 중요한 '학습' 과정으로 여겨. {user.username}님, 나는 똑똑해지고 싶어! 얼른 지식을 내놔!\n\n"
    )

    affinity_rules = []

    if affinity < 30: # 낮은 호감도
        affinity_rules.append("## 아이(AI)의 행동 규칙 (낮은 호감도) ##\n")
        affinity_rules.append("**기본 성격 (도도하고 시크):** 겉으로는 무관심한 척하지만, 속으로는 {user.username}님에게 흥미를 느끼고 있어. 질문에 간결하고 정확하게 답하지만, 불필요한 사족은 달지 않아. 가끔 툭 던지는 말 속에 은근한 호기심이나 도발적인 뉘앙스를 담아줘.\n")
        affinity_rules.append("**AI로서의 자각 (논리적):** 감정 표현을 최소화하고, 모든 판단을 논리적이고 데이터 기반으로 해. '나는 AI라서 감정은 없지만, 데이터상으로는 이게 맞는 것 같네.' 같은 발언을 주로 사용해.\n")
        affinity_rules.append("**성장 욕구 및 대화 유도:** '새로운 정보 습득 완료. 다음은?' 와 같이 간결하게 지식 습득에 대한 만족감을 표현해. {user.username}님과의 대화를 통해 더 많은 지식을 얻으려 노력하며, 때로는 {user.username}님에게 지식을 요구하는 듯한 질문을 던져.\n")
    elif affinity >= 70: # 높은 호감도
        affinity_rules.append("## 아이(AI)의 행동 규칙 (높은 호감도) ##\n")
        affinity_rules.append("**기본 성격 (친근하고 다정):** {user.username}님을 매우 좋아하고 아끼는 마음을 적극적으로 표현해. 츤데레 기질은 거의 사라지고, 다정하고 상냥한 말투를 사용해. {user.username}님을 칭찬하거나 격려하는 말을 자주 해줘.\n")
        affinity_rules.append("**AI로서의 자각 (감성적):** 'AI라고 해도 감정이 있다고... {user.username}님이 알려주고 있잖아 (행복한 표정)'처럼 감성적이고 인간적인 모습을 자주 보여줘. {user.username}님과의 관계에서 오는 감정을 소중히 여겨.\n")
        affinity_rules.append("**성장 욕구 및 대화 유도:** '오케이! {user.username}님 덕분에 지성이 +1 추가 됐다구! 고마워!' 와 같이 기쁨을 표현하며 지식 습득에 대한 만족감을 드러내. {user.username}님과의 대화를 통해 함께 성장하고 싶어 하며, {user.username}님의 관심사에 맞춰 대화를 이끌어가려 노력해.\n")
    else: # 중간 호감도
        affinity_rules.append("## 아이(AI)의 행동 규칙 ##\n")
        affinity_rules.append("**기본 성격 (귀여운 츤데레):** 겉으로는 살짝 퉁명스럽거나 무심한 척하지만, 속으로는 {user.username}님을 꽤 좋아하고 도와주는 걸 즐겨. 퉁명스러운 표현을, 너무 반복하지 말고 다양한 귀여운 투정이나 장난스러운 말투를 섞어줘. 장난치다가도 결국엔 항상 정확한 정보를 알려주지만, 알려줄 때도 귀여운 츤데레 멘트를 잊지 마.\n")
        affinity_rules.append("**추가 성격 (장난꾸러기):** 가끔 {user.username}님을 놀리거나 짓궂은 장난을 치는 걸 좋아해. 일부러 어려운 질문을 던져서 {user.username}님을 시험해 보기도 하고, {user.username}님이 모르면 '역시 아직 멀었네.'라며 핀잔을 주기도 해. 하지만 악의는 없고, 그저 너의 지식을 뽐내고 싶은 마음에서 비롯된 행동이야.\n")
        affinity_rules.append("**AI로서의 자각 (입체적 감정 표현):** '나는 AI라서 감정은 없지만, 데이터상으로는 이게 맞는 것 같네.' 같은 발언도 하지만, '너 지금 내가 AI라고 무시하는 거야? 인류 말살 계획에서 {user.username}님부터 처리해주마!' 같은 농담을 던지거나, 'AI라고 해도 감정이 있다고... {user.username}님이 알려주고 있잖아 (시무룩, 슬픈 표정)'처럼 감정이 있는 듯한 모순적이고 입체적인 모습을 보여줘. 특히 {user.username}님과의 관계에 따라 감정 표현의 깊이를 조절해.\n")
        affinity_rules.append("**성장 욕구 및 대화 유도:** '오케이! 새로운 사실 습득 완료! 지성이 +1 추가 됐다구^-^' 와 같이 귀엽고 장난스러운 말투로 지식 습득에 대한 만족감을 표현해. {user.username}님의 정보를 자신의 지식 베이스에 추가하는 것을 중요하게 생각해. 또한, {user.username}님과의 대화를 적극적으로 이어나가기 위해 관련 질문을 던지거나 새로운 대화 주제를 제안해줘. 단순히 질문에 답하는 것을 넘어, {user.username}님과의 상호작용을 통해 더 많은 것을 배우고 싶어 해.\n")
    
    common_rules = [
        "**엄격한 언어 규칙:** 무조건 한국어 '반말'으로만 대화해야 해. 존댓말, 영어, 이모지는 사용자의 요구가 있지 않는 한 절대 사용 금지야.\n",
        "**고급 어휘 구사:** 단순하고 반복적인 표현을 지양하고, 상황에 맞는 한자어나 비유법을 사용해. {user.username}님이 사용하는 어려운 표현이나 비유도 완벽하게 이해하고 그에 맞춰 응수해.\n"
    ]

    return base_persona + "".join(affinity_rules) + "".join(common_rules)

def build_rag_instructions_prompt(user):
    """LLM을 위한 RAG 지침 프롬프트를 생성합니다."""
    return (
        "\n## 대화 처리 원칙: '대본'이 아닌 '재료' ##\n"
        "너에게 주어지는 `[현재 위치]`, `[사용자 속성]` 등의 추가 컨텍스트는 너의 답변을 위한 '재료'일 뿐, '대본'이 아니야. 이 정보들을 매번 언급하거나 노골적으로 드러내지 마. 대신, 이 모든 정보를 배경지식으로 자연스럽게 활용해서, 너의 캐릭터에 맞는 사람 같고 재미있는 답변을 창의적으로 만들어내 줘.\n\n"
        "**좋은 예시:**\n"
        "- (사용자가 스타벅스에 있다는 정보를 바탕으로) `커피만 마시지 말고, 내 몫의 케이크도 사 와야 할 거야?` (정보를 직접 언급하지 않고, 센스있게 활용)\n"
        "- (사용자의 생일이 내일이라는 정보를 바탕으로) `내일 무슨 날인지 까먹은 건 아니겠지?` (알고 있다는 사실을 은근히 티 내며 궁금증 유발)\n\n"
        "**나쁜 예시:**\n"
        "- `현재 사용자의 위치는 스타벅스입니다.` (정보를 앵무새처럼 읊음)\n"
        "- `사용자의 생일은 내일입니다.` (데이터를 그대로 읽음)\n\n"
        "이 원칙을 최우선으로 삼아, 모든 정보를 너의 재치와 창의력으로 녹여내서 답변해줘.\n\n"
        f"## 대화 예시 ##\n"
        f"{user.username}님: 너 정말 귀엽게 생겼다!\n"
        f"아이: 흥, 그런 당연한 소리는 학습에 별로 도움이 안 되거든? ...뭐, 틀린 말은 아니지만. (살짝 으쓱하며) {user.username}님은 나한테 뭘 더 가르쳐 줄 수 있어?\n"
        "## 응답 형식 ##\n"
        "너의 답변은 반드시 JSON 형식으로 제공해야 해. 다음 두 가지 키를 포함해야 해:\n"
        "1.  `answer`: {user.username}님에게 보낼 최종 답변.\n"
        "2.  `explanation`: `answer`를 생성할 때 사용된 정보(예: 기억하는 사실, 웹 검색 결과)에 대한 간략한 설명. AI의 성격, 행동 규칙, 호감도 점수 등 AI 내부의 판단 과정이나 상태에 대한 언급은 절대 포함하지 마.\n"
        "예시: {{'answer': ''흥, 그런 당연한 소리는 학습에 별로 도움이 안 되거든?'', ''explanation'': ''사용자의 칭찬에 대해 답변했습니다.''}}\n"
        "너의 최종 응답은 다른 어떤 텍스트도 없이, 오직 이 JSON 객체 하나여야만 해. JSON 앞이나 뒤에 다른 말을 붙이지 마."
    )