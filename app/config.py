import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
QUINTYPE_API_BASE = os.getenv("QUINTYPE_API_BASE", "https://www.esakal.com")
SMARTFLOW_XML_DIR = os.getenv("SMARTFLOW_XML_DIR", "")
SMARTFLOW_INDEX_URL = os.getenv("SMARTFLOW_INDEX_URL", "")
SAKAL_PLUS_SUBSCRIPTION_URL = os.getenv("SAKAL_PLUS_SUBSCRIPTION_URL", "https://www.esakal.com/subscribe")
PORT = int(os.getenv("PORT", "8000"))

MODEL = "gpt-4o-mini"
MAX_ARTICLES = 8
MAX_TOKENS_PER_ARTICLE = 800
SUGGESTIONS_CACHE_TTL = 0  # always fetch fresh suggestions
