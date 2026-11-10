# Atithi AI — 2–3 minute submission video storyboard

All steps must show the **actual application**. Use a fictional restaurant and only consenting simulated callers.

| Time | Screen | Action and proof |
| --- | --- | --- |
| 0:00–0:15 | Title + problem | A restaurant misses a call during dinner rush. One sentence explains the product. |
| 0:15–0:35 | Manager dashboard | Show eight real tables, reservation ledger and configured provider status. |
| 0:35–1:10 | Voice Studio | Speak in Hindi/Hinglish using Prisma; show actual transcript, Gemini intent, spoken Timbre reply. |
| 1:10–1:35 | Booking confirmation | Confirm a reservation of 8 guests. Show new database booking and table ID T08. |
| 1:35–1:55 | Second customer session | Repeat same request. Demonstrate no table available; no second booking. |
| 1:55–2:15 | Manager request | Request birthday arrangement; observe the task in dashboard and mark done. |
| 2:15–2:35 | Call evidence | Show stored transcript/intent and the data model. |
| 2:35–2:50 | Technical validation | Show `python -m pytest -q`, call source mode (browser / Twilio), and exact integration limits. |

## Submission disclosures

- The restaurant and menu are seeded demonstration data.
- The reservation engine and dashboard are real within the local demo environment.
- If Twilio custom calling did not work, do not say it did. Say “browser voice channel, with an experimental Twilio webhook bridge.”
- If the rule parser ran, label it `demo_rules`. Claim Gnani + Gemini only after live calls succeeded.
- No CCTV, POS, real restaurant table integration or outgoing manager transfer is currently implemented.
- Use screenshots and logs without real numbers, API tokens, or personal call data.
