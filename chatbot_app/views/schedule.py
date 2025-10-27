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
    GET: 오늘 날짜의 모든 일정을 조회합니다.
    POST: 일정 항목을 생성, 업데이트 또는 삭제합니다.
    """
    today = date.today()
    user = request.user

    if request.method == 'GET':
        schedules = schedule_service.get_schedules_for_day(user, today)
        schedule_list = []
        for schedule in schedules:
            schedule_list.append({
                'id': schedule.id,
                'content': schedule.content,
                'schedule_time': schedule.schedule_time.strftime('%H:%M') if schedule.schedule_time else None
            })
        return JsonResponse({'schedules': schedule_list})

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action') # 'create', 'update', 'delete'
            schedule_id = data.get('id')
            content = data.get('content', '')
            schedule_time_str = data.get('schedule_time')
            schedule_time = None

            if schedule_time_str:
                try:
                    schedule_time = datetime.strptime(schedule_time_str, '%H:%M').time()
                except ValueError:
                    return JsonResponse({'status': 'error', 'message': '잘못된 시간 형식입니다. HH:MM 형식으로 입력해주세요.'}, status=400)

            if action == 'create':
                schedule = schedule_service.create_schedule(user, today, content, schedule_time)
                return JsonResponse({'status': 'success', 'message': '일정이 생성되었습니다.', 'id': schedule.id})
            elif action == 'update':
                if not schedule_id:
                    return JsonResponse({'status': 'error', 'message': '업데이트할 일정의 ID가 필요합니다.'}, status=400)
                updated_schedule = schedule_service.update_schedule_entry(schedule_id, content, schedule_time)
                if updated_schedule:
                    return JsonResponse({'status': 'success', 'message': '일정이 업데이트되었습니다.'})
                else:
                    return JsonResponse({'status': 'error', 'message': '일정을 찾을 수 없습니다.'}, status=404)
            elif action == 'delete':
                if not schedule_id:
                    return JsonResponse({'status': 'error', 'message': '삭제할 일정의 ID가 필요합니다.'}, status=400)
                if schedule_service.delete_schedule_entry(schedule_id):
                    return JsonResponse({'status': 'success', 'message': '일정이 삭제되었습니다.'})
                else:
                    return JsonResponse({'status': 'error', 'message': '일정을 찾을 수 없습니다.'}, status=404)
            else:
                return JsonResponse({'status': 'error', 'message': '알 수 없는 액션입니다.'}, status=400)

        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': '잘못된 요청입니다.'}, status=400)
