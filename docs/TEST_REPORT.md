# Test report — starter snapshot

- **Local test invocation:** `python -m pytest -q`
- **Observed outcome:** 15 passed (on the creation runtime, 2026-11-10)
- **Syntax check:** `python -m compileall -q app` passed
- **Secrets check:** `python scripts/check_secrets.py` reported none in included source/config templates
- **Coverage tested:** seeded data; atomic single-table reservation, overlap, cancel / rebook; concurrency race; blocked table; modify conflict; invalid requests; call history; task creation; manager auth; health endpoint; API booking; dialogue confirmation; correction from four to six before commit.
- **Not verified:** Real Gnani provider credentials or audio quality, real Gemini parsing against user's credentials, Twilio phone calls or recording fetch, browser microphone on user's Windows device, production deployment, accessibility audit, caller identity verification.

Tests do not prove service readiness in external environments. See `docs/CODEX_TASKS.md` for the live integration verification plan.
