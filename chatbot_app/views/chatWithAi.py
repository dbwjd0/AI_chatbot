import json
import os
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from dotenv import load_dotenv
from ..services import chat_service, emotion_service, finetuning_service
from ..models import UserProfile

@login_required
def chat_response(request):
    if request.method == 'POST':
        user_message_text = request.POST.get('message', '')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        image_file = request.FILES.get('image') # FormData에서 이미지 파일 가져오기

        bot_message_text = "죄송합니다. API 응답을 가져오는 데 실패했습니다."
        explanation = ""
        character_emotion = "default"
        bot_message_obj = None
        image_url = None

        try:
            # 1. 채팅 상호작용 (컨텍스트 생성, API 호출, 응답 처리, 기억 저장)
            bot_message_text, explanation, bot_message_obj, user_message_obj = chat_service.process_chat_interaction(
                request, user_message_text, latitude, longitude, image_file
            )

            # 2. 파인튜닝 데이터 로깅
            finetuning_service.anonymize_and_log_finetuning_data(request, user_message_text, bot_message_text, explanation)

            # 3. 감정 분석
            character_emotion = emotion_service.analyze_emotion(bot_message_text)

            # 4. 감정 분석 결과에 따라 호감도 증감
            user_profile = request.user.profile
            AFFINITY_CHANGE_MAP = {
                "공포": -1,
                "놀람": -1,
                "분노": -3,
                "슬픔": 0,
                "중립": +3,
                "행복": +5,
                "혐오": -10,
            }
            affinity_change = AFFINITY_CHANGE_MAP.get(character_emotion, 0) # 매핑되지 않은 감정은 0으로 처리
            user_profile.affinity_score += affinity_change
            user_profile.save()

        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc() # traceback을 문자열로 가져옵니다.
            # 콘솔 출력은 문제가 있으므로, bot_message_text에 상세 traceback을 포함시킵니다.
            bot_message_text = f"예상치 못한 오류가 발생했습니다: {e}\n\n--- 상세 오류 정보 ---\n{error_traceback}"
            character_emotion = "중립" # 오류 발생 시 기본 감정은 '중립'으로 설정

        timestamp = bot_message_obj.timestamp.isoformat() if bot_message_obj else timezone.now().isoformat()
        
        # 사용자가 보낸 이미지의 URL을 응답에 포함
        if user_message_obj and user_message_obj.image:
            image_url = user_message_obj.image.url

        return JsonResponse({
            'message': bot_message_text, 
            'character_emotion': character_emotion, 
            'explanation': explanation, 
            'timestamp': timestamp,
            'user_image_url': image_url 
        })
    return JsonResponse({'error': 'Invalid request'}, status=400)