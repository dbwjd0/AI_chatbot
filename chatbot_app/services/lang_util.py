# chatbot_app/services/lang_util.py
import os
import json
from typing import List
from openai import OpenAI
from django.utils.translation import get_language_info
from django.utils.translation import gettext as gt
from django.core.cache import cache # Import Django's cache framework

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

def translate_from_korean_batch(texts: List[str], target_lang: str) -> List[str]:
    """한국어 텍스트 리스트를 대상 언어로 일괄 번역합니다."""
    if not texts:
        return []

    # Generate a cache key based on the texts and target_lang
    cache_key = f"translation_batch:{hash(json.dumps(texts, sort_keys=True))}:{target_lang}"
    cached_result = cache.get(cache_key)
    if cached_result:
        print(f"--- [일괄 번역 로그] 캐시된 결과 반환 ({len(texts)}개 메시지) ---")
        return cached_result

    target_lang_name = get_language_info(target_lang).get('name_local', target_lang)

    if target_lang == 'ja':
        tone_instruction = "natural, informal Japanese (タメ口)"
    else:  # 기본값은 영어
        tone_instruction = "natural, informal English"

    # LLM에 입력으로 제공할 JSON 배열 생성
    input_json = json.dumps(texts, ensure_ascii=False)

    prompt = f"""
        You are an expert translator. Your sole job is to translate a JSON array of Korean strings into {tone_instruction}.
        The original Korean text is informal (반말), so the translation should capture that informal, friendly tone.
        You will receive a JSON array of strings in the user message.
        You MUST return a single JSON object with one key, \"translations\", which contains a JSON array of the translated strings. The returned array must have the exact same number of elements as the input array.
        Each string in the \"translations\" array must be the translation of the string at the same index in the input array.
        Do not add any other text or explanations.

        Example user input: [\"안녕\", \"오늘 날씨 어때?\"]
        Example assistant output for Japanese: {{"translations": ["やあ", "今日天気どう？"]}}
    """

    try:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": input_json}
            ],
            temperature=0.1,
            max_tokens=2500,  # 여러 텍스트를 번역하므로 토큰 수를 늘림
            response_format={"type": "json_object"},
        )
        response_content = response.choices[0].message.content
        response_data = json.loads(response_content)
        translated_texts = response_data.get("translations", [])

        if len(translated_texts) == len(texts):
            print(f"--- [일괄 번역 로그] {len(texts)}개 메시지 번역 완료 ---")
            cache.set(cache_key, translated_texts, 3600) # Cache for 1 hour
            return translated_texts
        else:
            print(f"--- [번역 오류] 일괄 번역 결과 개수({len(translated_texts)})가 원본({len(texts)})과 다릅니다. ---")
            return texts  # Fallback to original texts
            
    except Exception as e:
        print(f"--- [번역 오류] 일괄 번역 API 호출 실패: {e} ---")
        return texts  # Fallback to original texts
