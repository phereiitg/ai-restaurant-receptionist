from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    db_path: str = os.getenv("DB_PATH", "./runtime/atithi.sqlite3")
    gnani_api_key: str = os.getenv("GNANI_API_KEY", "")
    gnani_stt_model: str = os.getenv("GNANI_STT_MODEL", "prisma-v3.0")
    gnani_tts_model: str = os.getenv("GNANI_TTS_MODEL", "timbre-v3.0")
    gnani_voice: str = os.getenv("GNANI_VOICE", "Shivani")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    admin_token: str = os.getenv("ADMIN_TOKEN", "replace-with-a-long-random-local-token")
    allow_rule_demo: bool = os.getenv("ALLOW_RULE_BASED_DEMO", "true").lower() == "true"
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    manager_phone: str = os.getenv("MANAGER_PHONE", "")

    @property
    def runtime_dir(self) -> Path:
        return Path(self.db_path).resolve().parent

settings = Settings()
