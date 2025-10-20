from datetime import date
from django.contrib.auth.models import User
from chatbot_app.models import UserSchedule

def get_or_create_schedule(user: User, schedule_date: date) -> UserSchedule:
    """
    지정된 사용자와 날짜에 대한 일정을 가져오거나, 없으면 새로 생성합니다.
    """
    schedule, created = UserSchedule.objects.get_or_create(
        user=user,
        date=schedule_date,
        defaults={'content': ''}
    )
    return schedule

def update_schedule(user: User, schedule_date: date, content: str) -> UserSchedule:
    """
    지정된 사용자와 날짜의 일정 내용을 업데이트합니다.
    """
    schedule = get_or_create_schedule(user, schedule_date)
    schedule.content = content
    schedule.save()
    return schedule
