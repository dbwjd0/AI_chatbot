import os
import base64
from openai import OpenAI

class ImageCaptioningService:
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ImageCaptioningService, cls).__new__(cls)
            # Initialize the client upon creation.
            # The OpenAI client automatically looks for the OPENAI_API_KEY env var.
            try:
                cls._client = OpenAI()
                print("OpenAI client initialized successfully.")
            except Exception as e:
                cls._client = None
                print(f"Failed to initialize OpenAI client: {e}")
        return cls._instance

    def generate_caption(self, image_data_b64: str) -> str:
        """
        Generates a caption for a given image using the OpenAI gpt-4o model.
        """
        if not self._client:
            return "OpenAI 클라이언트가 초기화되지 않았습니다. OPENAI_API_KEY 환경 변수를 확인하세요."

        try:
            response = self._client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "이 이미지를 한 문장으로 설명해줘."},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{image_data_b64}"},
                            },
                        ],
                    }
                ],
                max_tokens=100,
            )
            caption = response.choices[0].message.content
            return caption.strip()

        except Exception as e:
            print(f"Error generating caption with OpenAI: {e}")
            return "이미지 캡션을 생성하는 데 실패했습니다."