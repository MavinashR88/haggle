"""
Haggle voice pipeline: Twilio → Deepgram STT → Claude → Cartesia TTS
Target latency: <1.5s end-to-end (STT→LLM→TTS first chunk)

Architecture:
  Twilio Media Stream (WebSocket) → Pipecat TwilioFrameSerializer
  → DeepgramSTTService (Nova-3, interim results)
  → ClaudeNegotiationLLM (Sonnet 4.6, streaming)
  → CartesiaTTSService (Sonic-2, streaming chunks)
  → TwilioFrameSerializer → Twilio → PSTN
"""

import asyncio
import os
import json
import logging
from typing import Optional

from dotenv import load_dotenv
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.anthropic import AnthropicLLMService
from pipecat.services.cartesia import CartesiaTTSService
from pipecat.services.deepgram import DeepgramSTTService
from pipecat.transports.network.websocket_server import (
    WebsocketServerParams,
    WebsocketServerTransport,
)

load_dotenv()
logger = logging.getLogger(__name__)


async def run_negotiation_pipeline(
    websocket,
    negotiation_context: dict,
    system_prompt: str,
):
    """
    Run the full negotiation pipeline for one call.
    Called once per inbound WebSocket connection from Twilio.
    """

    # ── Transport (Twilio Media Stream over WebSocket) ────────────────────────
    transport = WebsocketServerTransport(
        websocket=websocket,
        params=WebsocketServerParams(
            audio_out_enabled=True,
            add_wav_header=False,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
            vad_audio_passthrough=True,
        ),
    )

    # ── STT: Deepgram Nova-3 ──────────────────────────────────────────────────
    stt = DeepgramSTTService(
        api_key=os.environ["DEEPGRAM_API_KEY"],
        model="nova-3",
        language="en-US",
        smart_format=True,
        interim_results=True,
        utterance_end_ms=1000,
        vad_events=True,
    )

    # ── LLM: Claude Sonnet 4.6 ───────────────────────────────────────────────
    llm = AnthropicLLMService(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        model="claude-sonnet-4-6",
        max_tokens=512,
    )

    # ── TTS: Cartesia Sonic-2 ─────────────────────────────────────────────────
    tts = CartesiaTTSService(
        api_key=os.environ["CARTESIA_API_KEY"],
        voice_id=os.environ.get("CARTESIA_VOICE_ID", "a0e99841-438c-4a64-b679-ae501e7d6091"),
        model="sonic-2",
        output_format={
            "container": "raw",
            "encoding": "pcm_mulaw",
            "sample_rate": 8000,
        },
    )

    # ── Context: seed with opening disclosure ─────────────────────────────────
    opening = (
        "Hi, this is an AI voice assistant calling on behalf of the account holder. "
        "This call may be recorded for quality purposes. Is it okay to proceed?"
    )
    messages = [
        {"role": "user", "content": "The call just connected. Please give your opening disclosure."},
        {"role": "assistant", "content": opening},
    ]
    context = OpenAILLMContext(messages=messages, system=system_prompt)
    context_agg = llm.create_context_aggregator(context)

    # ── Pipeline ──────────────────────────────────────────────────────────────
    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_agg.user(),
            llm,
            tts,
            transport.output(),
            context_agg.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=True,
            enable_usage_metrics=True,
            report_only_initial_ttfb=True,
        ),
    )

    # Speak opening immediately
    await task.queue_frames([context_agg.assistant().get_context_frame()])

    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)

    # Return transcript for post-call processing
    return [m for m in context.messages if m["role"] in ("user", "assistant")]
