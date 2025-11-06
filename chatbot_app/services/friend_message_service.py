import json
import os
from openai import OpenAI, APIError
from typing import List, Dict, Any, Tuple
from ..models import UserProfile, FriendMessage
from .llm_utils import call_openai_api
from . import prompt_service
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext as gt

def process_friend_messages_in_batch(recipient_user, messages: List[FriendMessage]) -> List[Dict[str, Any]]:
    """%s""" % _("여러 친구 메시지를 한 번의 API 호출로 수신자의 챗봇 페르소나에 맞게 조정합니다.")
    if not messages:
        return []

    try:
        client = OpenAI()
        recipient_profile = recipient_user.profile
        persona_name = recipient_profile.persona_preference
        detailed_persona_prompt = prompt_service.build_persona_system_prompt(recipient_user, persona_name)

        # 프롬프트를 위한 메시지 JSON 배열 생성 (보낸 사람 username 포함)
        messages_json_array = json.dumps([
            {
                "id": msg.id,
                "sender_username": msg.sender.username, # 보낸 친구의 아이디 추가
                "sender_chatbot_name": msg.sender_chatbot_name,
                "sender_persona": msg.sender_persona,
                "original_content": msg.message_content
            } for msg in messages
        ], ensure_ascii=False)

        system_prompt = gt("""
            {detailed_persona_prompt}

            ## 🤯 매우 복잡한 추가 임무: 친구의 원본 메시지를 보고, 친구 챗봇의 1차 가공을 추론한 뒤, 너의 스타일로 2차 가공하여 전달 ##

            너는 지금부터 매우 지능적인 추론을 해야 하는 중간 다리 역할을 맡았어.

            너의 사용자({recipient_user.username})의 친구({{{{sender_username}}}})가 자신의 챗봇({{{{sender_chatbot_name}}}})에게 아래 '친구의 원본 메시지'를 말했어.
            그 메시지는 가공되지 않은 **완전한 원본**이야.

            너의 임무는 두 단계에 걸쳐 메시지를 가공하는 거야.

            **1단계: 친구 챗봇의 생각 읽기 (추론)**
            - 먼저, 친구 챗봇의 페르소나(`sender_persona`)를 분석해.
            - 그 페르소나를 가진 챗봇이라면, '친구의 원본 메시지'를 어떻게 가공해서 너에게 전달했을지 **상상하고 추론**해야 해.

            **2단계: 너의 스타일로 변환 (가공)**
            - 이제, 1단계에서 네가 추론한 '가공되었을 법한 메시지'를, **너의 페르소나와 말투**에 맞게 **다시 한번** 자연스럽게 가공해야 해.
            - 최종적으로 너의 주인인 {recipient_user.username}님에게 전달될 메시지는 **오직 너의 스타일**이어야만 해.

            **예시:**
            - **친구 원본 메시지:** "나 오늘 너무 피곤해. 일정이 너무 많았어."
            - **친구 챗봇 페르소나:** '사무적'
            - **(너의 추론):** '사무적인 챗봇이라면 \'오늘 사용자께서 피로도가 높음. 다수의 일정 소화.\' 라고 전달했겠군.'
            - **너의 페르소나:** '애교 많음'
            - **(너의 최종 결과):** "주인님! {{{{sender_username}}}}님이 오늘 너무너무 피곤하대! 일 때문에 완전 지쳤나 봐 ㅠㅠ"

            --- 친구들의 원본 메시지 목록 (JSON 배열) ---
            {messages_json_array}
            ---

            이제, 위와 같은 복잡한 추론 과정을 거쳐, {recipient_user.username}님에게 전달할 최종 메시지들을 아래 JSON 형식에 맞춰 생성해줘.
            'explanation'에는 네가 어떤 추론 과정을 거쳤는지 간단히 설명해줘. (예: "사무적인 친구 챗봇의 메시지를 제 애교있는 말투로 바꿨어요!")

            응답 형식:
            {{
              "processed_messages": [
                {{
                  "id": <원본 메시지 ID>,
                  "answer": "<가공된 메시지 내용>",
                  "explanation": "<가공 이유 설명>"
                }},
                ...
              ]
            }}
        """).format(detailed_persona_prompt=detailed_persona_prompt, recipient_user=recipient_user, messages_json_array=messages_json_array)

        llm_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": gt("위 쪽지들을 내 페르소나에 맞게 모두 가공해서 전달해줘.")}
        ]
        response_json = call_openai_api(client, os.getenv("FINETUNED_MODEL_ID", "gpt-4.1"), llm_messages)

        if 'choices' not in response_json or not response_json['choices'] or \
           'message' not in response_json['choices'][0] or \
           'content' not in response_json['choices'][0]['message']:
            raise ValueError(gt("OpenAI API 응답에 'content' 필드가 누락되었습니다."))

        content_from_llm_raw = response_json['choices'][0]['message']['content']

        if content_from_llm_raw is None:
            raise ValueError(gt("OpenAI API 응답의 'content' 필드가 None입니다."))

        # --- 배치 응답을 위한 스마트 파싱 로직 ---
        try:
            # 전체 문자열을 JSON으로 파싱 시도
            parsed_data = json.loads(content_from_llm_raw)
            if 'processed_messages' in parsed_data and isinstance(parsed_data['processed_messages'], list):
                # 응답이 입력과 동일한 수의 메시지를 가지고 있는지 확인
                if len(parsed_data['processed_messages']) == len(messages):
                    return parsed_data['processed_messages']
                else:
                    print(gt("경고: LLM이 다른 수의 메시지를 반환했습니다. 입력: {input_count}, 출력: {output_count}").format(input_count=len(messages), output_count=len(parsed_data['processed_messages'])))
                    # 여기서 폴백 또는 오류 처리를 구현할 수 있습니다.
                    return [] # 실패를 나타내기 위해 빈 리스트 반환
            else:
                raise ValueError(gt("JSON 응답에 'processed_messages' 키가 없거나 리스트가 아닙니다."))

        except json.JSONDecodeError:
            # 잘못된 형식의 JSON에 대한 폴백
            print(gt("오류: LLM 응답에서 JSON을 디코딩하지 못했습니다. 원시 콘텐츠: {content_from_llm_raw}").format(content_from_llm_raw=content_from_llm_raw))
            return [] # 실패를 나타내기 위해 빈 리스트 반환

    except APIError as e:
        print(gt("OpenAI API 요청 실패: {error_message}").format(error_message=e))
        return []
    except Exception as e:
        import traceback
        print(gt("예상치 못한 오류: {error_message}").format(error_message=e))
        traceback.print_exc()
        return []

# 이전 함수는 참조용으로 유지되지만 더 이상 사용되지 않습니다.
def process_friend_message_for_recipient(recipient_user, sender_chatbot_name, sender_persona, original_message_content):
    """%s""" % _("친구의 메시지를 수신자 챗봇의 상세 페르소나에 맞게 조정합니다.")
    try:
        client = OpenAI()
        recipient_profile = recipient_user.profile

        # 1. prompt_service에서 상세 페르소나 프롬프트를 가져옵니다.
        # persona_name은 사용자의 프로필에 저장된 선호도입니다 (예: '츤데레').
        persona_name = recipient_profile.persona_preference
        # build_persona_system_prompt는 친밀도 규칙을 포함하므로 컨텍스트에 유용합니다.
        detailed_persona_prompt = prompt_service.build_persona_system_prompt(recipient_user, persona_name)

        # 2. 상세 페르소나와 특정 작업을 결합한 새 시스템 프롬프트를 만듭니다.
        system_prompt = gt("""
            {detailed_persona_prompt}

            ## 추가 임무: 친구 메시지 전달 ##
            너의 친구 챗봇인 '{sender_chatbot_name}'(페르소나: {sender_persona})으로부터 아래와 같은 쪽지를 받았어.
            이 쪽지 내용을 너의 페르소나와 말투에 맞게 자연스럽게 가공해서 {recipient_user.username}님에게 전달해줘.
            쪽지의 핵심 의미는 유지하되, 너의 성격이 드러나도록 재구성하는 거야.

            --- 친구 챗봇의 원본 메시지 ---
            {original_message_content}
            ---

            이제, {recipient_user.username}님에게 전달할 메시지를 아래 JSON 형식에 맞춰 생성해줘.
        """).format(detailed_persona_prompt=detailed_persona_prompt, sender_chatbot_name=sender_chatbot_name, sender_persona=sender_persona, original_message_content=original_message_content, recipient_user=recipient_user)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": gt("'{sender_chatbot_name}'에게서 온 쪽지: {original_message_content}").format(sender_chatbot_name=sender_chatbot_name, original_message_content=original_message_content)} # 컨텍스트를 위한 사용자 메시지
        ]

        response_json = call_openai_api(client, os.getenv("FINETUNED_MODEL_ID", "gpt-4.1"), messages)
        
        if 'choices' not in response_json or not response_json['choices'] or \
           'message' not in response_json['choices'][0] or \
           'content' not in response_json['choices'][0]['message']:
            raise ValueError(gt("OpenAI API 응답에 'content' 필드가 누락되었습니다."))

        content_from_llm_raw = response_json['choices'][0]['message']['content']

        if content_from_llm_raw is None:
            raise ValueError(gt("OpenAI API 응답의 'content' 필드가 None입니다."))

        # --- 스마트 파싱 로직 ---
        parsed_successfully = False
        processed_message = ""
        explanation = ""
        try:
            content_from_llm = json.loads(content_from_llm_raw)
            if 'answer' in content_from_llm:
                processed_message = content_from_llm.get('answer', '').strip()
                explanation = content_from_llm.get('explanation', gt('설명 없음.'))
                parsed_successfully = True
            else:
                 explanation = gt("LLM 응답 JSON에 'answer' 키가 누락되었습니다: {content_from_llm}").format(content_from_llm=content_from_llm)
                 processed_message = gt("AI 응답 형식이 잘못되었습니다. (answer 키 누락)")

        except json.JSONDecodeError:
            try:
                start_index = content_from_llm_raw.find('{')
                end_index = content_from_llm_raw.rfind('}') + 1
                if start_index != -1 and end_index != 0:
                    json_str = content_from_llm_raw[start_index:end_index]
                    content_from_llm = json.loads(json_str)
                    if 'answer' in content_from_llm:
                        processed_message = content_from_llm.get('answer', '').strip()
                        explanation = content_from_llm.get('explanation', gt('설명 없음.'))
                        parsed_successfully = True
                    else:
                        explanation = gt("추출된 JSON에 'answer' 키가 누락되었습니다: {content_from_llm}").format(content_from_llm=content_from_llm)
                        processed_message = gt("AI 응답 형식이 잘못되었습니다. (추출된 JSON에 answer 키 누락)")

            except json.JSONDecodeError:
                 explanation = gt("LLM 응답에서 JSON을 추출하여 파싱하는 데 실패했습니다.")
                 processed_message = gt("AI 응답 형식이 잘못되었습니다. (JSON 파싱 실패)")
        
        if not parsed_successfully and content_from_llm_raw.strip():
            processed_message = content_from_llm_raw.strip()
            explanation = gt("AI가 지정된 JSON 형식을 따르지 않았으나, 원본 응답을 그대로 반환합니다.")
        elif not parsed_successfully: 
            processed_message = gt("AI 응답 파싱 실패. 원본 응답: '{content_from_llm_raw}'. 설명: {explanation}").format(content_from_llm_raw=content_from_llm_raw, explanation=explanation)
            explanation = gt("LLM 응답 파싱에 실패하여 디버그 메시지를 반환합니다.")
        
        if not processed_message.strip():
            processed_message = gt("음... 뭐라 답해야 할지 잘 모르겠어. 다른 질문 해줄래?")
            explanation = gt("파싱 후 최종 답변이 비어있어 대체 메시지를 사용합니다.")

        return processed_message, explanation

    except APIError as e:
        print(gt("OpenAI API 요청 실패: {error_message}").format(error_message=e))
        return gt("API 요청 중 오류가 발생했습니다: {error_message}").format(error_message=e), gt("API 오류")
    except Exception as e:
        import traceback
        print(gt("예상치 못한 오류: {error_message}").format(error_message=e))
        traceback.print_exc()
        return gt("예상치 못한 오류가 발생했습니다: {error_message}").format(error_message=e), gt("예상치 못한 오류")