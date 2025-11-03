import random
from ..models import QuizResult
from ..quiz_data import QUIZ_QUESTIONS

# ID로 질문을 빠르게 찾기 위한 딕셔너리 (메모리에 미리 생성)
QUIZ_QUESTIONS_BY_ID = {q['id']: q for q in QUIZ_QUESTIONS}

def start_quiz(session, genre, difficulty, num_questions):
    """퀴즈를 시작하고, 선택된 질문의 ID 목록과 상태를 세션에 초기화합니다."""
    filtered_questions = [
        q for q in QUIZ_QUESTIONS
        if (genre == 'all' or q['genre'] == genre)
    ]

    random.shuffle(filtered_questions)
    selected_questions = filtered_questions[:num_questions]
    
    # 세션에는 질문의 ID 목록만 저장
    session['quiz_question_ids'] = [q['id'] for q in selected_questions]
    session['current_question_index'] = 0
    session['quiz_score'] = 0
    session['quiz_total_questions'] = len(selected_questions)
    session['selected_genre'] = genre

    return True

def get_current_question_context(session):
    """세션에서 현재 퀴즈 상태를 가져와 템플릿 컨텍스트를 반환합니다."""
    question_ids = session.get('quiz_question_ids')
    current_question_index = session.get('current_question_index')
    quiz_total_questions = session.get('quiz_total_questions')

    if is_quiz_finished(session):
        return None

    # 현재 질문 ID를 가져와서 전체 데이터에서 질문을 찾음
    current_question_id = question_ids[current_question_index]
    current_question = QUIZ_QUESTIONS_BY_ID.get(current_question_id)

    if not current_question:
        # ID에 해당하는 질문을 찾을 수 없는 경우 (데이터 오류 등)
        return None

    context = {
        'question': current_question['question'],
        'options': current_question['options'],
        'current_question_number': current_question_index + 1,
        'total_questions': quiz_total_questions,
        'quiz_active': True,
    }
    return context

def process_answer(session, user_answer):
    """사용자의 답변을 처리하고, 점수를 업데이트하며, 피드백을 세션에 저장합니다."""
    question_ids = session.get('quiz_question_ids')
    current_question_index = session.get('current_question_index')
    
    # 현재 질문 ID를 가져와서 정답을 찾음
    current_question_id = question_ids[current_question_index]
    current_question = QUIZ_QUESTIONS_BY_ID.get(current_question_id)

    if not current_question:
        return

    correct_answer = current_question['answer']

    is_correct = (user_answer == correct_answer)
    if is_correct:
        session['quiz_score'] = session.get('quiz_score', 0) + 1

    session['quiz_feedback'] = {
        'is_correct': is_correct,
        'correct_answer': correct_answer,
        'user_answer': user_answer,
        'character_emotion': '정답' if is_correct else '오답',
    }

def get_feedback(session): # Renamed from get_feedback_and_advance
    """세션에서 피드백을 가져옵니다. (다음 질문으로 인덱스를 이동시키지 않음)"""
    feedback = session.pop('quiz_feedback', None)
    return feedback

def advance_question(session):
    """다음 질문으로 인덱스를 이동시킵니다."""
    session['current_question_index'] = session.get('current_question_index', 0) + 1

def is_quiz_finished(session):
    """퀴즈가 끝났는지 확인합니다."""
    current_question_index = session.get('current_question_index')
    quiz_total_questions = session.get('quiz_total_questions')
    
    if current_question_index is None or quiz_total_questions is None:
        return True # 퀴즈가 시작되지 않았으면 끝난 것으로 간주
        
    return current_question_index >= quiz_total_questions

def save_quiz_result_and_cleanup(session, user):
    """퀴즈 결과를 DB에 저장하고 세션에서 관련 데이터를 삭제합니다."""
    final_score = session.get('quiz_score', 0)
    total_questions = session.get('quiz_total_questions', 0)
    selected_genre = session.get('selected_genre', 'all')

    QuizResult.objects.create(
        user=user,
        genre=selected_genre,
        num_questions=total_questions,
        score=final_score
    )

    # 세션에서 퀴즈 데이터 정리 (키 이름 변경)
    for key in ['quiz_question_ids', 'current_question_index', 'quiz_score', 'quiz_total_questions', 'selected_genre', 'quiz_feedback']:
        session.pop(key, None)
        
    return {'final_score': final_score, 'total_questions': total_questions}