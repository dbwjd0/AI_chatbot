
from apscheduler.schedulers.background import BackgroundScheduler
from django.core.management import call_command

def update_analytics_job():
    """
    update_activity_analytics 관리자 명령을 실행합니다.
    """
    try:
        call_command('update_activity_analytics')
        print("'update_activity_analytics' 작업이 성공적으로 실행되었습니다.")
    except Exception as e:
        print(f"'update_activity_analytics' 작업 실행 중 오류 발생: {e}")

def start():
    """
    스케줄러를 시작하고 일일 작업을 추가합니다.
    """
    scheduler = BackgroundScheduler()
    # 매일 새벽 3시에 실행되도록 설정
    scheduler.add_job(
        update_analytics_job,
        'cron',
        hour='3',
        minute='0',
        id='update_analytics_daily_job',  # 고유한 ID 부여
        replace_existing=True
    )
    scheduler.start()
    print("스케줄러가 시작되었습니다... 분석 작업이 매일 새벽 3시에 실행됩니다.")
