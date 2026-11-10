"""Check local environment without ever printing credentials."""
from __future__ import annotations
import os,shutil,sys
from pathlib import Path
from app.config import settings

print('Python:',sys.version.split()[0])
print('FFmpeg:',bool(shutil.which('ffmpeg')))
print('Database directory:',settings.runtime_dir)
print('Gnani key configured:',bool(settings.gnani_api_key))
print('Gemini key configured:',bool(settings.gemini_api_key))
print('Manager token customized:',settings.admin_token!='replace-with-a-long-random-local-token')
print('Public Twilio origin configured:',bool(settings.public_base_url))
print('No credentials printed.')
