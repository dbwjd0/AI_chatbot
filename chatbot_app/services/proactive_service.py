from ..models import ChatMessage, UserProfile
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

def _check_upcoming_schedule(user):
    today = date.today()
    schedule = schedule_service.get_or_create_schedule(user, today)

    if schedule.schedule_time and schedule.content:
        now_korea = timezone.now().astimezone(timezone.get_default_timezone())
        
        # Combine today's date with schedule_time to create a datetime object
        schedule_datetime = datetime.combine(today, schedule.schedule_time)
        schedule_datetime = timezone.make_aware(schedule_datetime, timezone.get_default_timezone())

        time_until_schedule = schedule_datetime - now_korea

        # Check if the schedule is within the next 10 minutes and not in the past
        if timedelta(minutes=0) < time_until_schedule <= timedelta(minutes=5):
            return schedule.content
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
        emotion = analyze_emotion(message_text) # emotion_service를 사용하여 감정 분석 
        return message_text, emotion
    except (requests.exceptions.RequestException, KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"LLM 능동적 메시지 생성 오류: {e}")
        return None, None


def generate_proactive_message(user):
    last_chat = ChatMessage.objects.filter(user=user).order_by('-timestamp').first()
    korea_tz = timezone.get_default_timezone()
    now_korea = timezone.now().astimezone(korea_tz)
    
    trigger_type = None
    proactive_instruction_base = ""

    # 1. 비활동 기반 트리거
    # 1시간 이상 활동이 없으면 능동적인 메시지 생성
    if last_chat and (now_korea - last_chat.timestamp.astimezone(now_korea.tzinfo)) > timedelta(hours=1):
        trigger_type = "inactivity"
        proactive_instruction_base = (
            f"너는 {user.username}님에게 오랜만에 말을 거는 상황이야. "
            f"1시간 이상 대화가 없었으니, {user.username}님의 안부를 묻거나, "
        )
    # 2. 시간대 기반 트리거 (30분 이상 비활동 시 고려)
    elif not last_chat or (now_korea - last_chat.timestamp.astimezone(now_korea.tzinfo)) > timedelta(minutes=30):
        current_hour = now_korea.hour
        if 6 <= current_hour < 10: # 아침
            trigger_type = "morning_greeting"
            proactive_instruction_base = f"좋은 아침이야, {user.username}! 오늘 하루를 활기차게 시작할 수 있도록 응원하는 메시지를 생성해줘. "
        elif 12 <= current_hour < 14: # 점심
            trigger_type = "lunch_time"
            proactive_instruction_base = f"{user.username}님, 점심시간이야! 맛있는 점심을 추천하거나, 점심 관련 가벼운 대화를 시작하는 메시지를 생성해줘. "
        elif 18 <= current_hour < 22: # 저녁
            trigger_type = "evening_greeting"
            proactive_instruction_base = f"{user.username}님, 저녁 시간이야! 오늘 하루는 어땠는지 묻거나, 편안한 저녁을 보낼 수 있도록 격려하는 메시지를 생성해줘. "
        # TODO: 다른 시간대 (새벽, 오후 등) 추가 가능

    # 3. 일정 알림 트리거 (새로 추가)
    upcoming_schedule_content = _check_upcoming_schedule(user)
    if upcoming_schedule_content:
        trigger_type = "upcoming_schedule"
        proactive_instruction_base = (
            f"{user.username}님, 곧 일정이 있어! {upcoming_schedule_content} 일정이 10분 이내로 다가왔으니, "
            f"일정을 상기시켜주거나, 준비를 돕는 메시지를 생성해줘. "
        )
    
    # 4. 컨텍스트 기반 트리거 강화 (기존 로직에 통합)
    # LLM 호출 전에 system_prompt에 assemble_context를 추가하는 방식으로 이미 강화되어 있음.
    # proactive_instruction_base에 컨텍스트 활용 지시를 더 명확히 추가.
    
    if trigger_type:
        persona_system_prompt = build_persona_system_prompt(user)
        rag_instructions_prompt = build_rag_instructions_prompt(user)

        memory_contexts_dict = _assemble_context_data(user, "")
        memory_context_str = ""
        for key, value in memory_contexts_dict.items():
            if value:
                memory_context_str += f"[{key.replace('_', ' ').capitalize()}]: {value}\n"
        if memory_context_str:
            memory_context_str = "\n## 사용자 기억 컨텍스트 ##\n" + memory_context_str
        
        # 능동적 메시지 생성을 위한 추가 지시사항
        proactive_instruction = f"{proactive_instruction_base}제공된 사용자 정보와 기억 컨텍스트를 적극적으로 활용하여 메시지를 생성해줘. 너의 페르소나에 맞게 재치있고 흥미롭게 말을 걸어줘. 응답은 반드시 JSON 형식으로 'answer' 키를 포함해야 해."
        
        system_prompt = f"{persona_system_prompt}{rag_instructions_prompt}{memory_context_str}\n\n## 능동적 대화 지시 ##\n{proactive_instruction}"
        
        message_text, emotion = _call_llm_for_proactive_message(user, system_prompt)
        if message_text:
            return message_text, emotion
        else:
            # LLM 호출 실패 시 기본 메시지
            # 각 트리거 타입별 기본 메시지를 다르게 설정할 수도 있음
            if trigger_type == "inactivity":
                return "오랜만이야! 뭐 하고 지냈어?", "default"
            elif trigger_type == "morning_greeting":
                return "좋은 아침이야!", "happy"
            elif trigger_type == "lunch_time":
                return "점심시간이야! 뭐 먹을지 고민돼?", "thinking"
            elif trigger_type == "evening_greeting":
                return "오늘 하루도 수고했어!", "default"
            elif trigger_type == "upcoming_schedule": # Add default message for upcoming schedule
                return f"곧 {upcoming_schedule_content} 일정이 있어! 준비는 잘 되고 있어?", "default"
            else:
                return "무슨 일이야?", "default"

    return None, None # 능동적인 메시지가 필요하지 않음
