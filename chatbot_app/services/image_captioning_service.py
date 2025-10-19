import os
import json
import base64
from openai import OpenAI

class ImageCaptioningService:
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ImageCaptioningService, cls).__new__(cls)
            # 클라이언트 생성 시 초기화합니다.
            # OpenAI 클라이언트는 자동으로 OPENAI_API_KEY 환경 변수를 찾습니다.
            try:
                cls._client = OpenAI()
                print("OpenAI 클라이언트가 성공적으로 초기화되었습니다.")
            except Exception as e:
                cls._client = None
                print(f"OpenAI 클라이언트 초기화 실패: {e}")
        return cls._instance

    def analyze_image(self, image_data_b64: str, user_message: str) -> dict:
        """
        이미지를 분석하고, 상세한 설명과 답변 초안을 생성합니다.
        'image_description'과 'draft_response' 키를 가진 딕셔너리를 반환합니다.
        """
        if not self._client:
            print("OpenAI 클라이언트가 초기화되지 않았습니다.")
            return None

        analysis_prompt = f"""
        제공된 이미지를 자세히 분석해주세요. 주요 대상, 배경, 전체적인 분위기, 그리고 흥미로운 세부 사항들을 묘사해주세요.
        이 분석과 사용자의 메시지(\"{user_message}\")를 바탕으로, 간단하고 사실에 기반한 답변의 초안을 작성해주세요.
        결과는 "image_description"과 "draft_response" 두 개의 키를 가진 JSON 객체로 출력해주세요.
        **모든 설명과 답변은 반드시 한글로 작성해야 합니다.**
        """

        try:
            response = self._client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": analysis_prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{image_data_b64}"},
                            },
                        ],
                    }
                ],
                max_tokens=500,
                response_format={"type": "json_object"},
            )
            
            analysis_result = json.loads(response.choices[0].message.content)
            print(f"--- [디버그] 이미지 분석 결과 (gpt-4o): {analysis_result} ---")
            return analysis_result

        except Exception as e:
            print(f"OpenAI 이미지 분석 중 오류 발생: {e}")
            return None
