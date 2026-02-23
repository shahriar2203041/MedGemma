"""
Offline Fallback Module for MedEcho
Manages local storage of audio and images when internet connectivity is lost.
"""

import json
import logging
import os
import shutil
import socket
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# ── Connectivity check ─────────────────────────────────────────────────────────

_CHECK_HOSTS = [
    ("8.8.8.8", 53),     # Google DNS
    ("1.1.1.1", 53),     # Cloudflare DNS
]
_TIMEOUT_S = 2.0


def is_online() -> bool:
    """Return True if internet connectivity is available."""
    for host, port in _CHECK_HOSTS:
        try:
            socket.setdefaulttimeout(_TIMEOUT_S)
            with socket.create_connection((host, port)):
                return True
        except OSError:
            continue
    return False


# ── Offline Store ──────────────────────────────────────────────────────────────


class OfflineStore:
    """
    Manages local storage of encounters, audio files, and images
    when the device has no internet connection.

    Directory layout:
        <base_dir>/
            audio/        raw WAV recordings
            images/       uploaded medical images
            metadata/     JSON metadata per encounter
            processed/    encounters successfully uploaded/processed
    """

    def __init__(self, base_dir: Union[str, Path] = "offline_data"):
        self._base = Path(base_dir)
        self._audio_dir = self._base / "audio"
        self._image_dir = self._base / "images"
        self._meta_dir = self._base / "metadata"
        self._proc_dir = self._base / "processed"

        for d in (self._audio_dir, self._image_dir, self._meta_dir, self._proc_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    def _ts(self) -> str:
        return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    # ------------------------------------------------------------------
    def save_audio(self, wav_bytes: bytes, encounter_id: Optional[str] = None) -> Path:
        """Persist raw WAV audio for later processing."""
        eid = encounter_id or self._ts()
        path = self._audio_dir / f"{eid}.wav"
        path.write_bytes(wav_bytes)
        logger.info("Offline audio saved → %s", path)
        return path

    # ------------------------------------------------------------------
    def save_image(
        self,
        image_bytes: bytes,
        encounter_id: Optional[str] = None,
        suffix: str = ".png",
    ) -> Path:
        """Persist a medical image for later analysis."""
        eid = encounter_id or self._ts()
        path = self._image_dir / f"{eid}{suffix}"
        path.write_bytes(image_bytes)
        logger.info("Offline image saved → %s", path)
        return path

    # ------------------------------------------------------------------
    def save_metadata(self, metadata: Dict, encounter_id: Optional[str] = None) -> Path:
        """Persist encounter metadata as JSON."""
        eid = encounter_id or self._ts()
        path = self._meta_dir / f"{eid}.json"
        path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Offline metadata saved → %s", path)
        return path

    # ------------------------------------------------------------------
    def list_pending(self) -> List[Dict]:
        """Return a list of pending offline encounters (not yet processed)."""
        pending = []
        for meta_file in sorted(self._meta_dir.glob("*.json")):
            try:
                data = json.loads(meta_file.read_text(encoding="utf-8"))
                data["_meta_path"] = str(meta_file)
                pending.append(data)
            except Exception as exc:
                logger.warning("Could not read %s: %s", meta_file, exc)
        return pending

    # ------------------------------------------------------------------
    def mark_processed(self, encounter_id: str) -> None:
        """Move processed metadata to the 'processed' subdirectory."""
        src = self._meta_dir / f"{encounter_id}.json"
        if src.exists():
            dst = self._proc_dir / src.name
            shutil.move(str(src), str(dst))
            logger.info("Encounter %s marked as processed.", encounter_id)

    # ------------------------------------------------------------------
    def get_stats(self) -> Dict:
        """Return storage statistics."""
        return {
            "pending_encounters": len(list(self._meta_dir.glob("*.json"))),
            "offline_audio_files": len(list(self._audio_dir.glob("*.wav"))),
            "offline_images": len(list(self._image_dir.glob("*"))),
            "processed_encounters": len(list(self._proc_dir.glob("*.json"))),
            "total_size_mb": round(
                sum(f.stat().st_size for f in self._base.rglob("*") if f.is_file())
                / (1024 * 1024),
                2,
            ),
        }


# ── Connection Monitor ─────────────────────────────────────────────────────────


class ConnectionMonitor:
    """
    Polls connectivity and fires callbacks on state changes.
    Designed to run in a background thread.
    """

    def __init__(
        self,
        poll_interval_s: float = 10.0,
        on_online=None,
        on_offline=None,
    ):
        self._interval = poll_interval_s
        self._on_online = on_online or (lambda: None)
        self._on_offline = on_offline or (lambda: None)
        self._last_state: Optional[bool] = None
        self._running = False

    # ------------------------------------------------------------------
    def start(self) -> None:
        """Start monitoring in a daemon thread."""
        import threading

        self._running = True
        thread = threading.Thread(target=self._loop, daemon=True)
        thread.start()
        logger.info("ConnectionMonitor started (poll interval: %ss)", self._interval)

    # ------------------------------------------------------------------
    def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------
    def _loop(self) -> None:
        while self._running:
            current = is_online()
            if current != self._last_state:
                if current:
                    logger.info("Connection restored – back online.")
                    self._on_online()
                else:
                    logger.warning("Connection lost – switching to offline mode.")
                    self._on_offline()
                self._last_state = current
            time.sleep(self._interval)
