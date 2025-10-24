import json
from datetime import date, time, datetime # Import time and datetime
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from chatbot_app.services import schedule_service

@login_required
@require_http_methods(["GET", "POST"])
def schedule_view(request):
    """
    GET: 오늘 날짜의 일정을 조회합니다.
    POST: 오늘 날짜의 일정을 업데이트합니다.
    """
    today = date.today()
    user = request.user

    if request.method == 'GET':
        schedule = schedule_service.get_or_create_schedule(user, today)
        schedule_time_str = schedule.schedule_time.strftime('%H:%M') if schedule.schedule_time else None
        return JsonResponse({'content': schedule.content, 'schedule_time': schedule_time_str})

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            content = data.get('content', '')
            schedule_time_str = data.get('schedule_time')
            schedule_time = None
            if schedule_time_str:
                try:
                    schedule_time = datetime.strptime(schedule_time_str, '%H:%M').time()
                except ValueError:
                    return JsonResponse({'status': 'error', 'message': '잘못된 시간 형식입니다. HH:MM 형식으로 입력해주세요.'}, status=400)

            schedule_service.update_schedule(user, today, content, schedule_time)
            return JsonResponse({'status': 'success', 'message': '일정이 저장되었습니다.'})
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': '잘못된 요청입니다.'}, status=400)
