import os
from typing import Dict, Any
from openai import OpenAI

def call_openai_api(client: OpenAI, model_to_use: str, messages: list) -> Dict[str, Any]:
    """OpenAI API를 호출하고 응답 JSON을 반환합니다."""
    print(f"--- 사용 모델: {model_to_use} ---")
    response = client.chat.completions.create(
        model=model_to_use,
        messages=messages,
        temperature=0.7,
        top_p=0.9,
        frequency_penalty=0.2,
        presence_penalty=0.1,
        response_format={"type": "json_object"}
    )
    return response.model_dump()
