from datetime import date, time
from django.contrib.auth.models import User
from chatbot_app.models import UserSchedule
from typing import List, Optional

def get_schedules_for_day(user: User, schedule_date: date) -> List[UserSchedule]:
    """
    지정된 사용자와 날짜에 대한 모든 일정을 가져옵니다.
    """
    return UserSchedule.objects.filter(user=user, date=schedule_date).order_by('schedule_time')

def create_schedule(user: User, schedule_date: date, content: str, schedule_time: Optional[time] = None) -> UserSchedule:
    """
    새로운 일정 항목을 생성합니다.
    """
    schedule = UserSchedule.objects.create(
        user=user,
        date=schedule_date,
        content=content,
        schedule_time=schedule_time
    )
    return schedule

def update_schedule_entry(schedule_id: int, content: str, schedule_time: Optional[time] = None) -> Optional[UserSchedule]:
    """
    지정된 ID의 일정 항목을 업데이트합니다.
    """
    try:
        schedule = UserSchedule.objects.get(id=schedule_id)
        schedule.content = content
        schedule.schedule_time = schedule_time
        schedule.save()
        return schedule
    except UserSchedule.DoesNotExist:
        return None

def delete_schedule_entry(schedule_id: int) -> bool:
    """
    지정된 ID의 일정 항목을 삭제합니다.
    """
    try:
        schedule = UserSchedule.objects.get(id=schedule_id)
        schedule.delete()
        return True
    except UserSchedule.DoesNotExist:
        return False
