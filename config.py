"""
Configuration module for Gemini Parallel Question Solver
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-3-pro-preview"  # Fast and efficient for vision tasks

# Parallel Processing
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "60"))

# Retry Configuration
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Paths
BASE_DIR = Path(__file__).parent
QUESTIONS_DIR = BASE_DIR / "questions"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"

# Supported image formats
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

# Prompt template for question solving
QUESTION_PROMPT = """Bu soruyu çöz.

Lütfen şu formatta cevapla:
1. **Soru Analizi**: Sorunun ne istediğini kısaca açıkla
2. **Çözüm Adımları**: Adım adım çözümü göster
3. **Cevap**: Net ve kesin cevabı belirt

Türkçe açıklama yap. Matematiksel ifadeleri açık şekilde yaz."""
