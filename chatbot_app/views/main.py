from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
import re
from ..models import UserProfile, ChatMessage, UserAttribute, UserRelationship

QUESTIONS = [
    {'step': 0, 'question': '안녕! 만나서 반가워. 너의 이름은 뭐야?', 'fact_type': '이름'},
    {'step': 1, 'question': '너는 남자야, 여자야?', 'fact_type': '성별'},
    {'step': 2, 'question': '몇 살이야?', 'fact_type': '나이'},
    {'step': 3, 'question': 'MBTI는 뭐야? 알려줄 수 있어?', 'fact_type': 'mbti'},
]

def parse_onboarding_answer(answer, fact_type):
    """온보딩 답변을 파싱하여 핵심 정보만 추출합니다."""
    if fact_type == 'gender':
        if '남자' in answer: return '남자'
        if '여자' in answer: return '여자'
    elif fact_type == 'age':
        match = re.search(r'\d+', answer)
        if match: return match.group(0)
    elif fact_type == 'mbti':
        match = re.search(r'[A-Z]{4}', answer.upper())
        if match: return match.group(0)
    
    # 이름 또는 파싱 실패 시 원본 답변 반환
    return answer

@login_required
def setup_view(request):
    onboarding_step = request.session.get('onboarding_step', 0)

    if request.method == 'POST':
        answer = request.POST.get('answer', '').strip()
        
        if answer:
            current_question = QUESTIONS[onboarding_step]
            cleaned_answer = parse_onboarding_answer(answer, current_question['fact_type'])
            
            UserAttribute.objects.create(
                user=request.user,
                fact_type=current_question['fact_type'],
                content=cleaned_answer
            )
            
            onboarding_step += 1
            request.session['onboarding_step'] = onboarding_step

    if onboarding_step >= len(QUESTIONS):
        # Onboarding complete
        profile = request.user.profile
        profile.is_onboarding_complete = True
        profile.save()
        del request.session['onboarding_step']
        return redirect('room')

    question_to_ask = QUESTIONS[onboarding_step]['question']
    return render(request, 'setup.html', {'question': question_to_ask})

@login_required
def room(request):
    """캐릭터가 있는 방 페이지를 렌더링합니다."""
    if not request.user.profile.is_onboarding_complete:
        return redirect('setup')
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
    
    # 템플릿에서는 시간순으로 보여줘야 하므로 다시 뒤집음
    chat_messages_data = list(messages_page.object_list.values('message', 'is_user', 'timestamp'))[::-1]

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
    
    # 템플릿에 맞게 데이터 포맷팅 (시간순으로 뒤집기)
    messages_data = list(messages_page.object_list.values('message', 'is_user', 'timestamp'))[::-1]
    
    return JsonResponse({
        'messages': messages_data,
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
    # Serialize relationships for pagination in JavaScript
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
