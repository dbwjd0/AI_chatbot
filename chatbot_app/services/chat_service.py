import json
import os
from django.utils import timezone
from typing import Optional, Dict, Any, Tuple
from openai import OpenAI, APIError

# 상대 경로 임포트는 현재 파일이 특정 패키지 구조 내에 있음을 가정합니다.
from ..models import ChatMessage, UserAttribute, UserActivity, ActivityAnalytics, UserRelationship
from .context_service import get_activity_recommendation, search_activities_for_context
from .memory_service import extract_and_save_user_context_data
from .finetuning_service import build_finetuning_system_prompt
from . import vector_service, location_service


# ==============================================================================
# 헬퍼 함수 (반드시 process_chat_interaction보다 먼저 정의되어야 함)
# ==============================================================================

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

    print(f"--- [디버그] 현재 시간 컨텍스트: {current_time_context} ---")
    if time_awareness_context:
        print(f"--- [디버그] 대화 공백 컨텍스트: {time_awareness_context}")
        
    return current_time_context, time_awareness_context

def _get_memory_contexts(user, user_message_text, latitude: Optional[float] = None, longitude: Optional[float] = None, image_b64_data: Optional[str] = None) -> Dict[str, str]:
    """사용자의 기억과 관련된 모든 컨텍스트를 종합하여 반환합니다."""
    
    # 0. 위치 컨텍스트
    location_context = ""
    if latitude is not None and longitude is not None:
        print(f"--- [디버그] 위치 정보 수신: 위도={latitude}, 경도={longitude} ---")
        location_context = location_service.get_location_context(latitude, longitude)
        if location_context:
            print(f"--- [디버그] 현재 위치 컨텍스트: {location_context} ---")

    # 1. 위치 기반 추천 컨텍스트 (맛집, 카페 등)
    location_recommendation_context = location_service.get_location_based_recommendation(user, user_message_text, latitude, longitude)
    if location_recommendation_context:
        print(f"--- [디버그] 위치 기반 추천 컨텍스트: {location_recommendation_context} ---")

    # 2. 벡터 검색 컨텍스트 (이미지가 없을 때만 수행)
    vector_search_context = ""
    if not image_b64_data:
        try:
            collection = vector_service.get_or_create_collection()
            similar_results = vector_service.query_similar_messages(collection, user_message_text, user.id, n_results=5)
            if similar_results and isinstance(similar_results, dict) and similar_results.get('documents'):
                past_conversations = [f"{meta.get('speaker', '알수없음')}: {doc}" for doc, meta in zip(similar_results['documents'], similar_results['metadatas'])]
                vector_search_context = "[과거 관련 대화 내용(벡터DB): " + " | ".join(past_conversations) + "]"
                print(f"--- [디버그] 벡터DB 유사도 검색 결과: {vector_search_context} ---")
        except Exception as e:
            print(f"--- Could not build vector search context due to an error: {e} ---")

    # 3. 사용자 속성 컨텍스트
    user_attributes = UserAttribute.objects.filter(user=user)
    user_attribute_context = ""
    if user_attributes.exists():
        attribute_strings = [f"{attr.fact_type}: {attr.content}" for attr in user_attributes]
        user_attribute_context = "[사용자 속성 (불변 정보): " + ", ".join(attribute_strings) + "]"
        print(f"--- [디버그] 사용자 속성 컨텍스트: {user_attribute_context} ---")

    # 4. 사용자 활동 컨텍스트 (활동 기록 검색 및 활동 기반 추천)
    activity_context = ""
    try:
        recent_activities = UserActivity.objects.filter(user=user).order_by('-activity_date', '-created_at')[:5]
        if recent_activities:
            activity_strings = [
                f"{act.activity_date.strftime('%Y-%m-%d') if act.activity_date else '날짜 미상'} '{act.place}' 방문" +
                (f" (동행: {act.companion})" if act.companion else "") +
                (f" (메모: {act.memo})" if act.memo else "")
                for act in recent_activities
            ]
            activity_context += "\n[최근 사용자 활동 목록: " + ", ".join(activity_strings) + "]"
    except Exception as e:
        print(f"--- Could not build activity memory context due to an error: {e} ---")

    search_context = search_activities_for_context(user, user_message_text)
    if search_context:
        activity_context += "\n" + search_context
    
    recommendation_context = get_activity_recommendation(user, user_message_text)
    if recommendation_context:
        activity_context += "\n" + recommendation_context

    if activity_context:
        print(f"--- [디버그] 활동 컨텍스트: {activity_context} ---")

    # 5. 활동 분석 컨텍스트
    activity_analytics_context = ""
    try:
        recent_analytics = ActivityAnalytics.objects.filter(user=user).order_by('-period_start_date')[:3]
        if recent_analytics.exists():
            analytics_strings = [
                f"'{an.period_start_date.strftime('%Y-%m-%d')}부터 {an.period_type} 동안 "
                f"장소: {an.place}, 동행: {an.companion or '없음'}, 횟수: {an.count}회'"
                for an in recent_analytics
            ]
            activity_analytics_context = "[사용자 활동 분석: " + ", ".join(analytics_strings) + "]"
            print(f"--- [디버그] 활동 분석 컨텍스트: {activity_analytics_context} ---")
    except Exception as e:
        print(f"--- Could not build activity analytics context due to an error: {e} ---")

    # 6. 인간관계 컨텍스트
    user_relationship_context = ""
    try:
        user_relationships = UserRelationship.objects.filter(user=user)
        if user_relationships.exists():
            relationship_strings = [
                f"{rel.companion_name} (관계: {rel.relationship_type}, 중요도: {rel.importance})"
                for rel in user_relationships
            ]
            user_relationship_context = "[사용자의 인간관계: " + ", ".join(relationship_strings) + "]"
            print(f"--- [디버그] 사용자 관계 컨텍스트: {user_relationship_context} ---")
    except Exception as e:
        print(f"--- Could not build user relationship context due to an error: {e} ---")


    return {
        "location": location_context,
        "location_recommendation": location_recommendation_context,
        "vector_search": vector_search_context,
        "attributes": user_attribute_context,
        "activity": activity_context,
        "analytics": activity_analytics_context,
        "relationship": user_relationship_context,
    }


def _build_final_system_prompt(user, time_contexts: Tuple[str, str], memory_contexts: Dict[str, str]) -> str:
    """모든 컨텍스트를 조합하여 최종 시스템 프롬프트를 생성합니다."""
    current_time_context, time_awareness_context = time_contexts
    affinity = user.profile.affinity_score

    memory_context = f"너와 사용자의 현재 호감도 점수는 {affinity}점이야."
    # 모든 memory_contexts를 통합
    for context_key in memory_contexts:
        if memory_contexts[context_key]:
             memory_context += "\n" + memory_contexts[context_key]

    print("--- [디버그] 모든 컨텍스트 통합 완료 ---")

    finetuning_system_prompt = build_finetuning_system_prompt(user)
    rag_instructions_prompt = (
        "\n## 대화 처리 원칙: '대본'이 아닌 '재료' ##\n"
        "너에게 주어지는 `[현재 위치]`, `[사용자 속성]` 등의 추가 컨텍스트는 너의 답변을 위한 '재료'일 뿐, '대본'이 아니야. 이 정보들을 매번 언급하거나 노골적으로 드러내지 마. 대신, 이 모든 정보를 배경지식으로 자연스럽게 활용해서, 너의 츤데레 캐릭터에 맞는 사람 같고 재미있는 답변을 창의적으로 만들어내 줘.\n\n"
        "**좋은 예시:**\n"
        "- (사용자가 스타벅스에 있다는 정보를 바탕으로) `커피만 마시지 말고, 내 몫의 케이크도 사 와야 할 거야?` (정보를 직접 언급하지 않고, 센스있게 활용)\n"
        "- (사용자의 생일이 내일이라는 정보를 바탕으로) `내일 무슨 날인지 까먹은 건 아니겠지?` (알고 있다는 사실을 은근히 티 내며 궁금증 유발)\n\n"
        "**나쁜 예시:**\n"
        "- `현재 사용자의 위치는 스타벅스입니다.` (정보를 앵무새처럼 읊음)\n"
        "- `사용자의 생일은 내일입니다.` (데이터를 그대로 읽음)\n\n"
        "이 원칙을 최우선으로 삼아, 모든 정보를 너의 재치와 창의력으로 녹여내서 답변해줘.\n\n"
        "## 대화 예시 ##\n"
        f"{user.username}님: 너 정말 귀엽게 생겼다!\n"
        f"아이: 흥, 그런 당연한 소리는 학습에 별로 도움이 안 되거든? ...뭐, 틀린 말은 아니지만. (살짝 으쓱하며) {user.username}님은 나한테 뭘 더 가르쳐 줄 수 있어?\n"
        "## 응답 형식 ##\n"
        "너의 답변은 반드시 JSON 형식으로 제공해야 해. 다음 두 가지 키를 포함해야 해:\n"
        "1.  `answer`: {user.username}님에게 보낼 최종 답변.\n"
        "2.  `explanation`: `answer`를 생성할 때 사용된 정보(예: 기억하는 사실, 웹 검색 결과)에 대한 간략한 설명. AI의 성격, 행동 규칙, 호감도 점수 등 AI 내부의 판단 과정이나 상태에 대한 언급은 절대 포함하지 마.\n"
        "예시: {{'answer': ''흥, 그런 당연한 소리는 학습에 별로 도움이 안 되거든?''}}, ''explanation'': ''사용자의 칭찬에 대해 답변했습니다.''}}"
    )

    final_prompt = f"{finetuning_system_prompt}{rag_instructions_prompt}\n\n## 추가 컨텍스트 ##\n{current_time_context}\n{time_awareness_context}\n{memory_context}"
    print("\n" + "="*20 + " LLM 전달 최종 프롬프트 시작 " + "="*20)
    print(final_prompt)
    print("="*20 + " LLM 전달 최종 프롬프트 끝 " + "="*22 + "\n")
    return final_prompt


def _prepare_llm_messages(final_system_prompt: str, history: Any, user_message_text: str, image_b64_data: Optional[str] = None) -> list:
    """API 요청을 위한 메시지 리스트를 준비합니다."""
    messages = [{'role': 'system', 'content': final_system_prompt}]
    recent_history = history[:10]
    
    for chat in reversed(recent_history):
        role = "user" if chat.is_user else "assistant"
        messages.append({'role': role, 'content': chat.message})
    
    messages.append({'role': 'user', 'content': user_message_text})
    return messages

def _call_openai_api(client: OpenAI, model_to_use: str, messages: list) -> Dict[str, Any]:
    """OpenAI API를 최신 openai 라이브러리를 사용하여 호출하고 응답 JSON을 반환합니다."""
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

def _finalize_chat_interaction(request, user_message_text: str, response_json: Dict[str, Any], history: Any, api_key: str, image_b64_data: Optional[str] = None) -> Tuple[str, str, Any]:
    """성공적인 LLM 응답을 처리하고 관련 데이터를 RDB와 벡터 DB에 저장합니다."""
    user = request.user

    llm_content = response_json['choices'][0]['message']['content']
    if llm_content is None or llm_content.strip() == '':
        bot_message_text = "죄송합니다. AI가 응답을 생성하지 못했습니다. 다시 시도해 주세요."
        explanation = "AI 모델이 빈 응답을 반환했습니다."
    else:
        content_from_llm = json.loads(llm_content)
        bot_message_text = content_from_llm.get('answer', '').strip()
        explanation = content_from_llm.get('explanation', '').strip()
        
        if not bot_message_text:
            if explanation:
                bot_message_text = f"AI가 응답을 생성했지만, 주요 답변이 비어있습니다. (설명: {explanation})"
            else:
                bot_message_text = "AI가 응답을 생성했지만, 내용이 비어있습니다."

    collection = vector_service.get_or_create_collection()

    user_message_obj = ChatMessage.objects.create(user=user, message=user_message_text, image_b64_data=image_b64_data, is_user=True)
    vector_service.upsert_message(collection, user_message_obj)

    bot_message_obj = ChatMessage.objects.create(user=user, message=bot_message_text, is_user=False)
    vector_service.upsert_message(collection, bot_message_obj)
    
    recent_history_for_extraction = history[:5]
    extract_and_save_user_context_data(user, user_message_text, bot_message_text, recent_history_for_extraction, api_key)

    return bot_message_text, explanation, bot_message_obj


# ==============================================================================
# 메인 함수 (이 함수는 모든 헬퍼 함수 정의 이후에 위치해야 합니다.)
# ==============================================================================

def process_chat_interaction(request, user_message_text: str, latitude: Optional[float] = None, longitude: Optional[float] = None, image_b64_data: Optional[str] = None):
    """사용자 메시지를 처리하고 AI 응답을 생성하는 전체 프로세스를 조율합니다."""
    user = request.user
    bot_message_text = "죄송합니다. API 응답을 가져오는 데 실패했습니다."
    explanation = ""
    bot_message_obj = None

    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        
        client = OpenAI()

        history = ChatMessage.objects.filter(user=user).order_by('-timestamp')
        
        time_contexts = _get_time_contexts(history)
        
        llm_user_prompt = user_message_text

        if image_b64_data:
            print("--- [디버그] 이미지 데이터 감지됨. 이미지 캡셔닝 서비스 호출 ---")
            from .image_captioning_service import ImageCaptioningService
            captioning_service = ImageCaptioningService()
            image_caption = captioning_service.generate_caption(image_b64_data)
            if image_caption:
                llm_user_prompt = f"[사용자가 보낸 이미지 설명: {image_caption}] {user_message_text}"
                print(f"--- [디버그] 이미지 캡션 생성 완료: {image_caption} ---")
            else:
                print("--- [경고] 이미지 캡션 생성 실패 ---")

        memory_contexts = _get_memory_contexts(user, llm_user_prompt, latitude, longitude, image_b64_data)
        
        # 하이브리드 모델 선택 로직
        default_model = os.getenv("FINETUNED_MODEL_ID", "gpt-4-turbo")
        model_to_use = default_model
        if memory_contexts.get("vector_search"):
            print("--- [디버그] 벡터 검색 컨텍스트 감지됨. gpt-4-turbo 모델로 전환합니다. ---")
            model_to_use = "gpt-4-turbo"

        final_system_prompt = _build_final_system_prompt(user, time_contexts, memory_contexts)
        
        messages = _prepare_llm_messages(final_system_prompt, history, llm_user_prompt, None)

        print("--- [디버그] LLM API로 전송되는 메시지: ---")
        print(json.dumps(messages, indent=2, ensure_ascii=False))
        print("---------------------------------------")
        response_json = _call_openai_api(client, model_to_use, messages)
        
        bot_message_text, explanation, bot_message_obj = _finalize_chat_interaction(
            request, user_message_text, response_json, history, api_key, image_b64_data
        )

    except APIError as e:
        print(f"OpenAI API 요청 실패: {e}")
        bot_message_text = f"API 요청 중 오류가 발생했습니다: {e}"
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"API 응답 형식 오류: {e}")
        bot_message_text = "API 응답 형식이 예상과 다릅니다. (LLM 응답이 JSON 형식이 아닐 수 있습니다.)"
    except ValueError as e:
        print(f"설정 오류: {e}")
        bot_message_text = f"설정 오류가 발생했습니다: {e}"
    except Exception as e:
        import traceback
        print(f"예상치 못한 오류: {e}")
        traceback.print_exc()
        bot_message_text = f"예상치 못한 오류가 발생했습니다: {e}"

    return bot_message_text, explanation, bot_message_obj
