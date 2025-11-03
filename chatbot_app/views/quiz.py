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
    context = {}
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'submit_answer':
            user_answer = request.POST.get('answer')
            if user_answer:
                quiz_service.process_answer(request.session, user_answer)
            # After processing answer, redirect to show feedback for the current question
            return redirect('quiz_question')
        elif action == 'next_question':
            # Advance to the next question
            quiz_service.advance_question(request.session)
            # Clear feedback from session as we are moving to next question
            request.session.pop('quiz_feedback', None)
            return redirect('quiz_question')

    # GET 요청 처리 (질문 또는 피드백 표시)
    # 또는 POST 요청 후 리디렉션되어 다시 GET으로 들어온 경우
    
    feedback = None
    if 'quiz_feedback' in request.session:
        feedback = quiz_service.get_feedback(request.session) # Use the new get_feedback
        context['quiz_feedback'] = feedback

    # 퀴즈가 끝났는지 확인
    if quiz_service.is_quiz_finished(request.session):
        # 퀴즈가 끝났고, 마지막 문제에 대한 피드백이 있다면 먼저 보여줌
        if feedback and not request.POST.get('action') == 'next_question': # Only show feedback if not explicitly advancing
            # This case handles showing feedback for the very last question before showing results
            question_context = quiz_service.get_current_question_context(request.session)
            if question_context:
                context.update(question_context)
            return render(request, 'quiz.html', context)
        
        result_data = quiz_service.save_quiz_result_and_cleanup(request.session, request.user)
        context.update({'quiz_finished': True, **result_data})
        return render(request, 'quiz.html', context)
    
    # 다음 문제 표시 (또는 피드백과 함께 현재 문제 표시)
    question_context = quiz_service.get_current_question_context(request.session)
    if not question_context:
        return redirect('quiz_mode') # 퀴즈가 시작되지 않은 경우

    context.update(question_context)
    return render(request, 'quiz.html', context)

@login_required
def quiz_view(request):
    return render(request, 'quiz.html')
