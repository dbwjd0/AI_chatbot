from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone
import re
import json # json 모듈 임포트
from ..models import UserProfile, ChatMessage, UserAttribute, UserRelationship, PendingProactiveMessage, QuizResult
from chatbot_app.services.proactive_service import generate_proactive_message
from ..quiz_data import QUIZ_QUESTIONS
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

    return render(request, 'chat.html', {
        'user_profile': user_profile, 
        'chat_messages': chat_messages_data,
        'has_next_page': messages_page.has_next()
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

        filtered_questions = [
            q for q in QUIZ_QUESTIONS
            if (genre == 'all' or q['genre'] == genre)
        ]

        import random
        random.shuffle(filtered_questions)
        selected_questions = filtered_questions[:num_questions]
        request.session['quiz_total_questions'] = len(selected_questions)
        request.session['selected_genre'] = genre # Store selected genre

        request.session['quiz_questions'] = selected_questions
        request.session['current_question_index'] = 0
        request.session['quiz_score'] = 0
        return redirect('quiz_question')
    return redirect('quiz_mode')

@login_required
def quiz_question_view(request):
    """현재 퀴즈 질문을 표시하고 답변을 처리합니다."""
    quiz_questions = request.session.get('quiz_questions')
    current_question_index = request.session.get('current_question_index')
    quiz_score = request.session.get('quiz_score')
    quiz_total_questions = request.session.get('quiz_total_questions')
    
    # Initialize quiz_feedback for this request
    quiz_feedback_for_template = None

    if not quiz_questions or current_question_index is None or quiz_total_questions is None:
        return redirect('quiz_mode')

    if request.method == 'POST':
        user_answer = request.POST.get('answer')
        current_question = quiz_questions[current_question_index]
        correct_answer = current_question['answer']

        is_correct = (user_answer == correct_answer)
        if is_correct:
            request.session['quiz_score'] += 1

        request.session['quiz_feedback'] = {
            'is_correct': is_correct,
            'correct_answer': correct_answer,
            'user_answer': user_answer,
            'character_emotion': '정답' if is_correct else '오답',
        }
        return redirect('quiz_question')

    # GET 요청 처리
    if 'quiz_feedback' in request.session:
        quiz_feedback_for_template = request.session['quiz_feedback']
        
        if request.GET.get('next_question') == 'true':
            request.session['current_question_index'] += 1
            current_question_index = request.session['current_question_index']
            request.session.pop('quiz_feedback') # Clear feedback after advancing
            quiz_feedback_for_template = None
    else:
        pass


    if current_question_index >= quiz_total_questions:
        final_score = request.session['quiz_score']
        selected_genre = request.session.get('selected_genre', 'all') # Retrieve selected genre

        # Save quiz result
        from ..models import QuizResult
        QuizResult.objects.create(
            user=request.user,
            genre=selected_genre,
            num_questions=quiz_total_questions,
            score=final_score
        )

        del request.session['quiz_questions']
        del request.session['current_question_index']
        del request.session['quiz_score']
        del request.session['quiz_total_questions']
        del request.session['selected_genre'] # Clear selected genre from session
        return render(request, 'quiz.html', {'quiz_finished': True, 'final_score': final_score, 'total_questions': quiz_total_questions})
    else:
        current_question = quiz_questions[current_question_index]
        context = {
            'question': current_question['question'],
            'options': current_question['options'],
            'current_question_number': current_question_index + 1,
            'total_questions': quiz_total_questions,
            'quiz_active': True,
            'quiz_feedback': quiz_feedback_for_template,
        }
        return render(request, 'quiz.html', context)

@login_required
def quiz_view(request):
    return render(request, 'quiz.html')
