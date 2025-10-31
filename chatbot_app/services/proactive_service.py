from ..models import ChatMessage, UserProfile, PendingProactiveMessage
from django.utils import timezone
from datetime import timedelta, datetime, date, time
import os
import requests
import json
import re
from .chat_service import _assemble_context_data # 필요한 함수 임포트
from .prompt_service import build_persona_system_prompt, build_rag_instructions_prompt
from .emotion_service import analyze_emotion
from . import schedule_service # schedule_service 임포트
from .rl_agent_service import decide_action # RL 에이전트의 decide_action 함수 임포트

def _check_upcoming_schedule(user):
    today = date.today()
    schedules = schedule_service.get_schedules_for_day(user, today)
    now_korea = timezone.now().astimezone(timezone.get_default_timezone())

    for schedule in schedules:
        if schedule.schedule_time and schedule.content:
            # 오늘 날짜와 스케줄 시간을 결합하여 datetime 객체 생성
            schedule_datetime = datetime.combine(today, schedule.schedule_time)
            schedule_datetime = timezone.make_aware(schedule_datetime, timezone.get_default_timezone())

            time_until_schedule = schedule_datetime - now_korea

            # 스케줄이 10분 이내로 다가왔고 과거가 아닌지 확인
            if timedelta(minutes=0) < time_until_schedule <= timedelta(minutes=10):
                return schedule.content # 가장 빨리 다가오는 스케줄 내용 반환
    return None

def _call_llm_for_proactive_message(user, system_prompt):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("오류: OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        return None, None

    model_to_use = os.getenv("FINETUNED_MODEL_ID", "gpt-4.1")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': f"{user.username}님에게 능동적인 대화를 시작할 메시지를 생성해줘."}
    ]

    data = {
        "model": model_to_use,
        "messages": messages,
        "temperature": 0.7,
        "top_p": 0.9,
        "frequency_penalty": 0.2,
        "presence_penalty": 0.1,
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
        response.raise_for_status()
        response_json = response.json()
        
        content_from_llm = json.loads(response_json['choices'][0]['message']['content'])
        message_text = content_from_llm.get('answer', '').strip()
        explanation = content_from_llm.get('explanation', '설명 없음.') # Extract explanation
        emotion = analyze_emotion(message_text, speaker="Bot") # emotion_service를 사용하여 감정 분석 

        print("\n" + "-"*20 + " [Debug] Proactive Message Explanation " + "-"*20)
        print(explanation)
        print("-"*66 + "\n")

        return message_text, emotion, explanation # Return explanation
    except (requests.exceptions.RequestException, KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"LLM 능동적 메시지 생성 오류: {e}")
        return None, None, None # Return None for explanation on error


def generate_proactive_message(user):
    last_chat = ChatMessage.objects.filter(user=user).order_by('-timestamp').first()
    korea_tz = timezone.get_default_timezone()
    now_korea = timezone.now().astimezone(korea_tz)
    
    trigger_type = None
    proactive_instruction_base = ""
    message_text = None
    emotion = "default"

    # 1. 비활동 기반 트리거
    if last_chat and (now_korea - last_chat.timestamp.astimezone(korea_tz)) > timedelta(hours=1):
        trigger_type = "inactivity"
        proactive_instruction_base = f"너는 {user.username}님에게 오랜만에 말을 거는 상황이야. 1시간 이상 대화가 없었으니, {user.username}님의 안부를 묻거나, "
    
    # 2. 시간대 기반 트리거
    elif not last_chat or (now_korea - last_chat.timestamp.astimezone(korea_tz)) > timedelta(minutes=30):
        current_hour = now_korea.hour
        if 6 <= current_hour < 10:
            trigger_type = "morning_greeting"
            proactive_instruction_base = f"좋은 아침이야, {user.username}! 오늘 하루를 활기차게 시작할 수 있도록 응원하는 메시지를 생성해줘. "
        elif 12 <= current_hour < 14:
            trigger_type = "lunch_time"
            proactive_instruction_base = f"{user.username}님, 점심시간이야! 맛있는 점심을 추천하거나, 점심 관련 가벼운 대화를 시작하는 메시지를 생성해줘. "
        elif 18 <= current_hour < 22:
            trigger_type = "evening_greeting"
            proactive_instruction_base = f"{user.username}님, 저녁 시간이야! 오늘 하루는 어땠는지 묻거나, 편안한 저녁을 보낼 수 있도록 격려하는 메시지를 생성해줘. "

    # 3. 일정 알림 트리거
    upcoming_schedule_content = _check_upcoming_schedule(user)
    if upcoming_schedule_content:
        trigger_type = "upcoming_schedule"
        proactive_instruction_base = f"{user.username}님, 곧 일정이 있어! '{upcoming_schedule_content}' 일정이 10분 이내로 다가왔으니, 일정을 상기시켜주거나, 준비를 돕는 메시지를 생성해줘. "

    if trigger_type:
        # RL 에이전트에게 액션 결정 요청
        # 능동적 메시지이므로 user_message_text는 트리거에 따른 설명을 제공
        # history는 모든 채팅 기록을 넘겨주어 RL 에이전트가 판단할 수 있도록 함
        all_chat_history = ChatMessage.objects.filter(user=user).order_by('-timestamp')
        
        # proactive_instruction_base를 user_message_text로 활용하여 RL 에이전트가 현재 상황을 인지하도록 함
        rl_action = decide_action(user, proactive_instruction_base, all_chat_history, has_image=False, user_emotion="중립")
        
        persona_prompt = rl_action['persona_prompt']
        contexts_to_use = rl_action['contexts_to_use']

        # RL 에이전트가 결정한 컨텍스트를 기반으로 데이터 조립
        assembled_contexts_dict = _assemble_context_data(user, "", contexts_to_use)
        assembled_contexts_str = "\n".join([f"[{key.replace('_', ' ').capitalize()}]: {value}" for key, value in assembled_contexts_dict.items() if value])
        if assembled_contexts_str:
            assembled_contexts_str = "\n## 사용자 기억 컨텍스트 ##\n" + assembled_contexts_str
        
        rag_instructions_prompt = build_rag_instructions_prompt(user) # RAG 지침은 항상 포함

        proactive_instruction = f"{proactive_instruction_base}제공된 사용자 정보와 기억 컨텍스트를 적극적으로 활용하여 메시지를 생성해줘. 너의 페르소나에 맞게 재치있고 흥미롭게 말을 걸어줘. 응답은 반드시 JSON 형식으로 'answer' 키와 'explanation' 키를 포함해야 해."
        system_prompt = f"{persona_prompt}{rag_instructions_prompt}{assembled_contexts_str}\n\n## 능동적 대화 지시 ##\n{proactive_instruction}"
        
        message_text, emotion, explanation = _call_llm_for_proactive_message(user, system_prompt)

        # LLM 호출 실패 시 기본 메시지 설정
        if not message_text:
            emotion = "default"
            if trigger_type == "inactivity":
                message_text = "오랜만이야! 뭐 하고 지냈어?"
            elif trigger_type == "morning_greeting":
                message_text = "좋은 아침이야!"
                emotion = "happy"
            elif trigger_type == "lunch_time":
                message_text = "점심시간이야! 뭐 먹을지 고민돼?"
                emotion = "thinking"
            elif trigger_type == "evening_greeting":
                message_text = "오늘 하루도 수고했어!"
            elif trigger_type == "upcoming_schedule":
                message_text = f"곧 '{upcoming_schedule_content}' 일정이 있어! 준비는 잘 되고 있어?"

    if message_text:
        # ChatMessage 객체 생성 및 저장
        proactive_chat_message = ChatMessage.objects.create(
            user=user,
            message=message_text,
            is_user=False,
            character_emotion=emotion
        )
        
        # 벡터 DB에 저장
        try:
            from . import vector_service
            collection = vector_service.get_or_create_collection()
            vector_service.upsert_message(collection, proactive_chat_message)
            print("--- [디버그] 능동 메시지 벡터 DB 저장 완료 ---")
        except Exception as e:
            print(f"--- [오류] 능동 메시지 벡터 DB 저장 실패: {e} ---")

        # 읽지 않은 메시지로 등록
        PendingProactiveMessage.objects.update_or_create(
            user=user,
            defaults={'message': proactive_chat_message}
        )
        print(f"--- [디버그] {user.username}님에게 읽지 않은 능동 메시지 등록 완료 ---")
            
        return proactive_chat_message

    return None # 능동적인 메시지가 생성되지 않음
