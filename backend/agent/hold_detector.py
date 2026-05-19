"""
Hold music and IVR detection using audio analysis.
Pipecat frame processor that sits between transport.input() and STT.
Detects:
  - Silence > 3s → flag as possible hold
  - Repetitive audio patterns → flag as hold music
  - DTMF tones → log, don't transcribe
  - IVR prompts → pass to STT with HOLD prefix in metadata
"""

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

HOLD_SILENCE_THRESHOLD_S = 3.0
HOLD_MUSIC_CONFIRMATION_S = 8.0


class HoldDetector:
    """
    Simple hold state tracker based on silence duration.
    More sophisticated version would use frequency analysis for music detection.
    """

    def __init__(self, on_hold_start=None, on_hold_end=None):
        self._silence_start: Optional[float] = None
        self._in_hold = False
        self._hold_duration = 0.0
        self.on_hold_start = on_hold_start
        self.on_hold_end = on_hold_end

    def on_speech_start(self):
        if self._in_hold:
            self._in_hold = False
            elapsed = time.time() - (self._silence_start or time.time())
            self._hold_duration += elapsed
            logger.info(f"Hold ended after {elapsed:.1f}s (total hold: {self._hold_duration:.1f}s)")
            if self.on_hold_end:
                self.on_hold_end(elapsed)
        self._silence_start = None

    def on_speech_end(self):
        self._silence_start = time.time()

    def tick(self) -> bool:
        """Call periodically. Returns True if now in hold state."""
        if self._silence_start is None:
            return False
        elapsed = time.time() - self._silence_start
        if elapsed > HOLD_SILENCE_THRESHOLD_S and not self._in_hold:
            self._in_hold = True
            logger.info(f"Hold detected after {elapsed:.1f}s of silence")
            if self.on_hold_start:
                self.on_hold_start()
        return self._in_hold

    @property
    def total_hold_seconds(self) -> float:
        if self._in_hold and self._silence_start:
            return self._hold_duration + (time.time() - self._silence_start)
        return self._hold_duration
