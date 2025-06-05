"""Utility for performing OCR on images using Tesseract.

This module provides an asynchronous interface that wraps the
``pytesseract`` library, allowing image bytes or file paths to be
processed without blocking the event loop.
"""

import logging
from typing import Optional, Union
import asyncio
from io import BytesIO

from PIL import Image
import pytesseract

logger = logging.getLogger(__name__)

class OCRProcessor:
    """Simple OCR processor based on the ``pytesseract`` library."""

    def __init__(self, tesseract_cmd: Optional[str] = None) -> None:
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
        self.logger.info("OCRProcessor initialized using pytesseract.")

    async def _image_to_text(self, img: Image.Image) -> str:
        """Run OCR in a thread to avoid blocking the event loop."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, pytesseract.image_to_string, img)

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
            if isinstance(image_data, bytes):
                img = Image.open(BytesIO(image_data))
            else:
                img = Image.open(image_data)

            text = await self._image_to_text(img)
            self.logger.debug(f"OCR extracted for {image_url or 'image'}: {text[:50]}...")
            return text.strip() if text else ""
        except Exception as exc:
            self.logger.error(f"OCR processing failed for {image_url or 'image'}: {exc}")
            return None

# Create a singleton instance
ocr_processor = OCRProcessor()
