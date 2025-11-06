import json
import requests
from datetime import datetime, timedelta, date
from django.utils import timezone
from ..models import UserAttribute, UserActivity, UserRelationship, UserSchedule
from . import schedule_service

from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext as gt

def extract_and_save_user_context_data(user, user_message, bot_message, recent_history, api_key):
    """
    대화 내용을 한 번의 API 호출로 분석하여 사용자 속성, 활동, 인간관계를 추출하고 저장합니다.
    """
    saved_info = []
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

        if extracted_data.get("user_attributes"):
            saved_info.extend(_save_user_attributes(user, extracted_data["user_attributes"]))

        if extracted_data.get("activity"):
            saved_info.extend(_save_activity(user, extracted_data["activity"], today_str))

        if extracted_data.get("relationships"):
            saved_info.extend(_save_relationships(user, extracted_data["relationships"]))

        if extracted_data.get("schedule"):
            saved_info.extend(_save_schedule(user, extracted_data["schedule"], today_str))
                
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError, IndexError, ValueError) as e:
        print(f"--- 속성, 활동, 관계 또는 스케줄을 추출하거나 저장할 수 없습니다. 오류: {e} ---")
    return saved_info

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
    saved_info = []
    for attr_data in attributes_data:
        fact_type = attr_data.get('fact_type')
        content = attr_data.get('content')
        if not (fact_type and content):
            continue

        obj, created = UserAttribute.objects.get_or_create(
            user=user, 
            fact_type=fact_type,
            defaults={'content': content}
        )

        if created:
            saved_info.append(f"[속성] {fact_type}: {content}")
            print(f"--- 새로운 사용자 속성 저장: {fact_type} for {user.username} ---")
        elif obj.content != content:
            obj.content = content
            obj.save()
            saved_info.append(f"[속성 업데이트] {fact_type}: {content}")
            print(f"--- 사용자 속성 업데이트: {fact_type} for {user.username} ---")
    return saved_info

def _save_activity(user, activity_data, today_str):
    saved_info = []
    activities_to_save = [activity_data] if isinstance(activity_data, dict) else activity_data if isinstance(activity_data, list) else []

    for single_activity_data in activities_to_save:
        memo_content = single_activity_data.get('memo')
        if not memo_content:
            continue

        activity_date_str = single_activity_data.get('activity_date', today_str)
        try:
            parsed_date = datetime.strptime(activity_date_str, '%Y-%m-%d').date()
        except ValueError:
            print(f"--- 잘못된 활동 날짜 형식: {activity_date_str} ---")
            continue

        time_str = single_activity_data.get('activity_time')
        parsed_time = None
        if time_str:
            try:
                parsed_time = datetime.strptime(time_str, '%H:%M').time()
            except ValueError:
                pass # 추가 파싱 로직 필요 시 여기에

        # 동일 날짜, 동일 메모의 활동이 이미 있는지 확인
        obj, created = UserActivity.objects.get_or_create(
            user=user,
            activity_date=parsed_date,
            memo=memo_content,
            defaults={
                'activity_time': parsed_time,
                'place': single_activity_data.get('place'),
                'companion': single_activity_data.get('companion')
            }
        )

        if created:
            saved_info.append(f"[활동] {memo_content}")
            print(f"--- 새로운 활동 저장 for {user.username}: {single_activity_data} ---")
        else:
            # 이미 존재하는 활동이지만, 세부 정보가 업데이트되었는지 확인
            if (obj.activity_time != parsed_time or 
                obj.place != single_activity_data.get('place') or 
                obj.companion != single_activity_data.get('companion')):
                
                obj.activity_time = parsed_time
                obj.place = single_activity_data.get('place')
                obj.companion = single_activity_data.get('companion')
                obj.save()
                saved_info.append(f"[활동 업데이트] {memo_content}")
                print(f"--- 활동 업데이트 for {user.username}: {single_activity_data} ---")

    return saved_info

def _save_relationships(user, relationships_data):
    saved_info = []
    for rel_data in relationships_data:
        name = rel_data.get('name')
        rel_type = rel_data.get('relationship_type')
        new_traits = rel_data.get('traits', '')
        if not name or not rel_type:
            continue

        obj, created = UserRelationship.objects.get_or_create(
            user=user, 
            name=name,
            defaults={'relationship_type': rel_type, 'traits': new_traits}
        )

        if created:
            saved_info.append(f"[인간관계] {name} ({rel_type})")
            print(f"--- 새로운 관계 생성: {name} for {user.username} ---")
        else:
            existing_traits = {t.strip() for t in (obj.traits or "").split(',') if t.strip()}
            new_traits_set = {t.strip() for t in new_traits.split(',') if t.strip()}
            if not new_traits_set.issubset(existing_traits):
                existing_traits.update(new_traits_set)
                obj.traits = ", ".join(sorted(list(existing_traits)))
                obj.save()
                saved_info.append(f"[인간관계 업데이트] {name}: 새로운 정보 추가")
                print(f"--- 관계 업데이트: {name} for {user.username} ---")
    return saved_info

def _save_schedule(user, schedule_data, today_str):
    saved_info = []
    schedules_to_save = [schedule_data] if isinstance(schedule_data, dict) else schedule_data if isinstance(schedule_data, list) else []

    for single_schedule_data in schedules_to_save:
        content = single_schedule_data.get('content')
        if not content:
            continue

        schedule_date_str = single_schedule_data.get('schedule_date', today_str)
        try:
            parsed_date = datetime.strptime(schedule_date_str, '%Y-%m-%d').date()
        except ValueError:
            print(f"--- 잘못된 스케줄 날짜 형식: {schedule_date_str} ---")
            continue

        if parsed_date < date.today():
            continue

        schedule_time_str = single_schedule_data.get('schedule_time')
        parsed_time = None
        if schedule_time_str:
            try:
                parsed_time = datetime.strptime(schedule_time_str, '%H:%M').time()
            except ValueError:
                pass

        # Safely handle multiple objects by using filter() and updating the first one found.
        obj = UserSchedule.objects.filter(user=user, date=parsed_date, content=content).first()

        time_display = f"{parsed_time.strftime('%H:%M')} " if parsed_time else ""
        notification_message = f"[일정] {schedule_date_str} {time_display}{content}"

        if obj is None:
            # Create new schedule if none exists
            UserSchedule.objects.create(
                user=user,
                date=parsed_date,
                content=content,
                schedule_time=parsed_time
            )
            saved_info.append(notification_message)
            print(f"--- 새로운 스케줄 저장 for {user.username}: {single_schedule_data} ---")
        elif obj.schedule_time != parsed_time:
            # Update schedule only if the time is different
            obj.schedule_time = parsed_time
            obj.save()
            saved_info.append(f"{notification_message} (업데이트)")
            print(f"--- 스케줄 업데이트 for {user.username}: {single_schedule_data} ---")
            
    return saved_info