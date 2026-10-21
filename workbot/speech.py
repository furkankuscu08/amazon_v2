"""Reads the plan's spoken summary aloud with Amazon Polly."""

from __future__ import annotations

import logging
import os
import threading
from collections import OrderedDict

import boto3
from botocore.config import Config

log = logging.getLogger(__name__)


class SpeechError(Exception):
    pass


class Speech:
    """Polly standard voice in the AWS Region WorkBot uses; audio is kept per text."""

    def __init__(self, client=None, cache_size: int = 64):
        self._client = client
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._size = cache_size
        self._lock = threading.Lock()

    def _polly(self):
        # Built once; a race on first use only builds a client twice.
        if self._client is None:
            # boto3 reads only AWS_DEFAULT_REGION or the profile's Region.
            self._client = boto3.session.Session().client(
                "polly",
                region_name=os.getenv("AWS_REGION") or None,
                config=Config(
                    connect_timeout=5,
                    read_timeout=20,
                    retries={"mode": "standard", "max_attempts": 2},
                ),
            )
        return self._client

    def audio(self, text: str) -> bytes:
        with self._lock:
            if text in self._cache:
                self._cache.move_to_end(text)
                return self._cache[text]
            polly = self._polly
        # Not under the lock, so a slow call does not hold up cached texts; two
        # requests for the same new text may both reach Polly.
        try:
            reply = polly().synthesize_speech(
                Text=text,
                OutputFormat="mp3",
                VoiceId=os.getenv("WORKBOT_POLLY_VOICE") or "Brian",
                Engine=os.getenv("WORKBOT_POLLY_ENGINE") or "standard",
            )
            audio = reply["AudioStream"].read()
        except Exception as exc:
            # Only the class name: a message could quote the text or account.
            log.warning("speech_failed type=%s", type(exc).__name__)
            raise SpeechError("Audio is not available right now.") from exc
        with self._lock:
            self._cache[text] = audio
            if len(self._cache) > self._size:
                self._cache.popitem(last=False)
        return audio
