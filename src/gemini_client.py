"""
Gemini Client Module
Handles communication with Gemini API for question solving
"""
import asyncio
import time
import base64
from typing import Optional
from pathlib import Path

from google import genai
from google.genai import types
from rich.console import Console

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    QUESTION_PROMPT,
    MAX_RETRIES,
    RETRY_DELAY,
    REQUEST_TIMEOUT,
)

console = Console()


class GeminiClient:
    """Client for Gemini API with vision capabilities"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY
        if not self.api_key:
            raise ValueError(
                "Gemini API key not found! "
                "Set GEMINI_API_KEY in .env file or pass it directly."
            )
        
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = GEMINI_MODEL
        self._request_count = 0
        self._total_time = 0.0
    
    async def solve_question(
        self,
        image_bytes: bytes,
        mime_type: str,
        filename: str,
        custom_prompt: Optional[str] = None,
    ) -> dict:
        """
        Solve a question from an image using Gemini Vision
        
        Returns:
            dict with keys: filename, success, solution, error, time_taken
        """
        prompt = custom_prompt or QUESTION_PROMPT
        start_time = time.time()
        
        for attempt in range(MAX_RETRIES):
            try:
                # Create image part for Gemini new SDK
                image_part = types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type,
                )
                
                # Generate content with image
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.model_name,
                        contents=[prompt, image_part]
                    ),
                    timeout=REQUEST_TIMEOUT
                )
                
                time_taken = time.time() - start_time
                self._request_count += 1
                self._total_time += time_taken
                
                return {
                    "filename": filename,
                    "success": True,
                    "solution": response.text,
                    "error": None,
                    "time_taken": time_taken,
                }
                
            except asyncio.TimeoutError:
                console.print(f"[yellow]⏱️ Timeout for {filename}, attempt {attempt + 1}/{MAX_RETRIES}[/yellow]")
                
            except Exception as e:
                error_msg = str(e)
                console.print(f"[yellow]⚠️ Error for {filename}: {error_msg}, attempt {attempt + 1}/{MAX_RETRIES}[/yellow]")
                
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))  # Exponential backoff
        
        # All retries failed
        time_taken = time.time() - start_time
        return {
            "filename": filename,
            "success": False,
            "solution": None,
            "error": f"Failed after {MAX_RETRIES} attempts",
            "time_taken": time_taken,
        }
    
    def get_stats(self) -> dict:
        """Get client statistics"""
        return {
            "total_requests": self._request_count,
            "total_time": self._total_time,
            "avg_time": self._total_time / max(1, self._request_count),
        }


if __name__ == "__main__":
    # Test the client
    async def test():
        client = GeminiClient()
        print(f"Client initialized with model: {client.model_name}")
        print(client.get_stats())
    
    asyncio.run(test())
