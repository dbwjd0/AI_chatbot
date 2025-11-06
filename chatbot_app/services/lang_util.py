# chatbot_app/services/lang_util.py
import os
from openai import OpenAI
from django.utils.translation import get_language_info
from django.utils.translation import gettext as gt

def _call_gpt_for_translation(prompt: str, text_to_translate: str) -> str:
    """OpenAI API를 호출하여 번역을 수행하는 내부 헬퍼 함수"""
    try:
        # OpenAI 클라이언트는 자동으로 OPENAI_API_KEY 환경 변수를 사용합니다.
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4.1",  # 사용자가 요청한 모델
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text_to_translate}
            ],
            temperature=0.1,  # 번역 작업이므로 일관성을 위해 온도를 낮게 설정
            max_tokens=1500,
        )
        translated_text = response.choices[0].message.content.strip()
        print(f"--- [번역 로그] 원문: '{text_to_translate[:30]}...' -> 번역: '{translated_text[:30]}...' ---")
        return translated_text
    except Exception as e:
        print(f"--- [번역 오류] OpenAI API 호출 실패: {e} ---")
        # 오류 발생 시 원본 텍스트를 그대로 반환하여 기능 중단을 방지
        return text_to_translate

def translate_to_korean(text: str, source_lang: str) -> str:
    """주어진 텍스트를 한국어로 번역합니다."""
    # get_language_info를 사용하여 'en' 같은 코드 대신 'English' 같은 전체 이름을 얻습니다.
    source_lang_name = get_language_info(source_lang).get('name_local', source_lang)
    
    prompt = gt("""
        You are an expert translator.
        Your primary task is to translate the provided text into natural, informal Korean (반말).
        However, before translating, first identify the original language of the text.
        If the text is already in Korean, simply return the original Korean text without any changes or additional comments.
        If the text is in {source_lang_name} (or any other language), then translate it into natural, informal Korean (반말).
        Do not add any explanations or extra text. Just provide the translated Korean text (or the original Korean text if no translation was needed).
    """).format(source_lang_name=source_lang_name)
    
    return _call_gpt_for_translation(prompt, text)

def translate_from_korean(text: str, target_lang: str) -> str:
    """한국어 텍스트를 대상 언어로 번역합니다."""
    target_lang_name = get_language_info(target_lang).get('name_local', target_lang)

    # 목표 언어에 따라 적절한 톤을 지시합니다.
    if target_lang == 'ja':
        tone_instruction = "natural, informal Japanese (タメ口)"
    else:  # 기본값은 영어
        tone_instruction = "natural, informal English"

    prompt = gt("""
        You are an expert translator. Your sole job is to translate the following Korean text into {tone_instruction}.
        The original Korean text is informal (반말), so the translation should capture that informal, friendly tone.
        Do not add any explanations or extra text. Just provide the translated text.
    """).format(tone_instruction=tone_instruction)
    
    return _call_gpt_for_translation(prompt, text)
