from django.urls import path
from .views import main, chatWithAi, auth, schedule

urlpatterns = [
    path('', main.opening_view, name='opening'),
    path('room/', main.room, name='room'),
    path('start/', main.start_view, name='start'),
    path('chat_history/', main.chat_history_view, name='chat_history'),
    path('chat/', main.chat_main_view, name='chat'),
    path('landing/', main.landing_view, name='landing'),
    path('narrative-setup/', main.narrative_setup_view, name='narrative_setup'),
    path('chat_response/', chatWithAi.chat_response, name='chat_response'),
    path('chat_history/load-messages/', main.load_more_messages, name='load_more_messages'),
    path('opening/', main.opening_view, name='opening'),
    path('signup/', auth.signup_view, name='signup'),
    path('login/', auth.login_view, name='login'),
    path('logout/', auth.logout_view, name='logout'),
    path('ai_status/', main.ai_status, name='ai_status'),
    path('quiz_mode/', main.quiz_mode_view, name='quiz_mode'),
    path('start_quiz/', main.start_quiz_view, name='start_quiz'),
    path('quiz_question/', main.quiz_question_view, name='quiz_question'),
    path('quiz_history/', main.quiz_history_view, name='quiz_history'), # New URL pattern
    path('schedule/', schedule.schedule_view, name='schedule'),
    path('get_proactive_message/', main.get_proactive_message_view, name='get_proactive_message'),
    path('check-notification/', main.check_proactive_notification, name='check_notification'),
    path('get-and-clear-pending-message/', main.get_and_clear_pending_message, name='get_and_clear_pending_message'),
]