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

    def analyze_image(self, image_data_b64: str, user_message: str, image_content_type: str = 'image/jpeg') -> dict:
        """
        이미지를 분석하고, 상세한 설명을 생성합니다.
        'image_description' 키를 가진 딕셔너리를 반환합니다.
        """
        if not self._client:
            print("OpenAI 클라이언트가 초기화되지 않았습니다.")
            return None

        analysis_prompt = f"""
        제공된 이미지를 자세히 분석하고, 그 내용을 바탕으로 상세한 설명을 생성해주세요.
        설명에는 주요 대상, 배경, 전체적인 분위기, 그리고 사용자의 메시지(\"{user_message}\")와 관련될 수 있는 흥미로운 세부 사항들이 포함되어야 합니다.
        결과는 다른 부가 설명 없이, 이미지에 대한 설명 텍스트만 간결하게 반환해주세요.
        **모든 설명은 반드시 한글로 작성해야 합니다.**
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
                                "image_url": {"url": f"data:{image_content_type};base64,{image_data_b64}"},
                            },
                        ],
                    }
                ],
                max_tokens=500,
            )
            
            choice = response.choices[0]
            message_content = choice.message.content

            if not message_content:
                finish_reason = choice.finish_reason
                print(f"OpenAI 이미지 분석 실패: API가 응답 내용을 반환하지 않았습니다. (종료 사유: {finish_reason})")
                if finish_reason == 'content_filter':
                    print("--- [원인] OpenAI의 콘텐츠 필터링 정책에 의해 응답이 차단되었을 수 있습니다.")
                return None

            # 호출 함수와의 호환성을 위해 텍스트를 딕셔너리 형식으로 래핑
            analysis_result = {"image_description": message_content.strip()}
            print(f"--- [디버그] 이미지 분석 결과 (gpt-4o): {analysis_result} ---")
            return analysis_result

        except json.JSONDecodeError as e:
            print(f"OpenAI 이미지 분석 중 JSON 파싱 오류 발생: {e}")
            print(f"--- [원문] LLM 원본 응답: {message_content}")
            return None
        except Exception as e:
            print(f"OpenAI 이미지 분석 중 오류 발생: {e}")
            return None
