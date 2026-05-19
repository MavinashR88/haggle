"""
FastAPI server — two endpoints:
  POST /outbound   Twilio calls this when the agent wants to initiate a call
  WS   /ws/{job_id} Twilio streams audio here during the call

Job context is passed as query params on the WebSocket URL (set in TwiML).
"""

import asyncio
import json
import logging
import os
from urllib.parse import urlencode

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import Connect, VoiceResponse, Stream

from agent.pipeline import run_negotiation_pipeline
from prompts.negotiation_system import get_system_prompt

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Haggle Voice Agent")
twilio_client = TwilioClient(
    os.environ["TWILIO_ACCOUNT_SID"],
    os.environ["TWILIO_AUTH_TOKEN"],
)


@app.post("/outbound")
async def initiate_call(body: dict):
    """
    Initiate an outbound negotiation call.
    Body: { job_id, to_number, provider_number, negotiation_type, context }
    """
    job_id = body["job_id"]
    to_number = body["to_number"]          # provider's customer service number
    caller_id = os.environ["TWILIO_PHONE_NUMBER"]
    server_url = os.environ["SERVER_URL"]

    # Build TwiML: connect call audio to our WebSocket
    params = urlencode({"job_id": job_id, "ctx": json.dumps(body.get("context", {})), "type": body.get("negotiation_type", "bill_lower_rate")})
    ws_url = f"{server_url.replace('https://', 'wss://').replace('http://', 'ws://')}/ws/{job_id}?{params}"

    twiml = VoiceResponse()
    connect = Connect()
    stream = Stream(url=ws_url)
    connect.append(stream)
    twiml.append(connect)

    call = twilio_client.calls.create(
        twiml=str(twiml),
        to=to_number,
        from_=caller_id,
        status_callback=f"{server_url}/call-status",
        status_callback_event=["initiated", "ringing", "answered", "completed"],
        status_callback_method="POST",
        record=True,
    )

    logger.info(f"Call initiated: {call.sid} → {to_number}")
    return {"call_sid": call.sid, "status": call.status, "job_id": job_id}


@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str, ctx: str = "{}", type: str = "bill_lower_rate"):
    """
    Twilio streams bidirectional audio here during the call.
    We pipe it through the Pipecat pipeline.
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for job {job_id}")

    try:
        context = json.loads(ctx)
        system_prompt = get_system_prompt(type, context)
        transcript = await run_negotiation_pipeline(websocket, context, system_prompt)
        logger.info(f"Call {job_id} complete. Turns: {len(transcript)}")
        # TODO: persist transcript + result to DB
    except WebSocketDisconnect:
        logger.info(f"Call {job_id} disconnected")
    except Exception as e:
        logger.exception(f"Pipeline error on job {job_id}: {e}")
    finally:
        logger.info(f"Job {job_id} pipeline done")


@app.post("/call-status")
async def call_status(request):
    """Twilio status callback — update call record in DB."""
    form = await request.form()
    logger.info(f"Call status: {form.get('CallSid')} → {form.get('CallStatus')}")
    return PlainTextResponse("OK")


@app.get("/health")
def health():
    return {"status": "ok", "service": "haggle-voice-agent"}
