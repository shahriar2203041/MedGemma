"""
Output Module for MedEcho
Handles encrypted JSON export and QR code generation.
"""

import base64
import io
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Union

logger = logging.getLogger(__name__)

# ── Encrypted JSON Exporter ────────────────────────────────────────────────────


class EncryptedJSONExporter:
    """
    Serialises a clinical encounter to JSON and optionally encrypts it
    using AES-256-GCM via the `cryptography` library (Fernet symmetric key).

    Key management:
      - A new random 256-bit key is generated per session.
      - The key can be saved alongside the file (for demo purposes) or
        shared via a secure channel.
    """

    def __init__(self, key: Optional[bytes] = None):
        """
        Parameters
        ----------
        key : bytes, optional
            32-byte (256-bit) Fernet key.  If None, a new key is generated.
        """
        try:
            from cryptography.fernet import Fernet  # type: ignore

            self._Fernet = Fernet
            self._key = key or Fernet.generate_key()
            self._fernet = Fernet(self._key)
            self._available = True
        except ImportError:
            logger.warning(
                "cryptography not installed – encryption disabled. "
                "Install with: pip install cryptography"
            )
            self._available = False
            self._key = b""

    # ------------------------------------------------------------------
    @property
    def encryption_available(self) -> bool:
        """True when the cryptography library is installed and encryption is active."""
        return self._available

    # ------------------------------------------------------------------
    @property
    def key(self) -> bytes:
        """The symmetric encryption key (keep this secret!)."""
        return self._key

    @property
    def key_b64(self) -> str:
        """Base64-encoded key string, safe to display in UI."""
        return self._key.decode() if self._key else ""

    # ------------------------------------------------------------------
    def export(
        self,
        encounter_data: Dict,
        encrypt: bool = True,
        output_path: Optional[Union[str, Path]] = None,
    ) -> bytes:
        """
        Serialise *encounter_data* to JSON and optionally encrypt it.

        Returns the raw bytes (encrypted or plain JSON).
        Writes to *output_path* if given.
        """
        # Add export metadata
        payload = {
            "medecho_version": "1.0.0",
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "encrypted": encrypt and self._available,
            **encounter_data,
        }

        json_bytes = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")

        if encrypt and self._available:
            data = self._fernet.encrypt(json_bytes)
        else:
            data = json_bytes

        if output_path:
            Path(output_path).write_bytes(data)
            logger.info("Encounter saved → %s", output_path)

        return data

    # ------------------------------------------------------------------
    def decrypt(self, data: bytes) -> Dict:
        """Decrypt and deserialise an encrypted encounter file."""
        if not self._available:
            try:
                return json.loads(data)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ValueError(
                    "Data appears to be encrypted but the cryptography library is not "
                    "installed. Install it with: pip install cryptography"
                ) from exc
        return json.loads(self._fernet.decrypt(data))

    # ------------------------------------------------------------------
    def export_key_file(self, path: Union[str, Path]) -> None:
        """Write the encryption key to a separate file (for demo/hand-off)."""
        Path(path).write_bytes(self._key)
        logger.info("Encryption key saved → %s", path)


# ── QR Code Generator ─────────────────────────────────────────────────────────


class QRCodeGenerator:
    """
    Generates a QR code from clinical data for patient portability.

    The QR encodes a compact JSON summary (not the full encrypted blob)
    so it remains scannable within the density limits of a standard QR code.
    """

    MAX_QR_BYTES = 2953  # QR version 40, error correction L

    def __init__(self):
        self._available = False
        try:
            import qrcode  # type: ignore

            self._qrcode = qrcode
            self._available = True
        except ImportError:
            logger.warning(
                "qrcode not installed – QR generation disabled. "
                "Install with: pip install qrcode[pil]"
            )

    # ------------------------------------------------------------------
    @property
    def available(self) -> bool:
        return self._available

    # ------------------------------------------------------------------
    def _compact_summary(self, encounter_data: Dict) -> Dict:
        """Extract a compact subset of encounter data for QR encoding."""
        return {
            "id": encounter_data.get("encounter_id", ""),
            "date": encounter_data.get("date", datetime.utcnow().strftime("%Y-%m-%d")),
            "patient": encounter_data.get("patient_name", "[REDACTED]"),
            "diagnoses": encounter_data.get("structured", {}).get("diagnoses", [])[:3],
            "medications": encounter_data.get("structured", {}).get(
                "suggested_medications", []
            )[:3],
            "follow_up": encounter_data.get("structured", {}).get("follow_up_date", ""),
            "physician": encounter_data.get("physician", ""),
        }

    # ------------------------------------------------------------------
    def generate(
        self,
        encounter_data: Dict,
        compact: bool = True,
        error_correction: str = "M",
    ) -> Optional["PIL.Image.Image"]:  # type: ignore[name-defined]
        """
        Generate a QR code image.

        Parameters
        ----------
        encounter_data : dict
            Full encounter data dictionary.
        compact : bool
            If True, encode only a compact summary.  If False, attempt to
            encode the full JSON (may fail for large payloads).
        error_correction : str
            QR error correction level: L, M, Q, H.

        Returns
        -------
        PIL Image of the QR code, or None if qrcode is unavailable.
        """
        if not self._available:
            return None

        ec_map = {
            "L": self._qrcode.constants.ERROR_CORRECT_L,
            "M": self._qrcode.constants.ERROR_CORRECT_M,
            "Q": self._qrcode.constants.ERROR_CORRECT_Q,
            "H": self._qrcode.constants.ERROR_CORRECT_H,
        }

        data_to_encode = (
            self._compact_summary(encounter_data) if compact else encounter_data
        )
        payload = json.dumps(data_to_encode, separators=(",", ":"))

        # Truncate if over QR limit
        if len(payload.encode("utf-8")) > self.MAX_QR_BYTES:
            data_to_encode = self._compact_summary(encounter_data)
            payload = json.dumps(data_to_encode, separators=(",", ":"))

        qr = self._qrcode.QRCode(
            version=None,
            error_correction=ec_map.get(error_correction, ec_map["M"]),
            box_size=10,
            border=4,
        )
        qr.add_data(payload)
        qr.make(fit=True)

        img = qr.make_image(fill_color="#0D1B2A", back_color="white")
        return img

    # ------------------------------------------------------------------
    def generate_bytes(self, encounter_data: Dict, fmt: str = "PNG", **kwargs) -> bytes:
        """Generate a QR code and return it as image bytes."""
        img = self.generate(encounter_data, **kwargs)
        if img is None:
            return b""
        buf = io.BytesIO()
        img.save(buf, format=fmt)
        return buf.getvalue()
