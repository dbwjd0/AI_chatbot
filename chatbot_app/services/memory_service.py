import json
import requests
from datetime import datetime, timedelta, date
from django.utils import timezone
from ..models import UserAttribute, UserActivity, UserRelationship, UserSchedule
from . import schedule_service

def extract_and_save_user_context_data(user, user_message, bot_message, recent_history, api_key):
    """
    대화 내용을 한 번의 API 호출로 분석하여 사용자 속성, 활동, 인간관계를 추출하고 저장합니다.
    """
    try:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        today_str = timezone.now().astimezone(timezone.get_default_timezone()).strftime('%Y-%m-%d')

        # 1. 각 정보 유형에 대한 컨텍스트 준비
        existing_attributes_context = _get_existing_attributes_context(user)
        conversation_history_context = _get_conversation_history_context(recent_history)
        existing_relationships_context = _get_existing_relationships_context(user)

        # 2. 통합 프롬프트 생성
        extraction_prompt = f"""당신은 사용자 대화를 분석하여 네 가지 유형의 정보(사용자 속성, 활동, 인간관계, 일정)를 추출하는 고도로 지능적인 AI입니다.
        
        --- 현재 대화 ---
        사용자: {user_message}
        AI: {bot_message}
        {conversation_history_context}---
        
        **[추출 작업]**
        다음 네 가지 정보 유형에 대해 주어진 규칙에 따라 정보를 추출하고, 하나의 JSON 객체로 반환하세요.
        
        **1. 사용자 속성 (User Attributes) 추출**
        - **설명**: 이름, 성격, 생일, MBTI 등 거의 변하지 않는 사용자의 핵심 정보입니다.
        - **컨텍스트**:
        {existing_attributes_context}
        - **규칙**:
            1. **사용자 본인 정보만**: 사용자 자신의 고유 정보만 추출합니다.
            2. **타인 정보 제외**: '가족', '친구' 등 다른 사람 정보는 절대 포함하지 마세요.
            3. **신규 사실**: 기존에 없던 정보는 `action: "create"`로 설정합니다.
            4. **업데이트/구체화**: 기존 사실을 수정/구체화하는 경우 `action: "update"`로 설정하고, **기존 내용을 포함한 완전한 정보**를 `content`에 담아주세요.
            5. **중복/불필요 정보 무시**: 이미 기억된 내용, 단기 기억(예: 어제 점심)은 무시합니다.
        - **JSON 형식**: `{{"action": "create" | "update", "fact_type": "유형", "content": "내용"}}`
        
        **2. 활동 (Activity) 추출**
        - **설명**: 사용자의 과거 활동이나 경험에 대한 보고입니다.
        - **규칙**:
            1. **활동 보고만**: 메시지가 사용자의 과거 활동/경험 보고일 경우에만 추출합니다. (단순 질문, 명령어, 미래 계획 등은 제외)
            2. **날짜**: 날짜가 명시되지 않으면 오늘 날짜인 '{today_str}'를 사용합니다.
            3. **정보 식별**: 시간, 장소, 동행인, 메모 중 하나라도 식별될 경우에만 추출합니다.
        - **JSON 형식**: `{{"activity_date": "YYYY-MM-DD", "activity_time": "HH:MM", "place": "장소", "companion": "동행인", "memo": "활동 요약"}}`
        
        **3. 인간관계 (Relationships) 추출**
        - **설명**: 대화에서 언급된 인물 정보입니다.
        - **컨텍스트**:
        {existing_relationships_context}
        - **규칙**:
            1. **인물만 추출**: 'AI', '챗봇' 등 사람이 아닌 대상은 제외합니다.
            2. **별명/애칭 처리**: 언급된 이름이 '현재 저장된 인물 목록'에 있는 사람의 별명으로 보이면, `name`은 반드시 목록의 **원래 이름**으로 사용합니다. (예: 민이 -> 석민)
            3. **정보 통합**: 새로운 특징이 언급되면 `traits`에 추가합니다.
        - **JSON 형식**: `{{"name": "원래 이름", "relationship_type": "관계 유형", "traits": "새로운 특징"}}`
        
        **4. 일정 (Schedule) 추출**
        - **설명**: 사용자가 특정 날짜와 시간에 수행할 예정인 계획이나 약속입니다.
        - **규칙**:
            1. **미래 또는 오늘 일정만**: 과거 일정은 추출하지 않습니다.
            2. **날짜**: 날짜가 명시되지 않으면 오늘 날짜인 '{today_str}'를 사용합니다.
            3. **시간**: 시간이 명시되지 않으면 `null`로 설정합니다.
            4. **내용**: 일정을 명확히 설명하는 내용만 추출합니다.
        - **JSON 형식**: `{{"schedule_date": "YYYY-MM-DD", "schedule_time": "HH:MM" | null, "content": "일정 내용"}}`
        
        **[최종 반환 형식]**
        - 반드시 다음 네 개의 키를 가진 단일 JSON 객체로 반환하세요: `user_attributes`, `activity`, `relationships`, `schedule`.
        - 각 키의 값은 위에서 정의한 JSON 형식의 리스트 또는 객체입니다.
        - 추출할 정보가 없는 키는 빈 리스트 `[]` 또는 `null`을 값으로 가집니다.
        - 예시:
          `{{
            "user_attributes": [{{"action": "update", "fact_type": "성격", "content": "똑똑하고 장난기 많음"}}],
            "activity": {{"activity_date": "{today_str}", "place": "강남역", "memo": "친구와 저녁 식사"}},
            "relationships": [{{"name": "석민", "relationship_type": "소꿉친구", "traits": "치위생사 준비중"}}],
            "schedule": [{{"schedule_date": "{today_str}", "schedule_time": "15:00", "content": "팀 회의"}}]
          }}`
        """
        data = {
            "model": "gpt-4.1",
            "messages": [
                {"role": "system", "content": "You are an AI that extracts structured information about a user's core facts, activities, relationships, and schedules from a conversation, returning a single JSON object."}, 
                {"role": "user", "content": extraction_prompt}
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }
                
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
        response.raise_for_status()
        
        content_str = response.json().get('choices', [{}])[0].get('message', {}).get('content', '{{}}')
        extracted_data = json.loads(content_str)

        # 3. 각 정보 유형별로 저장 함수 호출
        if extracted_data.get("user_attributes"):
            _save_user_attributes(user, extracted_data["user_attributes"])

        if extracted_data.get("activity"):
            _save_activity(user, extracted_data["activity"], today_str)

        if extracted_data.get("relationships"):
            _save_relationships(user, extracted_data["relationships"])

        if extracted_data.get("schedule"): # 새 기능: 스케줄 데이터 저장
            _save_schedule(user, extracted_data["schedule"], today_str)
                
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError, IndexError, ValueError) as e:
        print(f"--- 속성, 활동, 관계 또는 스케줄을 추출하거나 저장할 수 없습니다. 오류: {e} ---")

def _get_existing_attributes_context(user):
    existing_attributes = UserAttribute.objects.filter(user=user)
    if not existing_attributes.exists():
        return ""
    attribute_list = [f"- {attr.fact_type}: {attr.content}" for attr in existing_attributes]
    return "\n--- 현재까지 기억된 사용자 속성 ---\n" + "\n".join(attribute_list) + "\n--------------------\n"

def _get_conversation_history_context(recent_history):
    if not recent_history:
        return ""
    history_strings = [f"{('사용자' if chat.is_user else 'AI')}: {chat.message}" for chat in recent_history]
    history_str = "\n".join(reversed(history_strings))
    return f"--- 이전 대화 ---\n{history_str}\n---\n"

def _get_existing_relationships_context(user):
    existing_relationships = UserRelationship.objects.filter(user=user)
    if not existing_relationships.exists():
        return ""
    rel_list = [f"- {rel.name} ({rel.relationship_type})" for rel in existing_relationships]
    rel_list_str = "\n".join(rel_list)
    return f"--- 현재 저장된 인물 목록 ---\n{rel_list_str}\n---"

def _save_user_attributes(user, attributes_data):
    print(f"--- Found Attributes to Create/Update for {user.username}: {attributes_data} ---")
    for attribute_data in attributes_data:
        action = attribute_data.get('action') # 'action' 필드는 이제 DB 작업에 덜 중요합니다.
        fact_type = attribute_data.get('fact_type')
        content = attribute_data.get('content')

        if not (fact_type and content):
            continue

        # 'create' 및 'update' 작업 모두에 대해 'user'와 'fact_type'을 사용하여 기존 속성을 찾고 'content'를 업데이트합니다.
        # 이는 각 (사용자, 속성 유형) 조합에 대해 하나의 고유한 항목만 존재하도록 보장합니다.
        UserAttribute.objects.update_or_create(
            user=user,
            fact_type=fact_type,
            defaults={'content': content}
        )
        # LLM의 'action' 필드는 이제 DB 메서드를 지시하는 것이 아니라 정보 제공용입니다.
        print(f"--- Ensured UserAttribute exists (action: {action}): {fact_type}: {content} for {user.username} ---")
def _save_activity(user, activity_data, today_str):
    activities_to_save = []
    if isinstance(activity_data, list):
        activities_to_save = activity_data
    elif isinstance(activity_data, dict):
        activities_to_save = [activity_data]
    else:
        print(f"--- Invalid activity_data format: {type(activity_data)} ---")
        return

    for single_activity_data in activities_to_save:
        if single_activity_data and (single_activity_data.get('place') or single_activity_data.get('memo')):
            memo_content = single_activity_data.get('memo')

            # 최근 10분 이내에 동일한 메모 내용이 있는지 확인
            if memo_content:
                time_threshold = timezone.now() - timedelta(minutes=10)
                is_duplicate = UserActivity.objects.filter(
                    user=user,
                    memo=memo_content,
                    created_at__gte=time_threshold
                ).exists()

                if is_duplicate:
                    print(f"--- Duplicate activity found, skipping save: {{memo_content}} ---")
                    continue  # 중복이므로 이 활동은 건너뜀
            
            time_str = single_activity_data.get('activity_time')
            parsed_time = None
            if time_str:
                try:
                    parsed_time = datetime.strptime(time_str, '%H:%M').time()
                except ValueError:
                    try:
                        parsed_time = datetime.strptime(time_str, '%I:%M %p').time()
                    except ValueError:
                        if '시' in time_str:
                            time_str = time_str.replace('시', ':').replace('분', '')
                            try:
                                parsed_time = datetime.strptime(time_str.strip(), '%H:%M').time()
                            except ValueError:
                                parsed_time = None

            UserActivity.objects.create(
                user=user,
                activity_date=single_activity_data.get('activity_date', today_str),
                activity_time=parsed_time,
                place=single_activity_data.get('place'),
                companion=single_activity_data.get('companion'),
                memo=memo_content
            )
            print(f"--- New Activity Saved for {user.username}: {{single_activity_data}} ---")

def _save_relationships(user, relationships_data):
    print(f"--- Found Relationships to Create/Update for {user.username}: {relationships_data} ---")
    for rel_data in relationships_data:
        name = rel_data.get('name')
        rel_type = rel_data.get('relationship_type')
        traits = rel_data.get('traits')

        if not name or not rel_type:
            continue

        obj, created = UserRelationship.objects.update_or_create(
            user=user,
            name=name,
            defaults={'relationship_type': rel_type}
        )

        if created:
            obj.traits = traits
            obj.save()
            print(f"--- Created new relationship: {name} ---")
        else:
            if traits:
                existing_traits = {t.strip() for t in (obj.traits or "").split(',') if t.strip()}
                new_traits = {t.strip() for t in traits.split(',') if t.strip()}
                existing_traits.update(new_traits)
                obj.traits = ", ".join(existing_traits)
                obj.save()
                print(f"--- Updated relationship: {name} ---")

def _save_schedule(user, schedule_data, today_str):
    print(f"--- {user.username}님을 위한 스케줄 생성 요청 발견: {schedule_data} ---")
    schedules_to_save = []
    if isinstance(schedule_data, list):
        schedules_to_save = schedule_data
    elif isinstance(schedule_data, dict):
        schedules_to_save = [schedule_data]
    else:
        print(f"--- 잘못된 스케줄 데이터 형식: {type(schedule_data)} ---")
        return

    for single_schedule_data in schedules_to_save:
        content = single_schedule_data.get('content')
        schedule_date_str = single_schedule_data.get('schedule_date', today_str)
        schedule_time_str = single_schedule_data.get('schedule_time')

        if not content:
            continue

        parsed_date = None
        try:
            parsed_date = datetime.strptime(schedule_date_str, '%Y-%m-%d').date()
        except ValueError:
            print(f"--- 잘못된 스케줄 날짜 형식: {schedule_date_str} ---")
            continue

        parsed_time = None
        if schedule_time_str:
            try:
                parsed_time = datetime.strptime(schedule_time_str, '%H:%M').time()
            except ValueError:
                print(f"--- 잘못된 스케줄 시간 형식: {schedule_time_str} ---")
                # Continue without time if invalid
                pass

        # 스케줄이 오늘 또는 미래인 경우에만 생성
        if parsed_date >= date.today():
            UserSchedule.objects.update_or_create(
                user=user,
                date=parsed_date,
                schedule_time=parsed_time,
                content=content, # Include content in lookup for exact match
                defaults={} # No defaults needed as all fields are in lookup
            )
            print(f"--- {user.username}님을 위한 스케줄 저장/업데이트 완료: {single_schedule_data} ---")
        else:
            print(f"--- 과거 스케줄 건너뛰기: {single_schedule_data} ---")