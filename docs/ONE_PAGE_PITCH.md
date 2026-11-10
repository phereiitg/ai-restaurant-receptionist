# ATITHI AI — An AI host that actually books the table

**Problem.** A restaurant's front desk is often busiest precisely when customers call. A conventional IVR cannot handle a caller who changes their mind, switches languages, asks about an unavailable table, or needs an arrangement that requires a human.

**Solution.** Atithi AI is a Hindi/Hinglish-friendly restaurant voice receptionist integrated with a real reservation engine and a manager dashboard. It can answer menu questions from the restaurant's own menu, check availability, request confirmation, commit bookings to the database and raise manager tasks. Its operational state is visible, rather than hidden behind a conversational interface.

**What is technically distinctive.** A two-way spoken interaction is grounded in live business state. The reservation engine enforces overlap constraints inside atomic SQLite transactions, so two simultaneous booking attempts cannot both claim the last available table. The LLM extracts intent but cannot directly issue SQL or invent availability; backend rules commit changes only after confirmation. Staff set table readiness; no unverified CCTV claim affects availability.

**Gnani integration.** Gnani Prisma transcribes real Hindi/Hinglish speech; Gnani Timbre synthesizes spoken responses. Gemini converts the transcript into constrained intent data. FFmpeg normalizes microphone audio. The actual live provider path must be verified with the user's keys. A separate limited text-mode parser is explicitly labelled demo-only.

**Working prototype scope.** Eight-seat demo restaurant inventory, menu lookup, booking / cancellation / modification logic, conflict-safe reservations, staff table status, manager escalation tasks, call transcripts and operational dashboard. Browser voice channel implemented; experimental Twilio record–transcribe–respond integration present but dependent on custom TwiML permissions and local testing.

**Future roadmap.** Low-latency bidirectional Twilio streaming, caller authentication for booking changes, POS/inventory APIs, SMS booking confirmation, waitlist, optional privacy-preserving floor occupancy observations with staff verification, per-restaurant tenancy.

**Trust and safety.** Demo restaurant only, no real bookings, no payments, no actual camera inference. Caller data and audio must be gathered with consent. Public launch requires production authentication, event logs and provider rate limits.

**Success measurement.** A real Hindi/Hinglish request produces a verified booking, the manager dashboard updates, a second caller cannot double-book the last table, and a complex request appears in the manager queue.
