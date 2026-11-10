"""Lightweight pre-commit guard; not a replacement for dedicated secret scanning."""
from pathlib import Path
import re,sys
root=Path(__file__).resolve().parents[1]
banned={'.env','.env.local','runtime'}
patterns=[re.compile(r'(?:AC[a-f0-9]{32}:[a-f0-9]{32})',re.I),
 re.compile(r'(?i)(?:twilio_auth_token|gemini_api_key|gnani_api_key)\s*=\s*[A-Za-z0-9_\-]{16,}')]
flag=[]
for path in root.rglob('*'):
    if not path.is_file() or any(part in banned or part.startswith('.venv') for part in path.relative_to(root).parts):continue
    if path.suffix not in {'.py','.md','.js','.html','.css','.txt','.yml','.example'}:continue
    content=path.read_text(encoding='utf8',errors='ignore')
    if any(p.search(content) for p in patterns):flag.append(str(path.relative_to(root)))
print('Possible credentials found in:',flag if flag else 'none')
sys.exit(1 if flag else 0)
