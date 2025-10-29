import json
import os
import torch
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from dotenv import load_dotenv
from ..services import chat_service, emotion_service, finetuning_service, rl_agent_service
from ..models import UserProfile

@login_required
def chat_response(request):
    if request.method == 'POST':
        user_message_text = request.POST.get('message', '')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        image_file = request.FILES.get('image')

        bot_message_text = "죄송합니다. API 응답을 가져오는 데 실패했습니다."
        explanation = ""
        character_emotion = "default"
        bot_message_obj = None
        image_url = None
        action = {} # action 딕셔너리 초기화

        try:
            # 1. 채팅 상호작용 (RL 에이전트의 결정 포함)
            bot_message_text, explanation, bot_message_obj, user_message_obj, action = chat_service.process_chat_interaction(
                request, user_message_text, latitude, longitude, image_file
            )

            # 2. 파인튜닝 데이터 로깅
            finetuning_service.anonymize_and_log_finetuning_data(request, user_message_text, bot_message_text, explanation)

            # 3. 감정 분석
            character_emotion = emotion_service.analyze_emotion(bot_message_text)

            # 4. 감정 분석 결과에 따라 호감도 증감
            user_profile = request.user.profile
            AFFINITY_CHANGE_MAP = {
                "공포": -1, "놀람": -1, "분노": -3, "슬픔": 0,
                "중립": +3, "행복": +5, "혐오": -10,
            }
            affinity_change = AFFINITY_CHANGE_MAP.get(character_emotion, 0)
            user_profile.affinity_score += affinity_change
            user_profile.save()

        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            bot_message_text = f"예상치 못한 오류가 발생했습니다: {e}\n\n--- 상세 오류 정보 ---\n{error_traceback}"
            character_emotion = "중립"

        timestamp = bot_message_obj.timestamp.isoformat() if bot_message_obj else timezone.now().isoformat()
        
        if user_message_obj and user_message_obj.image:
            image_url = user_message_obj.image.url

        # RL 학습을 위해 프론트엔드로 전달할 정보
        state_vector_list = None
        if 'state_vector' in action and hasattr(action['state_vector'], 'numpy'):
            state_vector_list = action['state_vector'].detach().numpy().tolist()

        return JsonResponse({
            'message': bot_message_text, 
            'character_emotion': character_emotion, 
            'explanation': explanation, 
            'timestamp': timestamp,
            'user_image_url': image_url,
            # 보상 시스템을 위한 추가 정보
            'bot_message_id': bot_message_obj.id if bot_message_obj else None,
            'action_id': action.get('action_id'),
            'state_vector': state_vector_list,
        })
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
@require_POST
def record_feedback(request):
    """사용자의 피드백을 받아 RL 에이전트의 학습을 트리거합니다."""
    try:
        data = json.loads(request.body)
        state_vector = data.get('state_vector')
        action_id = data.get('action_id')
        reward = data.get('reward')

        if state_vector is None or action_id is None or reward is None:
            return JsonResponse({'status': 'error', 'message': 'Missing data'}, status=400)

        # 리스트를 다시 토치 텐서로 변환
        state_tensor = torch.tensor(state_vector, dtype=torch.float32)

        # RL 에이전트의 학습 함수 호출
        rl_agent_service.agent.learn(state_tensor, action_id, reward)

        return JsonResponse({'status': 'success', 'message': 'Feedback recorded'})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)