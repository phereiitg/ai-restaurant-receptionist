# Codex implementation contract: Atithi AI

Paste this document (or the short prompt below) to Codex running in VS Code **after extracting the ZIP and opening that folder**.

## Non-negotiable rules

- Use **Python** for all backend/business logic. Keep the existing custom HTML/CSS/JS manager UI; do not replace it with a generated-looking template or spend time migrating frameworks during the challenge.
- Never log, print, search for, or commit API keys, phone numbers from real calls, .env files, or recorded calls. The previously disclosed Twilio token must be rotated outside the project.
- Do not fabricate speech transcripts, available tables, phone-call completions or bookings.
- No CCTV, voice cloning, payments, real restaurant integrations, or automatic outbound calls.
- Each change must pass `python -m pytest -q` and `python -m compileall -q app`.
- Do not alter schema or business rules without an associated regression test.
- Ask for human approval before changing cloud resources, charging Twilio, dialing a number, making an external deployment or pushing to GitHub.
- Do not describe the `<Record>` Twilio bridge as low-latency streaming. It isn't.

## Phase 0 — Health checks and safe start

1. Verify Python 3.11+, FFmpeg, `.env.example`, requirements, runtime paths.
2. Use `python -m pytest -q` and review failures.
3. Verify `curl http://127.0.0.1:8000/api/health` or `Invoke-RestMethod` in PowerShell.
4. Run a no-secret scan (`git status --short`, `git diff --check`, `git ls-files | Select-String ...`).
5. **Commit**: `chore: bootstrap Atithi project and document environment`.

## Phase 1 — Reliable reservations

1. Verify seeded tables, menu and dashboard.
2. Test booking for eight at 20:00, same request from two parallel sessions, cancel, then rebook.
3. Test 90-minute overlap and dirty/blocked table behaviour.
4. Fix any functional defects; avoid unnecessary redesign.
5. **Commit**: `feat(reservations): enforce atomic booking and manager states`.

## Phase 2 — Speech and dialogue integration

1. Check `GNANI_API_KEY`, `GEMINI_API_KEY` exist locally without printing values.
2. Test a short consenting Hindi recording through `POST /api/voice/turn`.
3. Confirm STT result originates from Prisma and not fallback, `parser_mode=gemini`, and TTS response is actual WAV.
4. Test context correction: “four people—actually six”; confirmation, cancellation and menu query.
5. On STT failure, show a real error and preserve state. On model parsing failure, declare fallback accurately.
6. Add a test with fake HTTP adapters (not a fake user-facing response) so the CI can run without credentials.
7. **Commit**: `feat(voice): connect Prisma, Gemini intents and Timbre responses`.

## Phase 3 — Twilio bridge (only if account permits)

1. Study `docs/TWILIO_SETUP.md` and verify trial status with owner. Never assume queued means connected.
2. Use a tunnel with a fresh random admin token, HTTPS, exact public origin.
3. Confirm Twilio signatures reject unsigned/fake requests. Test only verified, consented caller.
4. Verify one real call with menu Q&A, booking, manager task and call audit.
5. Report explicitly if custom TwiML is blocked. Browser call remains the supported demo.
6. **Commit**: `feat(telephony): validate Twilio webhooks and route recorded turns`.

## Phase 4 — Demo quality

1. Compare 2 parallel bookings to the last available eight-seat table.
2. Fix any stale UI refresh or call-state errors.
3. Run the full tests, browser click-through and secret scan.
4. Write a screenshot-free `README` with a demo link and exact measured outcomes.
5. **Commit**: `docs(demo): publish reproducible walkthrough and test evidence`.

## Suggested initial prompt to Codex

```text
You are implementing Atithi AI, a Python-first restaurant voice receptionist with a custom manager dashboard. Read README.md, docs/CODEX_TASKS.md, docs/TWILIO_SETUP.md and app/storage.py before edits. Keep the current architecture and business invariants. First run tests and compile checks; identify concrete issues. Fix only verified failures with tests, one logical task per commit. Do not use or reveal any secrets. Never place real caller data in a commit. Do not start billable external calls or push to GitHub without explicit approval. Report completed files, tests, remaining blockers and the exact proposed commit after each phase.
```
