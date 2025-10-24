from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone
import re
import json # json 모듈 임포트
from ..models import UserProfile, ChatMessage, UserAttribute, UserRelationship
from chatbot_app.services.proactive_service import generate_proactive_message

QUESTIONS = [
    {'step': 0, 'question': '안녕! 만나서 반가워. 너의 이름은 뭐야?', 'fact_type': '이름'},
    {'step': 1, 'question': '너는 남자야, 여자야?', 'fact_type': '성별'},
    {'step': 2, 'question': '몇 살이야?', 'fact_type': '나이'},
    {'step': 3, 'question': 'MBTI는 뭐야? 알려줄 수 있어?', 'fact_type': 'mbti'},
]

def parse_onboarding_answer(answer, fact_type):
    """온보딩 답변을 파싱하여 핵심 정보만 추출합니다."""
    cleaned_answer = None

    if fact_type == '이름':
        cleaned_answer = answer.strip()
    elif fact_type == '성별':
        if '남자' in answer: cleaned_answer = '남자'
        elif '여자' in answer: cleaned_answer = '여자'
    elif fact_type == '나이':
        match = re.search(r'\d+', answer)
        if match: cleaned_answer = match.group(0)
    elif fact_type == 'mbti':
        match = re.search(r'[A-Z]{4}', answer.upper())
        if match: cleaned_answer = match.group(0)
    
    # 파싱에 실패했거나 해당 fact_type에 대한 특정 로직이 없는 경우 원본 답변을 반환 (이름의 경우 이미 처리됨)
    # 다른 fact_type의 경우, 파싱 실패 시 None을 반환하여 저장되지 않도록 하거나, 
    # setup_view에서 cleaned_answer가 None일 경우 UserAttribute를 생성하지 않도록 처리해야 함.
    # 여기서는 클라이언트 측 유효성 검사가 있으므로, 파싱 실패 시 None을 반환하는 것이 더 안전함.
    return cleaned_answer if cleaned_answer is not None else ""

@login_required
def narrative_setup_view(request):
    """새로운 대화형 온보딩 페이지를 렌더링하고, 사용자 정보 제출을 처리합니다."""
    if request.method == 'POST':
        data = json.loads(request.body)
        fact_type = data.get('fact_type')
        content = data.get('content')

        if fact_type and content:
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

    return render(request, 'narrative_setup.html')

@login_required
def setup_view(request):
    onboarding_step = request.session.get('onboarding_step', 0)

    if request.method == 'POST':
        answer = request.POST.get('answer', '').strip()
        
        if answer:
            current_question = QUESTIONS[onboarding_step]
            cleaned_answer = parse_onboarding_answer(answer, current_question['fact_type'])
            
            if cleaned_answer:
                UserAttribute.objects.create(
                    user=request.user,
                    fact_type=current_question['fact_type'],
                    content=cleaned_answer
                )
            
            onboarding_step += 1
            request.session['onboarding_step'] = onboarding_step

    if onboarding_step >= len(QUESTIONS):
        # 온보딩 완료
        profile = request.user.profile
        profile.is_onboarding_complete = True
        profile.save()
        del request.session['onboarding_step']
        return redirect('opening')

    question_to_ask = QUESTIONS[onboarding_step]['question']
    fact_type_for_validation = QUESTIONS[onboarding_step]['fact_type']
    return render(request, 'setup.html', {'question': question_to_ask, 'fact_type': fact_type_for_validation})

@login_required
def room(request):
    """캐릭터가 있는 방 페이지를 렌더링합니다."""
    if not request.user.profile.is_onboarding_complete:
        return redirect('narrative_setup')
    return render(request, 'room.html')

@login_required
def chat_view(request):
    """메인 채팅 페이지를 렌더링합니다. (페이지네이션 적용)"""
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

    return render(request, 'chat.html', {
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
def game_chat_view(request):
    """미연시 스타일의 새로운 채팅 페이지를 렌더링합니다."""
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

    return render(request, 'game_chat.html', {
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
    message_text, emotion = generate_proactive_message(request.user)
    if message_text:
        # 능동적인 메시지를 ChatMessage에 저장하여 기록을 유지하고 반복 전송을 방지합니다.
        proactive_chat_message = ChatMessage.objects.create(
            user=request.user,
            message=message_text,
            is_user=False, # 봇 메시지
            character_emotion=emotion # 감정 저장
        )
        # 저장 후, 프론트엔드에 전달할 메시지 객체를 다시 가져오거나 구성
        return JsonResponse({
            'message': proactive_chat_message.message,
            'character_emotion': proactive_chat_message.character_emotion,
            'timestamp': proactive_chat_message.timestamp.isoformat()
        })
    return JsonResponse({'message': None})

@login_required
def opening_view(request):
    """오프닝 비디오를 재생하는 페이지를 렌더링합니다."""
    return render(request, 'opening.html')
