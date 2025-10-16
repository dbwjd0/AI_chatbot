from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration
import base64
import io

class ImageCaptioningService:
    _instance = None
    _processor = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ImageCaptioningService, cls).__new__(cls)
            cls._instance._load_model()
        return cls._instance

    def _load_model(self):
        """Loads the BLIP model and processor."""
        if self._processor is None:
            print("Loading BLIP processor...")
            self._processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
            print("BLIP processor loaded.")
        if self._model is None:
            print("Loading BLIP model...")
            self._model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
            print("BLIP model loaded.")

    def generate_caption(self, image_data_b64: str) -> str:
        """
        Generates a caption for a given image.

        Args:
            image_data_b64: Base64 encoded image data (JPEG).

        Returns:
            A string caption for the image.
        """
        if not self._processor or not self._model:
            self._load_model()

        try:
            # Decode base64 image data
            image_bytes = base64.b64decode(image_data_b64)
            raw_image = Image.open(io.BytesIO(image_bytes)).convert('RGB')

            # unconditional image captioning
            inputs = self._processor(raw_image, return_tensors="pt")
            out = self._model.generate(**inputs)
            caption = self._processor.decode(out[0], skip_special_tokens=True)
            return caption
        except Exception as e:
            print(f"Error generating caption: {e}")
            return "이미지 캡션을 생성하는 데 실패했습니다."
