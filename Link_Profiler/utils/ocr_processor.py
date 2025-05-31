"""
OCR Processor - Extracts text from images.
File: Link_Profiler/utils/ocr_processor.py
"""

import logging
from typing import Optional, Union, List
import asyncio # For async simulation
import random # For random delays

logger = logging.getLogger(__name__)

class OCRProcessor:
    """
    A placeholder for Optical Character Recognition (OCR) functionality.
    In a real application, this would integrate with an OCR library (e.g., Tesseract)
    or a cloud-based OCR API (e.g., Google Cloud Vision, AWS Textract).
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".OCRProcessor")
        self.logger.info("OCRProcessor initialized (simulated functionality).")

    async def process_image(self, image_data: Union[bytes, str], image_url: Optional[str] = None) -> Optional[str]:
        """
        Simulates processing an image to extract text using OCR.
        
        Args:
            image_data: The raw bytes of the image or a path/URL to the image.
                        For this simulation, it can be any string/bytes.
            image_url: The URL of the image, for logging purposes.
            
        Returns:
            A simulated string of extracted text, or None if processing fails.
        """
        if not image_data:
            self.logger.warning(f"No image data provided for OCR for {image_url or 'unknown'}.")
            return None

        # Simulate asynchronous processing time
        await asyncio.sleep(random.uniform(0.1, 0.5))

        # Simulate OCR results based on some simple logic
        simulated_text = ""
        if isinstance(image_data, bytes):
            simulated_text = f"Simulated OCR text from image bytes (size: {len(image_data)}). "
        elif isinstance(image_data, str):
            simulated_text = f"Simulated OCR text from image content '{image_data[:20]}...'. "
        
        # Add some random keywords to make it more "realistic"
        keywords = ["logo", "text", "button", "advertisement", "caption", "product"]
        simulated_text += f"Keywords: {', '.join(random.sample(keywords, random.randint(1, 3)))}."

        self.logger.debug(f"Simulated OCR for {image_url or 'image'}: {simulated_text[:50]}...")
        return simulated_text

# Create a singleton instance
ocr_processor = OCRProcessor()
