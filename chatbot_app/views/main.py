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
from ..quiz_data import QUIZ_QUESTIONS
from . import friend
from ..services import friend_message_service, quiz_service


@login_required
def check_unread_friend_messages(request):
    """현재 사용자에게 읽지 않은 쪽지가 있는지 확인합니다."""
    user = request.user
    has_unread = FriendMessage.objects.filter(receiver=user, is_read=False).exists()
    return JsonResponse({'has_unread_messages': has_unread})

@login_required
def get_processed_unread_friend_message(request):
    current_user = request.user
    
    # 1. 읽지 않은 모든 메시지를 리스트로 가져옵니다.
    unread_messages = list(FriendMessage.objects.filter(receiver=current_user, is_read=False).order_by('timestamp'))
    
    if not unread_messages:
        return JsonResponse({'status': 'no_messages', 'messages': []})

    # 2. 단일 배치 호출로 모든 메시지를 처리합니다.
    processed_results = friend_message_service.process_friend_messages_in_batch(current_user, unread_messages)

    if not processed_results:
        return JsonResponse({'status': 'error', 'message': '메시지 처리에 실패했습니다.'}, status=500)

    # 쉽게 조회할 수 있도록 원본 메시지를 ID별로 매핑합니다.
    unread_messages_map = {msg.id: msg for msg in unread_messages}
    
    final_messages = []
    processed_message_ids = []

    for result in processed_results:
        original_message = unread_messages_map.get(result.get('id'))
        if original_message:
            # 디버깅을 위한 터미널 출력 추가
            print("-" * 20)
            print(f"[디버그] 메시지 처리 정보 (ID: {original_message.id})")
            print(f"  - 수신자 페르소나: {current_user.profile.persona_preference}")
            print(f"  - 원본 메시지: {original_message.message_content}")
            print(f"  - LLM 생성 설명: {result.get('explanation', '설명 없음.')}")
            print(f"  - 최종 가공 메시지: {result.get('answer', '오류')}")
            print("-" * 20)

            final_messages.append({
                'sender': original_message.sender.username,
                'content': result.get('answer', '오류: 메시지 내용을 처리할 수 없습니다.')
            })
            processed_message_ids.append(original_message.id)

    # 3. 성공적으로 처리된 모든 메시지를 읽음으로 표시합니다.
    if processed_message_ids:
        FriendMessage.objects.filter(id__in=processed_message_ids).update(is_read=True)

    # 4. 처리된 메시지 목록을 반환합니다.
    return JsonResponse({
        'status': 'success',
        'messages': final_messages
    })

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
                request.user.first_name = content
                request.user.save()
            
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
    return render(request, 'room.html')

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

    has_unread_friend_messages = FriendMessage.objects.filter(receiver=request.user, is_read=False).exists()

    return render(request, 'chat.html', {
        'user_profile': user_profile, 
        'chat_messages': chat_messages_data,
        'has_next_page': messages_page.has_next(),
        'has_unread_friend_messages': has_unread_friend_messages,
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

@login_required
def quiz_history_view(request):
    """사용자의 퀴즈 기록을 표시합니다."""
    quiz_results = QuizResult.objects.filter(user=request.user).order_by('-date_completed')
    return render(request, 'quiz_history.html', {'quiz_results': quiz_results})

@login_required
def quiz_mode_view(request):
    """퀴즈 모드 설정 페이지를 렌더링합니다."""
    return render(request, 'quiz.html')

@login_required
def start_quiz_view(request):
    """퀴즈 시작 요청을 처리하고 퀴즈 페이지로 리디렉션합니다."""
    if request.method == 'POST':
        genre = request.POST.get('genre')
        difficulty = request.POST.get('difficulty')
        num_questions = int(request.POST.get('num_questions'))

        quiz_service.start_quiz(request.session, genre, difficulty, num_questions)
        
        return redirect('quiz_question')
    return redirect('quiz_mode')

@login_required
def quiz_question_view(request):
    """현재 퀴즈 질문을 표시하고, 답변을 처리하며, 퀴즈 흐름을 관리합니다."""
    # POST 요청 처리 (답변 제출)
    if request.method == 'POST':
        user_answer = request.POST.get('answer')
        if user_answer:
            quiz_service.process_answer(request.session, user_answer)
        return redirect('quiz_question')

    # GET 요청 처리 (질문 또는 피드백 표시)
    context = {}
    feedback = None

    # 이전 답변에 대한 피드백이 있는지 확인하고, 있으면 다음 문제로 넘어감
    if 'quiz_feedback' in request.session:
        feedback = quiz_service.get_feedback_and_advance(request.session)
        context['quiz_feedback'] = feedback

    # 퀴즈가 끝났는지 확인
    if quiz_service.is_quiz_finished(request.session):
        # 피드백이 마지막 문제에 대한 것이었다면, 결과 페이지 전에 잠시 보여줌
        if feedback:
            return render(request, 'quiz.html', context)
        
        result_data = quiz_service.save_quiz_result_and_cleanup(request.session, request.user)
        context.update({'quiz_finished': True, **result_data})
        return render(request, 'quiz.html', context)
    
    # 다음 문제 표시
    question_context = quiz_service.get_current_question_context(request.session)
    if not question_context:
        return redirect('quiz_mode') # 퀴즈가 시작되지 않은 경우

    context.update(question_context)
    return render(request, 'quiz.html', context)

@login_required
def quiz_view(request):
    return render(request, 'quiz.html')

@login_required
def friend_management_view(request):
    """친구 관리 페이지 (friend_management.html)를 렌더링합니다."""
    current_user = request.user

    # 1. 현재 친구 목록 (status=ACCEPTED) 검색
    accepted_friendships = UserFriendship.objects.filter(
        (Q(from_user=current_user) | Q(to_user=current_user)),
        status=UserFriendship.STATUS_ACCEPTED
    ).select_related('from_user', 'to_user')

    accepted_friends_list = []
    for friendship in accepted_friendships:
        friend_user = friendship.to_user if friendship.from_user == current_user else friendship.from_user
        accepted_friends_list.append({
            'username': friend_user.username
        })

    # 2. 받은 친구 요청 목록 (to_user=나 AND status=PENDING) 검색
    pending_requests = UserFriendship.objects.filter(
        to_user=current_user,
        status=UserFriendship.STATUS_PENDING
    ).select_related('from_user')

    pending_requests_list = []
    for request_obj in pending_requests:
        pending_requests_list.append({
            'id': request_obj.id,
            'from_user_username': request_obj.from_user.username,
        })
    
    context = {
        'accepted_friends': accepted_friends_list,
        'pending_requests': pending_requests_list,
    }
    return render(request, 'friend_management.html', context)
