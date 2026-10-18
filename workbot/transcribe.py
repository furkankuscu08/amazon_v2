"""Turns a short spoken idea or answer into text with Amazon Nova 2 Sonic on Bedrock.

Amazon Transcribe is not open to this project's AWS account, so the speech-to-speech
model's own transcript of the user's turn is used; its spoken reply is ignored.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
import uuid

import boto3

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
# 16-bit mono PCM: 20 seconds at most, so one request stays small and cheap.
MAX_SECONDS = 20
MAX_BYTES = SAMPLE_RATE * 2 * MAX_SECONDS
SONIC_MODEL = "amazon.nova-2-sonic-v1:0"
_CHUNK = 1024
# Silence after the recording, so the model hears the turn end.
_TAIL = b"\x00\x00" * SAMPLE_RATE * 2
# Seconds to wait for the first words once the whole recording has been sent.
_HEARD_WITHIN = 8
# A pause may split one recording into several user turns: keep listening until
# no new user text has arrived for this long.
_QUIET_AFTER = 1.5
_CLEANUP = 2


class TranscriptionError(Exception):
    pass


def _events(prompt: str, system: str, audio: str) -> list[dict]:
    """The session opening: a short system turn, then the start of the user's audio."""
    text = {"mediaType": "text/plain"}
    lpcm = {"mediaType": "audio/lpcm", "sampleSizeBits": 16, "channelCount": 1}
    return [
        {"sessionStart": {"inferenceConfiguration": {"maxTokens": 256}}},
        {
            "promptStart": {
                "promptName": prompt,
                "textOutputConfiguration": text,
                "audioOutputConfiguration": {
                    **lpcm,
                    "sampleRateHertz": 24000,
                    "voiceId": "matthew",
                    "encoding": "base64",
                    "audioType": "SPEECH",
                },
            }
        },
        {
            "contentStart": {
                "promptName": prompt,
                "contentName": system,
                "type": "TEXT",
                "interactive": False,
                "role": "SYSTEM",
                "textInputConfiguration": text,
            }
        },
        {
            "textInput": {
                "promptName": prompt,
                "contentName": system,
                "content": "Listen to the user. Reply with one short word.",
            }
        },
        {"contentEnd": {"promptName": prompt, "contentName": system}},
        {
            "contentStart": {
                "promptName": prompt,
                "contentName": audio,
                "type": "AUDIO",
                "interactive": True,
                "role": "USER",
                "audioInputConfiguration": {
                    **lpcm,
                    "sampleRateHertz": SAMPLE_RATE,
                    "audioType": "SPEECH",
                    "encoding": "base64",
                },
            }
        },
    ]


async def _stream(pcm: bytes, region: str, credentials) -> str:
    # Imported here: the SDK and its CRT transport load only when voice input is used.
    from aws_sdk_bedrock_runtime.client import AsyncBedrockRuntimeClient
    from aws_sdk_bedrock_runtime.config import AsyncBedrockRuntimeConfig
    from aws_sdk_bedrock_runtime.models import (
        BidirectionalInputPayloadPart,
        InvokeModelWithBidirectionalStreamInputChunk,
        InvokeModelWithBidirectionalStreamOperationInput,
    )
    from smithy_http.aio.crt import AWSCRTHTTPClient

    # The default HTTP transport cannot stream both ways.
    async with AWSCRTHTTPClient() as transport:
        client = AsyncBedrockRuntimeClient(
            config=await AsyncBedrockRuntimeConfig.resolve(
                region=region,
                endpoint_uri=f"https://bedrock-runtime.{region}.amazonaws.com",
                aws_access_key_id=credentials.access_key,
                aws_secret_access_key=credentials.secret_key,
                aws_session_token=credentials.token,
                transport=transport,
            )
        )
        stream = await client.invoke_model_with_bidirectional_stream(
            InvokeModelWithBidirectionalStreamOperationInput(model_id=SONIC_MODEL)
        )
        heard: list[str] = []
        last_heard = 0.0
        output = None
        reader = None
        prompt, system, audio = (str(uuid.uuid4()) for _ in range(3))

        async def send(event: dict) -> None:
            payload = json.dumps({"event": event}).encode()
            await stream.input_stream.send(
                InvokeModelWithBidirectionalStreamInputChunk(
                    value=BidirectionalInputPayloadPart(bytes_=payload)
                )
            )

        async def receive() -> None:
            nonlocal output, last_heard
            _, output = await stream.await_output()
            role = None
            while (result := await output.receive()) is not None:
                event = json.loads(result.value.bytes_.decode())["event"]
                if "contentStart" in event:
                    role = event["contentStart"].get("role")
                elif "textOutput" in event and role == "USER":
                    heard.append(event["textOutput"]["content"])
                    last_heard = time.monotonic()

        try:
            reader = asyncio.create_task(receive())
            for event in _events(prompt, system, audio):
                await send(event)
            recording = pcm + _TAIL
            for start in range(0, len(recording), _CHUNK):
                chunk = base64.b64encode(recording[start : start + _CHUNK]).decode()
                await send(
                    {
                        "audioInput": {
                            "promptName": prompt,
                            "contentName": audio,
                            "content": chunk,
                        }
                    }
                )
            await send({"contentEnd": {"promptName": prompt, "contentName": audio}})
            sent = time.monotonic()
            # Sonic says nothing at all about a silent recording.
            while not reader.done():
                now = time.monotonic()
                if (not heard and now - sent > _HEARD_WITHIN) or (
                    heard and now - last_heard > _QUIET_AFTER
                ):
                    break
                await asyncio.sleep(0.1)
            if reader.done() and reader.exception():
                raise reader.exception()
        finally:
            # End the session, then let the reply stream run out on its own: cancelling
            # a read while the transport still writes leaves its tasks failing later.
            try:
                async with asyncio.timeout(_CLEANUP):
                    await send({"promptEnd": {"promptName": prompt}})
                    await send({"sessionEnd": {}})
                    await stream.input_stream.close()
                    if reader:
                        await reader
            except Exception as exc:  # noqa: BLE001 - the session may already be closed.
                log.info("transcription_close_failed type=%s", type(exc).__name__)
            if reader and not reader.done():
                reader.cancel()
            if output is not None:
                try:
                    async with asyncio.timeout(_CLEANUP):
                        await output.close()
                except Exception as exc:  # noqa: BLE001
                    log.info("transcription_close_failed type=%s", type(exc).__name__)
    turns = [part.strip() for part in heard if part.strip()]
    return " ".join(turn[:1].upper() + turn[1:] for turn in turns)


class Transcriber:
    """Credentials and Region come from the same AWS chain as the model calls."""

    async def text(self, pcm: bytes) -> str:
        if not pcm or len(pcm) > MAX_BYTES or len(pcm) % 2:
            raise TranscriptionError("The recording could not be used. Try again.")
        try:
            session = boto3.session.Session()
            # boto3 reads only AWS_DEFAULT_REGION or the profile's Region.
            region = os.getenv("AWS_REGION") or session.region_name
            credentials = session.get_credentials()
            if not region or credentials is None:
                raise LookupError("No AWS Region or credentials")
            text = await asyncio.wait_for(
                _stream(pcm, region, credentials.get_frozen_credentials()), 30
            )
        except Exception as exc:
            # Only the class name: a message could quote the account or the audio.
            log.warning("transcription_failed type=%s", type(exc).__name__)
            raise TranscriptionError(
                "Voice input is not available right now. Type the text instead."
            ) from exc
        if not text:
            raise TranscriptionError("No speech was recognized. Try again or type it.")
        return text
