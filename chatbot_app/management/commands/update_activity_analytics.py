
import datetime
from django.core.management.base import BaseCommand
from django.db.models import Count, Value
from django.db.models.functions import Coalesce
from chatbot_app.models import UserActivity, ActivityAnalytics
from django.utils import timezone

class Command(BaseCommand):
    help = 'UserActivity 데이터를 주간, 월간, 연간 단위로 집계하여 ActivityAnalytics 테이블에 저장합니다.'

    def handle(self, *args, **options):
        self.stdout.write("활동 분석 데이터 업데이트를 시작합니다...")

        # 어제 날짜를 기준으로 집계
        yesterday = timezone.now().date() - datetime.timedelta(days=1)
        
        activities = UserActivity.objects.filter(activity_date=yesterday)

        if not activities.exists():
            self.stdout.write(self.style.SUCCESS(f"{yesterday}에 해당하는 활동 기록이 없습니다. 업데이트할 내용이 없습니다."))
            return

        # place와 companion이 NULL인 경우 빈 문자열로 대체하여 집계
        daily_summary = activities.annotate(
            place_non_null=Coalesce('place', Value('')),
            companion_non_null=Coalesce('companion', Value(''))
        ).values(
            'user', 'place_non_null', 'companion_non_null'
        ).annotate(
            daily_count=Count('id')
        ).order_by('user')

        for summary in daily_summary:
            user_id = summary['user']
            place = summary['place_non_null']
            companion = summary['companion_non_null']
            count = summary['daily_count']

            # 주간 (Weekly) 통계 업데이트
            start_of_week = yesterday - datetime.timedelta(days=yesterday.weekday())
            self.update_analytics('weekly', start_of_week, user_id, place, companion, count)

            # 월간 (Monthly) 통계 업데이트
            start_of_month = yesterday.replace(day=1)
            self.update_analytics('monthly', start_of_month, user_id, place, companion, count)

            # 연간 (Yearly) 통계 업데이트
            start_of_year = yesterday.replace(month=1, day=1)
            self.update_analytics('yearly', start_of_year, user_id, place, companion, count)

        self.stdout.write(self.style.SUCCESS(f"{yesterday} 날짜의 활동 분석 데이터가 성공적으로 업데이트되었습니다."))

    def update_analytics(self, period_type, start_date, user_id, place, companion, count):
        """
        ActivityAnalytics 레코드를 업데이트하거나 생성하는 헬퍼 함수
        """
        analytics, created = ActivityAnalytics.objects.get_or_create(
            user_id=user_id,
            period_type=period_type,
            period_start_date=start_date,
            place=place,
            companion=companion,
            defaults={'count': 0}
        )
        analytics.count += count
        analytics.save()

        action = "생성" if created else "업데이트"
        self.stdout.write(f"  - {action}: 사용자 {user_id}의 '{place}' 장소({companion} 동행)에 대한 {period_type} 분석. 새로운 횟수: {analytics.count}")
