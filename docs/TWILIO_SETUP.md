# Twilio integration: trial limitations and verified deployment steps

## First: do not reuse your disclosed Auth Token

Rotate the token in your Twilio console; create a new key where appropriate. Never place Twilio credentials in terminal screenshots, ChatGPT, your GitHub repo or the demo video. Review the Twilio Voice call log for unexpected activity.

## Your existing call request

The request shown in your earlier setup returned a Call SID with **status `queued`** and used Twilio's built-in template URL. It confirms neither delivery nor a functioning custom agent. Check the final status in the Twilio console. Do not repeat calls to someone's phone without their explicit permission.

## Trial restrictions

Twilio currently documents trial Voice restrictions on verified recipients, geography and custom TwiML; some custom verbs may be blocked. Test a supported incoming call with the Twilio Console first. **Do not pay or upgrade simply to test this starter without checking the account and geographic requirements.**

## Staged Twilio bridge (not yet live verified)

This starter includes a **turn-based** phone bridge:

1. A verified caller reaches Twilio.
2. Twilio POSTs to `https://YOUR_DOMAIN/twilio/voice`.
3. The server returns TwiML that plays a Gnani-produced greeting (if configured), then records the caller's next utterance with `<Record>`.
4. Twilio POSTs to `/twilio/turn`, including a recording URL. The server validates `X-Twilio-Signature`, fetches the recording with authenticated Twilio API credentials, and transcribes it using Gnani.
5. The same Gemini/booking engine creates a response; Gnani produces a WAV that Twilio `<Play>` plays.
6. Twilio starts recording another turn.

**Limitations:** Recording availability is asynchronous, webhook timeouts can interrupt the flow, trial restrictions may reject it, and callers cannot barge in during playback. This is a demo bridge, **not a verified low-latency live agent**.

### Requirements before attempting

- Upgraded/supported Twilio number or explicit trial permission for custom TwiML.
- Fresh `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` in local `.env`.
- A public HTTPS URL from a trusted tunnel or hosting provider. Put its exact origin in `PUBLIC_BASE_URL`.
- `ADMIN_TOKEN` rotated to a unique random value (do not use the default).
- In Twilio Console, set Voice **A call comes in** webhook to `POST https://YOUR_DOMAIN/twilio/voice`.
- Set speech keys in `.env` and test browser voice successfully first.
- Monitor logs and use only consented test callers.

For future full-duplex use bidirectional `<Connect><Stream>` and bridge Twilio's **8 kHz μ-law** frames to Gnani streaming **PCM16 8/16kHz**, then Gnani Timbre real-time speech back to Twilio. This is explicitly *not* in the starter. It deserves a separately tested implementation and barge-in handling.

## Deployment note

`app.__main__` binds to `127.0.0.1:8000`. A tunnel may forward to it, but exposing the manager's admin endpoints publicly requires added protections. Never expose the default token to a public tunnel.
