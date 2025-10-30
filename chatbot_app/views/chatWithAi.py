import json
import os
import torch
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from ..services import chat_service, emotion_service, finetuning_service, rl_agent_service
from ..models import UserProfile

# PPO 학습을 위한 설정
TRAJECTORY_LENGTH_FOR_LEARNING = 5

@login_required
def chat_response(request):
    if request.method == 'POST':
        user_message_text = request.POST.get('message', '')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        image_file = request.FILES.get('image')

        # 1. 사용자 메시지 감정 분석 (최적화: 한번만 실행)
        current_user_emotion = emotion_service.analyze_emotion(user_message_text, speaker="User")

        # --- PPO Trajectory 수집 및 암시적 보상 계산 --- #
        trajectory = request.session.get('ppo_trajectory', [])
        
        if trajectory: # 이전 턴의 데이터가 있다면
            try:
                implicit_reward = 0.0
                if current_user_emotion == '행복':
                    implicit_reward = 0.3
                elif current_user_emotion in ['놀람', '중립', '슬픔']:
                    implicit_reward = 0.0
                elif current_user_emotion in ['공포', '분노']:
                    implicit_reward = -0.3
                elif current_user_emotion == '혐오':
                    implicit_reward = -0.5
                
                if implicit_reward != 0.0:
                    trajectory[-1]['reward'] = implicit_reward

            except Exception as e:
                print(f"--- [PPO] 암시적 보상 계산 중 오류: {e} ---")

        # --- 채팅 상호작용 시작 ---
        bot_message_text = "죄송합니다. API 응답을 가져오는 데 실패했습니다."
        explanation = ""
        character_emotion = "default"
        bot_message_obj = None
        image_url = None
        action_data = {} 

        try:
            # 2. 채팅 상호작용 (RL 에이전트의 결정 포함) - 분석된 사용자 감정 전달
            bot_message_text, explanation, bot_message_obj, user_message_obj, action_data = chat_service.process_chat_interaction(
                request, user_message_text, user_emotion=current_user_emotion, latitude=latitude, longitude=longitude, image_file=image_file
            )
            finetuning_service.anonymize_and_log_finetuning_data(request, user_message_text, bot_message_text, explanation)
            
            # 3. 봇 메시지 감정 분석
            character_emotion = emotion_service.analyze_emotion(bot_message_text, speaker="Bot")

            # 4. 호감도 증감
            user_profile = request.user.profile
            AFFINITY_CHANGE_MAP = {"공포": -1, "놀람": -1, "분노": -3, "슬픔": 0, "중립": +3, "행복": +5, "혐오": -10}
            user_profile.affinity_score += AFFINITY_CHANGE_MAP.get(character_emotion, 0)
            user_profile.save()

        except Exception as e:
            import traceback
            bot_message_text = f"예상치 못한 오류: {e}\n\n{traceback.format_exc()}"
            character_emotion = "중립"

        # --- PPO Trajectory에 현재 턴의 경험 추가 ---
        if action_data:
            experience = {
                'state': action_data.get('state_vector'),
                'action': action_data.get('action'),
                'log_prob': action_data.get('action_log_prob'),
                'value': action_data.get('state_value'),
                'reward': 0, # 다음 턴에 채워짐
                'done': False
            }
            trajectory.append(experience)

        # --- 학습 트리거 ---
        if len(trajectory) >= TRAJECTORY_LENGTH_FOR_LEARNING:
            try:
                print(f"--- [PPO] Trajectory가 {len(trajectory)}에 도달하여 학습을 시작합니다. ---")
                rl_agent_service.agent.learn(trajectory)
                trajectory = [] # 학습 후 trajectory 초기화
            except Exception as e:
                print(f"--- [PPO] 정기 학습 중 오류 발생: {e} ---")
                trajectory = [] # 오류 발생 시에도 초기화

        request.session['ppo_trajectory'] = trajectory

        # --- 최종 응답 반환 ---
        timestamp = bot_message_obj.timestamp.isoformat() if bot_message_obj else timezone.now().isoformat()
        if user_message_obj and user_message_obj.image:
            image_url = user_message_obj.image.url

        return JsonResponse({
            'message': bot_message_text, 
            'character_emotion': character_emotion, 
            'explanation': explanation, 
            'timestamp': timestamp,
            'user_image_url': image_url,
            'bot_message_id': bot_message_obj.id if bot_message_obj else None,
            # 프론트엔드 피드백용 데이터는 마지막 경험의 데이터를 사용
            'action': trajectory[-1]['action'] if trajectory else None,
            'state_vector': trajectory[-1]['state'] if trajectory else None,
        })

    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
@require_POST
def record_feedback(request):
    """사용자의 명시적 피드백을 받아 PPO 에이전트의 학습을 즉시 트리거합니다."""
    try:
        data = json.loads(request.body)
        explicit_reward = float(data['reward'])

        trajectory = request.session.get('ppo_trajectory', [])
        if not trajectory:
            return JsonResponse({'status': 'error', 'message': '학습할 데이터가 없습니다.'}, status=400)

        # 마지막 행동에 대한 보상을 명시적 보상으로 설정
        trajectory[-1]['reward'] = explicit_reward
        # 대화가 끝난 것으로 간주 (하나의 에피소드 종료)
        trajectory[-1]['done'] = True 

        print(f"--- [PPO] 명시적 보상({explicit_reward})으로 즉시 학습을 시작합니다. ---")
        rl_agent_service.agent.learn(trajectory)
        
        # 학습 후 trajectory 초기화
        request.session['ppo_trajectory'] = []

        return JsonResponse({'status': 'success', 'message': 'Feedback recorded and learned'})
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return JsonResponse({'status': 'error', 'message': f'Invalid request data: {e}'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)