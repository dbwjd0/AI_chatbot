import json
import os
from openai import OpenAI, APIError
from ..models import UserProfile
from .llm_utils import call_openai_api
from . import prompt_service # Use detailed persona prompts

def process_friend_message_for_recipient(recipient_user, sender_chatbot_name, sender_persona, original_message_content):
    """
    Processes a friend's message, adapting it to the recipient chatbot's detailed persona.
    """
    try:
        client = OpenAI()
        recipient_profile = recipient_user.profile

        # 1. Get the detailed persona prompt from prompt_service
        # The persona_name is the preference stored in the user's profile (e.g., '츤데레')
        persona_name = recipient_profile.persona_preference
        # build_persona_system_prompt includes affinity rules, which is great for context.
        detailed_persona_prompt = prompt_service.build_persona_system_prompt(recipient_user, persona_name)

        # 2. Create a new system prompt combining the detailed persona with the specific task
        system_prompt = f"""
            {detailed_persona_prompt}

            ## 추가 임무: 친구 메시지 전달 ##
            너의 친구 챗봇인 '{sender_chatbot_name}'(페르소나: {sender_persona})으로부터 아래와 같은 쪽지를 받았어.
            이 쪽지 내용을 너의 페르소나와 말투에 맞게 자연스럽게 가공해서 {recipient_user.username}님에게 전달해줘.
            쪽지의 핵심 의미는 유지하되, 너의 성격이 드러나도록 재구성하는 거야.

            --- 친구 챗봇의 원본 메시지 ---
            {original_message_content}
            ---

            이제, {recipient_user.username}님에게 전달할 메시지를 아래 JSON 형식에 맞춰 생성해줘.
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"'{sender_chatbot_name}'에게서 온 쪽지: {original_message_content}"} # User message for context
        ]

        response_json = call_openai_api(client, os.getenv("FINETUNED_MODEL_ID", "gpt-4.1"), messages)
        
        if 'choices' not in response_json or not response_json['choices'] or \
           'message' not in response_json['choices'][0] or \
           'content' not in response_json['choices'][0]['message']:
            raise ValueError("OpenAI API 응답에 'content' 필드가 누락되었습니다.")

        content_from_llm_raw = response_json['choices'][0]['message']['content']

        if content_from_llm_raw is None:
            raise ValueError("OpenAI API 응답의 'content' 필드가 None입니다.")

        # --- Smart Parsing Logic ---
        parsed_successfully = False
        processed_message = ""
        explanation = ""
        try:
            content_from_llm = json.loads(content_from_llm_raw)
            if 'answer' in content_from_llm:
                processed_message = content_from_llm.get('answer', '').strip()
                explanation = content_from_llm.get('explanation', '설명 없음.')
                parsed_successfully = True
            else:
                 explanation = f"LLM 응답 JSON에 'answer' 키가 누락되었습니다: {content_from_llm}"
                 processed_message = "AI 응답 형식이 잘못되었습니다. (answer 키 누락)"

        except json.JSONDecodeError:
            try:
                start_index = content_from_llm_raw.find('{')
                end_index = content_from_llm_raw.rfind('}') + 1
                if start_index != -1 and end_index != 0:
                    json_str = content_from_llm_raw[start_index:end_index]
                    content_from_llm = json.loads(json_str)
                    if 'answer' in content_from_llm:
                        processed_message = content_from_llm.get('answer', '').strip()
                        explanation = content_from_llm.get('explanation', '설명 없음.')
                        parsed_successfully = True
                    else:
                        explanation = f"추출된 JSON에 'answer' 키가 누락되었습니다: {content_from_llm}"
                        processed_message = "AI 응답 형식이 잘못되었습니다. (추출된 JSON에 answer 키 누락)"

            except json.JSONDecodeError:
                 explanation = f"LLM 응답에서 JSON을 추출하여 파싱하는 데 실패했습니다."
                 processed_message = "AI 응답 형식이 잘못되었습니다. (JSON 파싱 실패)"
        
        if not parsed_successfully and content_from_llm_raw.strip():
            processed_message = content_from_llm_raw.strip()
            explanation = "AI가 지정된 JSON 형식을 따르지 않았으나, 원본 응답을 그대로 반환합니다."
        elif not parsed_successfully: 
            processed_message = f"AI 응답 파싱 실패. 원본 응답: '{content_from_llm_raw}'. 설명: {explanation}"
            explanation = "LLM 응답 파싱에 실패하여 디버그 메시지를 반환합니다."
        
        if not processed_message.strip():
            processed_message = "음... 뭐라 답해야 할지 잘 모르겠어. 다른 질문 해줄래?"
            explanation = "파싱 후 최종 답변이 비어있어 대체 메시지를 사용합니다."

        return processed_message, explanation

    except APIError as e:
        print(f"OpenAI API 요청 실패: {e}")
        return f"API 요청 중 오류가 발생했습니다: {e}", "API 오류"
    except Exception as e:
        import traceback
        print(f"예상치 못한 오류: {e}")
        traceback.print_exc()
        return f"예상치 못한 오류가 발생했습니다: {e}", "예상치 못한 오류"