from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from ..models import QuizResult
from ..services import quiz_service

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
