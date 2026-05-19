# Haggle Voice Agent

AI voice agent that calls companies on behalf of users to negotiate bills, credit limits, and account terms.

## Stack

| Layer | Tech |
|---|---|
| Phone calls | Twilio Voice (PSTN outbound) |
| Audio streaming | Twilio Media Streams → WebSocket |
| Voice pipeline | Pipecat |
| STT | Deepgram Nova-3 (streaming, interim results) |
| Negotiation brain | Claude Sonnet 4.6 (streaming) |
| TTS | Cartesia Sonic-2 (streaming, mulaw 8kHz) |
| Server | FastAPI + uvicorn |
| Hold detection | Silero VAD via Pipecat |

## Setup

```bash
# 1. Install deps
pip install -r requirements.txt

# 2. Configure env
cp .env.example .env
# Fill in: TWILIO_*, DEEPGRAM_API_KEY, ANTHROPIC_API_KEY, CARTESIA_API_KEY

# 3. Expose to internet (dev)
ngrok http 8765
# Copy the https URL into SERVER_URL in .env

# 4. Start server
uvicorn agent.server:app --host 0.0.0.0 --port 8765 --reload

# 5. Test call
python3 scripts/test_call.py
```

## Architecture

```
User UI → POST /outbound (job_id, context, negotiation_type)
  → Twilio dials provider number
  → Twilio streams audio to WS /ws/{job_id}
  → Pipecat pipeline:
      Twilio input
      → Silero VAD (hold detection)
      → Deepgram Nova-3 STT
      → Claude Sonnet 4.6 (system prompt = negotiation persona + playbook)
      → Cartesia Sonic-2 TTS
      → Twilio output
  → POST /call-status (on call end)
  → Transcript + result saved to DB
```

## Negotiation modes

- `bill_lower_rate` — existing bill, lower the monthly rate
- `bill_lock_promo` — lock in promotional rate before expiry
- `bill_cancel` — navigate cancellation + capture retention offer
- `credit_limit` — request credit card limit increase
- `apr_reduction` — negotiate lower APR
- `fee_waiver` — waive late/annual/overdraft fees
- `new_account` — negotiate terms before signing up for new service

## Provider playbooks

Provider-specific scripts, escalation paths, and magic phrases in `agent/playbooks.py`.
Currently configured: Comcast, AT&T, Verizon, Spectrum, Planet Fitness, Chase, Capital One.

## Self-learning loop (Day 9+)

```
Cekura 100-scenario suite
  → cluster failures by type
  → LLM proposes system prompt patch
  → re-run suite
  → keep patch if pass rate improves, revert otherwise
```

See `scripts/self_learning_loop.py` (Day 9 work).
