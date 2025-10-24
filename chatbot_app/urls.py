from django.urls import path
from .views import main, chatWithAi, auth, schedule

urlpatterns = [
    path('', main.room, name='room'),
    path('chat/', main.chat_view, name='chat'),
    path('game-chat/', main.game_chat_view, name='game_chat'),
    path('narrative-setup/', main.narrative_setup_view, name='narrative_setup'),
    path('chat_response/', chatWithAi.chat_response, name='chat_response'),
    path('chat/load-messages/', main.load_more_messages, name='load_more_messages'),
    path('setup/', main.setup_view, name='setup'),
    path('opening/', main.opening_view, name='opening'),
    path('signup/', auth.signup_view, name='signup'),
    path('login/', auth.login_view, name='login'),
    path('logout/', auth.logout_view, name='logout'),
    path('ai_status/', main.ai_status, name='ai_status'),
    path('schedule/', schedule.schedule_view, name='schedule'),
    path('get_proactive_message/', main.get_proactive_message_view, name='get_proactive_message'),
]
