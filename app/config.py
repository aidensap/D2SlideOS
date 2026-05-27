import os
from dotenv import load_dotenv

load_dotenv()

AICORE_AUTH_URL = os.getenv("AICORE_AUTH_URL", "")
AICORE_CLIENT_ID = os.getenv("AICORE_CLIENT_ID", "")
AICORE_CLIENT_SECRET = os.getenv("AICORE_CLIENT_SECRET", "")
AICORE_BASE_URL = os.getenv("AICORE_BASE_URL", "")
AICORE_RESOURCE_GROUP = os.getenv("AICORE_RESOURCE_GROUP", "default")
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")
CHART_LANG = os.getenv("CHART_LANG", "en")

BW_MODE = os.getenv("BW_MODE", "mock")  # mock | odata | rfc

EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USER = os.getenv("EMAIL_USER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)
