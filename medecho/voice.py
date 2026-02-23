"""
Voice Interface Module for MedEcho
Handles Voice Activity Detection (VAD), audio recording,
MedASR transcription, and PII redaction.
"""

import io
import re
import wave
import struct
import logging
import datetime
from pathlib import Path
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)

# ── PII Redaction ──────────────────────────────────────────────────────────────

# Regex patterns for common PII found in clinical speech
_PII_PATTERNS = [
    # Full names: "John Smith", "Dr. Jane Doe"
    (
        re.compile(
            r"\b(?:Dr\.?\s+|Mr\.?\s+|Ms\.?\s+|Mrs\.?\s+)?[A-Z][a-z]+-?[A-Z]?[a-z]*\s+[A-Z][a-z]+-?[A-Z]?[a-z]*\b"
        ),
        "[NAME]",
    ),
    # US phone numbers: (555) 123-4567, 555-123-4567, 5551234567
    (
        re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        "[PHONE]",
    ),
    # US Social Security Numbers
    (re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"), "[SSN]"),
    # Dates of birth when explicitly stated: "born on 01/15/1980"
    (
        re.compile(
            r"\bborn\s+(?:on\s+)?\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b",
            re.IGNORECASE,
        ),
        "born on [DOB]",
    ),
    # Email addresses
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b", re.IGNORECASE), "[EMAIL]"),
    # Medical record numbers: "MRN 123456", "record number 78910"
    (
        re.compile(
            r"\b(?:MRN|medical\s+record(?:\s+number)?)\s*:?\s*\d{4,10}\b",
            re.IGNORECASE,
        ),
        "[MRN]",
    ),
    # ZIP codes (standalone 5- or 9-digit)
    (re.compile(r"\b\d{5}(?:-\d{4})?\b"), "[ZIP]"),
]


def redact_pii(text: str) -> Tuple[str, List[str]]:
    """
    Redact PII from transcribed text using regex patterns.

    Returns:
        (redacted_text, list_of_redaction_labels)
    """
    redacted = text
    labels_found: List[str] = []

    for pattern, label in _PII_PATTERNS:
        matches = pattern.findall(redacted)
        if matches:
            labels_found.append(label)
        redacted = pattern.sub(label, redacted)

    return redacted, labels_found


# ── Audio helpers ──────────────────────────────────────────────────────────────

SAMPLE_RATE = 16000  # Hz – required by webrtcvad and MedASR
FRAME_DURATION_MS = 30  # ms per VAD frame (10, 20, or 30 ms supported)
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)  # samples per frame
VAD_AGGRESSIVENESS = 2  # 0–3; higher = more aggressive speech filtering


def bytes_to_wav(pcm_bytes: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Wrap raw 16-bit mono PCM bytes in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def pcm_frames(pcm_bytes: bytes, frame_size: int = FRAME_SIZE) -> List[bytes]:
    """Split raw PCM bytes into frames of *frame_size* samples (2 bytes each)."""
    frame_bytes = frame_size * 2  # 16-bit → 2 bytes per sample
    return [
        pcm_bytes[i : i + frame_bytes]
        for i in range(0, len(pcm_bytes) - frame_bytes + 1, frame_bytes)
    ]


# ── Voice Activity Detection ───────────────────────────────────────────────────


class VoiceActivityDetector:
    """
    Wraps webrtcvad to filter silent frames from audio recordings.
    Falls back gracefully when webrtcvad is not installed.
    """

    def __init__(self, aggressiveness: int = VAD_AGGRESSIVENESS):
        self._available = False
        try:
            import webrtcvad  # type: ignore

            self._vad = webrtcvad.Vad(aggressiveness)
            self._available = True
            logger.info("webrtcvad loaded (aggressiveness=%d)", aggressiveness)
        except ImportError:
            logger.warning(
                "webrtcvad not installed – VAD disabled. "
                "Install with: pip install webrtcvad"
            )

    @property
    def available(self) -> bool:
        return self._available

    def is_speech(self, frame: bytes, sample_rate: int = SAMPLE_RATE) -> bool:
        """Return True if *frame* contains speech."""
        if not self._available:
            return True  # assume speech when VAD unavailable
        try:
            return self._vad.is_speech(frame, sample_rate)
        except Exception:
            return True

    def filter_speech(
        self,
        pcm_bytes: bytes,
        frame_size: int = FRAME_SIZE,
        sample_rate: int = SAMPLE_RATE,
    ) -> bytes:
        """Return only speech frames concatenated together."""
        frames = pcm_frames(pcm_bytes, frame_size)
        speech_frames = [f for f in frames if self.is_speech(f, sample_rate)]
        return b"".join(speech_frames)


# ── MedASR Transcription ───────────────────────────────────────────────────────


class MedASRClient:
    """
    Client for MedASR – Google's medical speech recognition model
    (part of HAI-DEF suite), optimised for radiology dictation.

    Falls back to OpenAI Whisper (local) when the API is unavailable.
    """

    def __init__(self, api_key: Optional[str] = None, use_local_fallback: bool = True):
        self._api_key = api_key
        self._use_local_fallback = use_local_fallback
        self._local_model = None  # lazy-loaded Whisper model

    # ------------------------------------------------------------------
    def transcribe(
        self, audio_bytes: bytes, language: str = "en-US"
    ) -> dict:
        """
        Transcribe audio.

        Parameters
        ----------
        audio_bytes : bytes
            Raw WAV or PCM audio data.
        language : str
            BCP-47 language tag.

        Returns
        -------
        dict with keys:
            text        – transcription string
            confidence  – float [0, 1]
            source      – "medasr" | "whisper" | "none"
        """
        if self._api_key:
            try:
                return self._transcribe_medasr(audio_bytes, language)
            except Exception as exc:
                logger.warning("MedASR API failed (%s); falling back to Whisper.", exc)

        if self._use_local_fallback:
            try:
                return self._transcribe_whisper(audio_bytes)
            except Exception as exc:
                logger.error("Whisper fallback failed: %s", exc)

        return {"text": "", "confidence": 0.0, "source": "none"}

    # ------------------------------------------------------------------
    def _transcribe_medasr(self, audio_bytes: bytes, language: str) -> dict:
        """Call Google Cloud Speech-to-Text v2 / MedASR endpoint."""
        from google.cloud import speech  # type: ignore

        client = speech.SpeechClient(
            client_options={"api_key": self._api_key} if self._api_key else {}
        )

        # Ensure WAV wrapper
        if not audio_bytes[:4] == b"RIFF":
            audio_bytes = bytes_to_wav(audio_bytes)

        audio = speech.RecognitionAudio(content=audio_bytes)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=SAMPLE_RATE,
            language_code=language,
            model="medical_dictation",  # MedASR model selector
            enable_automatic_punctuation=True,
            use_enhanced=True,
        )

        response = client.recognize(config=config, audio=audio)
        if not response.results:
            return {"text": "", "confidence": 0.0, "source": "medasr"}

        best = max(
            response.results, key=lambda r: r.alternatives[0].confidence
        )
        alt = best.alternatives[0]
        return {
            "text": alt.transcript.strip(),
            "confidence": alt.confidence,
            "source": "medasr",
        }

    # ------------------------------------------------------------------
    def _transcribe_whisper(self, audio_bytes: bytes) -> dict:
        """Transcribe with OpenAI Whisper (runs locally, no internet needed)."""
        import tempfile
        import whisper  # type: ignore

        if self._local_model is None:
            logger.info("Loading Whisper model (first call may be slow)…")
            self._local_model = whisper.load_model("base.en")

        # Write to a temp WAV file because Whisper expects a file path
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_data = bytes_to_wav(audio_bytes) if audio_bytes[:4] != b"RIFF" else audio_bytes
            tmp.write(wav_data)
            tmp_path = tmp.name

        result = self._local_model.transcribe(tmp_path, language="en", fp16=False)
        Path(tmp_path).unlink(missing_ok=True)

        return {
            "text": result.get("text", "").strip(),
            "confidence": 0.85,  # Whisper doesn't return per-utterance confidence
            "source": "whisper",
        }


# ── Audio Recorder ─────────────────────────────────────────────────────────────


class AudioRecorder:
    """
    Records audio from the microphone with optional VAD gating.

    Uses sounddevice for cross-platform microphone access.
    """

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        vad: Optional[VoiceActivityDetector] = None,
    ):
        self._sample_rate = sample_rate
        self._vad = vad or VoiceActivityDetector()
        self._frames: List[bytes] = []
        self._recording = False

    # ------------------------------------------------------------------
    @property
    def is_recording(self) -> bool:
        return self._recording

    # ------------------------------------------------------------------
    def record_chunk(self, duration_s: float = 2.0) -> bytes:
        """
        Record *duration_s* seconds of audio, returning speech-only PCM bytes.
        """
        try:
            import sounddevice as sd  # type: ignore
            import numpy as np

            frames = int(self._sample_rate * duration_s)
            audio = sd.rec(
                frames,
                samplerate=self._sample_rate,
                channels=1,
                dtype="int16",
                blocking=True,
            )
            pcm = audio.flatten().astype("int16").tobytes()
            return self._vad.filter_speech(pcm) if self._vad.available else pcm
        except ImportError:
            logger.error(
                "sounddevice not installed. Install with: pip install sounddevice"
            )
            return b""
        except Exception as exc:
            logger.error("Recording failed: %s", exc)
            return b""

    # ------------------------------------------------------------------
    def save_offline(self, pcm_bytes: bytes, out_dir: Path = Path("offline_audio")) -> Path:
        """Save raw PCM as WAV for later processing (offline fallback)."""
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        path = out_dir / f"encounter_{ts}.wav"
        path.write_bytes(bytes_to_wav(pcm_bytes, self._sample_rate))
        logger.info("Offline audio saved → %s", path)
        return path
