from django.apps import AppConfig

class ChatbotAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chatbot_app"

    def ready(self):
        # 앱이 준비되면 스케줄러를 시작합니다.
        from . import scheduler
        scheduler.start()