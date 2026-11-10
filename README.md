# Atithi AI — restaurant voice host and operations console

> **Status:** Starter prototype. Real reservation database and dashboard; Gemini intent parsing and Gnani voice API adapters are wired but NOT live-tested with your account. Twilio custom call bridge is optional/experimental. No CCTV or POS integration.

A Python-first restaurant operations assistant: guests can speak or type to check menu information, find available tables, confirm bookings, and request a manager. Staff manage reservations, table readiness and requests in a purpose-built web dashboard.

**Illustrative venue:** The Banyan Table, Guwahati. Tables, menus and reservations are local demo data; nothing is sent to a real restaurant.

## Critical first action: rotate Twilio credential

A Twilio Auth Token was pasted into a conversation while setting up this project. **Rotate it in Twilio Console before proceeding**, verify no third-party calls were made, and never place the old token or your keys in source, screenshots, shell history or Git commits. The ZIP contains no supplied account credentials, phone numbers or secrets.

## Quick start (Windows PowerShell / VS Code)

1. Unzip this project and choose **File → Open Folder** in VS Code.
2. In **Terminal → New Terminal**, execute:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

3. Edit `.env` to set a newly generated `ADMIN_TOKEN`. For **voice**, also set `GNANI_API_KEY`, `GEMINI_API_KEY`. Keep `.env` local. Leave `PUBLIC_BASE_URL` blank for browser testing.

4. Start the application:

```powershell
.\.venv\Scripts\python.exe -m app
```

5. Visit **http://127.0.0.1:8000**. Enter `ADMIN_TOKEN` from your local `.env` at the manager access prompt.

6. Open **Reservations** to create a real booking; **Floor & service** to update table readiness; **Voice studio** to test the spoken conversation. For typed tests when Gemini isn't configured, the UI explicitly labels the limited `demo_rules` parser. It is **not an AI result**.

7. Run the test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

**Requirements:** Python 3.11+, FFmpeg available on PATH for browser microphone conversion. Microphone capture requires `localhost` or HTTPS. `pip` downloads packages; no npm is required for this first release.

## A reliable demo scenario

- Go to **Voice studio**. Use typed input or a real Gnani microphone turn.
- Say/enter: `Book 8 people tomorrow at 8 pm. My name is Rahul`.
- The assistant checks the actual database and requests confirmation.
- Say `yes`. Only then does a confirmed `RES-...` booking appear.
- Start **New session**, repeat the same request with a different name. The last eight-seat table is unavailable.
- Go to **Reservations** to show the persisted booking and **Calls & requests** to inspect the transcript.
- Ask for a `birthday manager request`. See a real open manager task.

No staged audio or fabricated result is necessary for this demo. For a new/empty database, the restaurant has exactly one eight-seat table, `T08`. **All times are Asia/Kolkata, 24-hour, and 90-minute seatings**. This simplified policy is intentionally documented, not a production optimization engine.

## Architecture

```text
Browser Voice studio [MediaRecorder]
           | audio file (25s max)
           v
FastAPI /api/voice/turn -> FFmpeg WAV normalization
           |              |
           |              -> Gnani Prisma REST STT [actual transcript]
           v
Gemini JSON intent parser (optional limited demo rule parser)
           |
Bounded Python dialogue coordinator (confirm changes)
           |
SQLite reservation engine (BEGIN IMMEDIATE / table locks / no overlap)
           |
Manager dashboard + call transcript + staff tasks
           |
Gnani Timbre REST TTS -> actual WAV reply in the browser

Optional: Twilio <Record> turn-based webhook -> same voice/dialogue pipeline
```

Key locations:

- `app/storage.py` — SQLite schema, transactional booking rules, tables, tasks, calls.
- `app/providers.py` — Gnani STT/TTS and Gemini provider adapters.
- `app/dialogue.py` — bounded orchestration and confirmation gate.
- `app/main.py` — API, audio conversion, security checks and optional Twilio webhooks.
- `app/static/` — bespoke manager dashboard with no third-party template.
- `tests/` — transaction, race-condition, validation, handoff and API checks.
- `docs/CODEX_TASKS.md` — exact phased implementation instructions for Codex.
- `docs/DEMO_SCRIPT.md` — video walkthrough and expected observations.

## Provider modes and honesty

| Feature | When configured | When not configured |
| --- | --- | --- |
| Gnani STT | Real external REST transcription | Error; no fabricated transcript |
| Gemini | Real structured intent extraction | Explicitly labelled `demo_rules` parser if allowed |
| Gnani TTS | Real audio from Timbre | Visible text reply; TTS unavailable |
| Booking | Always SQLite with atomic transaction | Same |
| Twilio | Experimental custom TwiML recording loop | Browser simulator works |
| CCTV | Not present | Staff-only floor states |

**This is NOT a real-time interruptible conversation**. The initial Twilio implementation uses the TwiML `<Record>` action to capture a short turn, transcribe with Gnani, return a spoken reply via `<Play>`, and record another turn. It is supported in principle by Twilio's APIs but **not live-tested on your account**. Twilio trial accounts can block custom TwiML or require verified recipients and upgraded account. See `docs/TWILIO_SETUP.md`.

## Reservation guarantees and limitations

- One table per booking; choose smallest available table that seats the party.
- Duration fixed at 90 minutes; hours 11:00–22:00; maximum party of eight.
- Prevent overlapping reservations on the same table, even under concurrent requests.
- Confirmation is required before an AI-booked reservation, modification or cancellation.
- Availability checked **again on commit**, so stale observations cannot double-book.
- Floor status is manual. 'Dirty' and 'occupied' block near-term placements; 'blocked' always prevents booking.
- No payments, real-world bookings or messages are sent.

## Before any public deployment

This is a demo starter, not a production-ready SaaS. Implement a real multi-user login, CSRF protections if using cookies, audited manager permissions, persistent request-rate limiting, a job queue, audio retention rules, secret management, domain-specific access control and deployment smoke tests. Configure public HTTPS, rotate secrets, use a non-default admin token and protect outbound provider costs. Never publish raw call audio without consent.

## Reference docs

- [Gnani STT REST](https://docs.gnani.ai/api/STT/speech-to-text)
- [Gnani TTS REST](https://docs.gnani.ai/api/TTS/tts-inference)
- [Twilio Voice trial limitations](https://www.twilio.com/docs/usage/trials/try-out-voice)
- [Twilio Record TwiML](https://www.twilio.com/docs/voice/twiml/record)
- [Twilio webhook validation](https://www.twilio.com/docs/usage/security)
