from django.urls import path
from .views import main, chatWithAi, auth, schedule, friend, quiz, profile # profile 임포트

urlpatterns = [
    path('', main.opening_view, name='opening'),
    path('room/', main.room, name='room'),
    path('start/', main.start_view, name='start'),
    path('chat_history/', main.chat_history_view, name='chat_history'),
    path('chat/', main.chat_main_view, name='chat'),
    path('landing/', main.landing_view, name='landing'),
    path('narrative-setup/', main.narrative_setup_view, name='narrative_setup'),
    path('chat_response/', chatWithAi.chat_response, name='chat_response'),
    path('record-feedback/', chatWithAi.record_feedback, name='record_feedback'),
    path('chat_history/load-messages/', main.load_more_messages, name='load_more_messages'),
    path('opening/', main.opening_view, name='opening'),
    path('signup/', auth.signup_view, name='signup'),
    path('login/', auth.login_view, name='login'),
    path('logout/', auth.logout_view, name='logout'),
    path('ai_status/', main.ai_status, name='ai_status'),
    path('profile/edit/', profile.edit_profile_view, name='edit_profile'), # 프로필 편집 URL 추가
    path('quiz_mode/', quiz.quiz_mode_view, name='quiz_mode'),
    path('start_quiz/', quiz.start_quiz_view, name='start_quiz'),
    path('quiz_question/', quiz.quiz_question_view, name='quiz_question'),
    path('quiz_history/', quiz.quiz_history_view, name='quiz_history'),
    path('quiz/', quiz.quiz_view, name='quiz'),
    path('schedule/', schedule.schedule_view, name='schedule'),
    path('get_proactive_message/', main.get_proactive_message_view, name='get_proactive_message'),
    path('check-notification/', main.check_proactive_notification, name='check_notification'),
    path('get-and-clear-pending-message/', main.get_and_clear_pending_message, name='get_and_clear_pending_message'),
    path('api/get-interaction-dialog/', main.get_interaction_dialog_view, name='get_interaction_dialog'),
    path('api/refrigerator-contents/', main.refrigerator_contents_view, name='refrigerator_contents'),
    path('api/consume-food/', main.consume_food_view, name='consume_food'),
    # 🌟 친구 기능 URL 패턴 추가 🌟
    path('friends/', friend.friend_management_view, name='friend_management'),
    path('api/friends/', friend.friend_list_view, name='api_friend_list'), 
    path('friends/request/', friend.send_friend_request, name='send_friend_request'), 
    path('friends/accept/<int:request_id>/', friend.accept_friend_request, name='accept_friend_request'),
    path('friends/reject/<int:request_id>/', friend.reject_friend_request, name='reject_friend_request'),
    path('friends/delete/<int:friendship_id>/', friend.delete_friend, name='delete_friend'),
    path('friends/search/', friend.search_users, name='search_users'),
    path('friends/message/send/', friend.send_friend_message, name='send_friend_message'), # 쪽지 보내기
    path('friends/message/unread/', friend.check_unread_friend_messages, name='check_unread_friend_messages'), # 읽지 않은 쪽지 확인
    path('friends/message/unread/get/', friend.get_and_mark_read_friend_message, name='get_and_mark_read_friend_message'), # 읽지 않은 쪽지 하나 가져오기 및 읽음 처리
    path('friends/message/unread/get_processed/', friend.get_processed_unread_friend_message, name='get_processed_unread_friend_message'), # 처리된 읽지 않은 쪽지 가져오기
    path('bgm_player/', main.bgm_player_view, name='bgm_player'), # BGM iframe player URL
]