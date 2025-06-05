"""Utility for performing OCR on images using Tesseract or Google Cloud Vision.

This module provides an asynchronous interface for performing OCR. By
default it uses ``pytesseract`` for local OCR processing but can optionally
integrate with Google Cloud Vision if credentials are available.
"""

import logging
import asyncio
from io import BytesIO
from typing import Optional, Union

from PIL import Image
import pytesseract

try:  # Optional Google Vision support
    from google.cloud import vision
except Exception:  # pragma: no cover - optional dependency may be missing
    vision = None

logger = logging.getLogger(__name__)

class OCRProcessor:
    """OCR processor using Tesseract or Google Cloud Vision."""

    def __init__(
        self,
        tesseract_cmd: Optional[str] = None,
        use_google_vision: bool = False,
    ) -> None:
        """Initialise the processor.

        Parameters
        ----------
        tesseract_cmd:
            Optional path to the ``tesseract`` executable. This can be provided
            when the binary is not available on the system ``PATH``.
        """

        self.logger = logging.getLogger(__name__ + ".OCRProcessor")
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

        self.use_google_vision = bool(use_google_vision and vision)
        if self.use_google_vision:
            self.vision_client = vision.ImageAnnotatorClient()  # type: ignore
            self.logger.info("OCRProcessor initialized using Google Vision API.")
        else:
            self.logger.info("OCRProcessor initialized using pytesseract.")

    async def _image_to_text(self, img: Image.Image) -> str:
        """Run OCR in a thread to avoid blocking the event loop."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, pytesseract.image_to_string, img)

    async def _vision_to_text(self, img_bytes: bytes) -> str:
        """Run Google Vision OCR in a thread."""
        if not self.use_google_vision:
            return ""

        def _call() -> str:
            image = vision.Image(content=img_bytes)
            response = self.vision_client.text_detection(image=image)
            if response.error.message:
                raise RuntimeError(response.error.message)
            return response.full_text_annotation.text if response.full_text_annotation else ""

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _call)

    async def process_image(self, image_data: Union[bytes, str], image_url: Optional[str] = None) -> Optional[str]:
        """Extract text from image bytes or a file path.

        Parameters
        ----------
        image_data:
            Raw bytes of the image or a path to an image file.
        image_url:
            Optional identifier for logging.

        Returns
        -------
        Optional[str]
            Extracted text, or ``None`` if OCR fails.
        """

        if not image_data:
            self.logger.warning(f"No image data provided for OCR for {image_url or 'unknown'}.")
            return None

        try:
            if self.use_google_vision:
                if isinstance(image_data, bytes):
                    img_bytes = image_data
                else:
                    with open(image_data, "rb") as f:
                        img_bytes = f.read()
                text = await self._vision_to_text(img_bytes)
            else:
                if isinstance(image_data, bytes):
                    img = Image.open(BytesIO(image_data))
                else:
                    img = Image.open(image_data)
                text = await self._image_to_text(img)

            self.logger.debug(
                f"OCR extracted for {image_url or 'image'}: {text[:50]}..."
            )
            return text.strip() if text else ""
        except Exception as exc:
            self.logger.error(f"OCR processing failed for {image_url or 'image'}: {exc}")
            return None

# Create a singleton instance
ocr_processor = OCRProcessor()
