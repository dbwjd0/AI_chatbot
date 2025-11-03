from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone
import re
import json # json 모듈 임포트
from django.db.models import Q
from ..models import UserProfile, ChatMessage, UserAttribute, UserRelationship, PendingProactiveMessage, QuizResult, UserFriendship, FriendMessage # FriendMessage 모델 추가
from chatbot_app.services.proactive_service import generate_proactive_message
from chatbot_app.services import chat_service
from ..services import friend_message_service


def landing_view(request):
    """사용자의 온보딩 완료 여부에 따라 적절한 페이지로 리디렉션합니다."""
    if request.user.profile.is_onboarding_complete:
        return redirect('start')
    else:
        return redirect('narrative_setup')

PERSISTENT_ATTRIBUTES = ['성별', 'mbti', '나이']

@login_required
def narrative_setup_view(request):
    """새로운 대화형 온보딩 페이지를 렌더링하고, 사용자 정보 제출을 처리합니다."""
    if request.method == 'POST':
        data = json.loads(request.body)
        fact_type = data.get('fact_type')
        content = data.get('content')

        if fact_type and content:
            if fact_type == '이름':
                profile = request.user.profile
                profile.nickname = content
                profile.save()
            
            elif fact_type == 'ai_name':
                profile = request.user.profile
                profile.chatbot_name = content
                profile.save()

            elif fact_type == 'persona_preference': # New condition
                profile = request.user.profile
                profile.persona_preference = content
                profile.save()

            elif fact_type in PERSISTENT_ATTRIBUTES:
                UserAttribute.objects.update_or_create(
                    user=request.user,
                    fact_type=fact_type,
                    defaults={'content': content}
                )
            return JsonResponse({'status': 'success', 'message': f'{fact_type} 저장 완료'})
        
        if data.get('action') == 'complete':
            profile = request.user.profile
            profile.is_onboarding_complete = True
            profile.save()
            return JsonResponse({'status': 'success', 'message': '온보딩 완료'})

        return JsonResponse({'status': 'error', 'message': '데이터가 누락되었습니다.'}, status=400)

    # 온보딩을 이미 완료한 경우, 메인 페이지로 리디렉션
    if request.user.profile.is_onboarding_complete:
        return redirect('room')
        
    return render(request, 'narrative_setup.html')

@login_required
def room(request):
    """캐릭터가 있는 방 페이지를 렌더링합니다."""
    if not request.user.profile.is_onboarding_complete:
        return redirect('narrative_setup')
    
    context = {
        'chatbot_name': request.user.profile.chatbot_name
    }
    return render(request, 'room.html', context)

@login_required
def chat_history_view(request):
    """채팅 기록 페이지를 렌더링합니다. (페이지네이션 적용)"""
    user_profile = UserProfile.objects.get(user=request.user)
    
    # 최신 메시지를 먼저 가져오기 위해 timestamp 내림차순으로 정렬
    all_messages = ChatMessage.objects.filter(user=request.user).order_by('-timestamp')
    
    # Paginator를 사용하여 20개씩 페이지 분할
    paginator = Paginator(all_messages, 20)
    page_number = 1
    messages_page = paginator.get_page(page_number)
    
    # 템플릿에서는 시간순으로 보여줘야 하므로, JS에서 사용하기 위해 JSON으로 가공
    chat_messages_data = [
        {
            'message': msg.message,
            'is_user': msg.is_user,
            'timestamp': msg.timestamp.isoformat(),
            'image_url': msg.image.url if msg.image else None
        }
        for msg in messages_page.object_list
    ][::-1] # 시간순으로 뒤집기

    return render(request, 'chat_history.html', {
        'user_profile': user_profile, 
        'chat_messages': chat_messages_data,
        'has_next_page': messages_page.has_next() # 다음 페이지가 있는지 여부
    })

@login_required
def load_more_messages(request):
    """이전 채팅 기록을 추가로 불러옵니다."""
    page_number = int(request.GET.get('page', 1))
    
    all_messages = ChatMessage.objects.filter(user=request.user).order_by('-timestamp')
    paginator = Paginator(all_messages, 20)
    
    if page_number > paginator.num_pages:
        return JsonResponse({'messages': [], 'has_next_page': False})

    messages_page = paginator.get_page(page_number)
    
    # JSON으로 만들기 위해 직접 데이터 가공
    messages_data = [
        {
            'message': msg.message,
            'is_user': msg.is_user,
            'timestamp': msg.timestamp.isoformat(),
            'image_url': msg.image.url if msg.image else None
        }
        for msg in messages_page.object_list
    ][::-1] # 시간순으로 뒤집기
    
    return JsonResponse({
        'messages': messages_data,
        'has_next_page': messages_page.has_next()
    })

@login_required
def chat_main_view(request):
    """게임 스타일의 채팅 페이지를 렌더링합니다."""
    user_profile = UserProfile.objects.get(user=request.user)
    
    all_messages = ChatMessage.objects.filter(user=request.user).order_by('-timestamp')
    
    paginator = Paginator(all_messages, 20)
    page_number = 1
    messages_page = paginator.get_page(page_number)
    
    chat_messages_data = [
        {
            'message': msg.message,
            'is_user': msg.is_user,
            'timestamp': msg.timestamp.isoformat(),
            'image_url': msg.image.url if msg.image else None
        }
        for msg in messages_page.object_list
    ][::-1]

    unread_friend_messages_count = FriendMessage.objects.filter(receiver=request.user, is_read=False).count()

    return render(request, 'chat.html', {
        'user_profile': user_profile, 
        'chat_messages': chat_messages_data,
        'has_next_page': messages_page.has_next(),
        'unread_friend_messages_count': unread_friend_messages_count,
    })

@login_required
def ai_status(request):
    """AI의 상태(기억, 호감도 등)를 보여주는 페이지를 렌더링합니다."""
    user_profile = UserProfile.objects.get(user=request.user)
    affinity_score = user_profile.affinity_score
    core_facts = list(
        UserAttribute.objects.filter(user=request.user).values('fact_type', 'content')
    )
    # JavaScript에서 페이지네이션을 위해 관계를 직렬화
    user_relationships = list(
        UserRelationship.objects.filter(user=request.user).order_by('name').values(
            'serial_code', 'name', 'relationship_type', 'position', 'traits'
        )
    )
    return render(request, 'ai_status.html', {
        'user_profile': user_profile,
        'affinity_score': affinity_score,
        'core_facts': core_facts,
        'user_relationships': user_relationships
    })

@login_required
def get_proactive_message_view(request):
    proactive_chat_message = generate_proactive_message(request.user)
    if proactive_chat_message:
        # 서비스에서 이미 메시지를 생성하고 저장했으므로, 해당 객체를 바로 사용합니다.
        return JsonResponse({
            'message': proactive_chat_message.message,
            'character_emotion': proactive_chat_message.character_emotion,
            'timestamp': proactive_chat_message.timestamp.isoformat()
        })
    return JsonResponse({'message': None})


def opening_view(request):
    """오프닝 비디오를 재생하는 페이지를 렌더링합니다."""
    if request.user.is_authenticated:
        return redirect('landing')
    return render(request, 'opening.html')

@login_required
def check_proactive_notification(request):
    """읽지 않은 능동 메시지가 있는지 확인하고, 없으면 생성을 시도합니다."""
    user = request.user
    has_pending = PendingProactiveMessage.objects.filter(user=user).exists()

    if not has_pending:
        # 읽지 않은 메시지가 없을 경우, 새로 생성을 시도
        generate_proactive_message(user)
        # 생성 시도 후 다시 확인
        has_pending = PendingProactiveMessage.objects.filter(user=user).exists()

    return JsonResponse({'has_pending_message': has_pending})

@login_required
def get_and_clear_pending_message(request):
    """읽지 않은 능동 메시지를 가져오고, '읽음' 처리(삭제)합니다."""
    user = request.user
    pending_message_entry = PendingProactiveMessage.objects.filter(user=user).first()

    if pending_message_entry:
        chat_message = pending_message_entry.message
        
        # '읽음' 처리: pending 테이블에서 해당 기록 삭제
        pending_message_entry.delete()

        return JsonResponse({
            'message': chat_message.message,
            'character_emotion': chat_message.character_emotion,
            'timestamp': chat_message.timestamp.isoformat(),
            'is_user': False, # AI 메시지이므로 항상 False
            'image_url': chat_message.image.url if chat_message.image else None
        })
    
    return JsonResponse({'message': None})

@login_required
def start_view(request):
    """로그인 후 게임 시작 화면을 렌더링합니다."""
    return render(request, 'start.html')

from ..services import friend_message_service


@login_required
def get_interaction_dialog_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        target = data.get('target')

        if not target:
            return JsonResponse({'error': 'Target not provided'}, status=400)

        # AI가 생성한 동적 독백을 가져옴
        message = chat_service.generate_object_monologue(request.user, target)
        
        return JsonResponse({'message': message})

    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def refrigerator_contents_view(request):
    """세션에 저장된 음식 목록을 반환합니다."""
    eaten_foods = request.session.get('eaten_foods', [])
    return JsonResponse({'foods': eaten_foods})

@login_required
def consume_food_view(request):
    """세션에서 특정 음식을 제거합니다."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            food_name = data.get('food_name')

            if not food_name:
                return JsonResponse({'status': 'error', 'message': 'Food name not provided'}, status=400)

            eaten_foods = request.session.get('eaten_foods', [])
            
            # 해당 음식을 목록에서 제거
            foods_to_keep = [food for food in eaten_foods if food.get('name') != food_name]
            
            request.session['eaten_foods'] = foods_to_keep
            
            return JsonResponse({'status': 'success', 'message': f'{food_name} consumed.'})

        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

def bgm_player_view(request):
    """Renders the BGM player HTML for the iframe."""
    return render(request, 'bgm/bgm_player.html')
