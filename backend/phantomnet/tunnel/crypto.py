"""Noise Protocol (XX pattern with 25519, ChaCha20-Poly1305, BLAKE2s) session manager."""

from __future__ import annotations

import os
import time
from typing import Any

from cryptography.exceptions import InvalidTag
from noise.connection import Keypair, NoiseConnection
from noise.exceptions import (
    NoiseHandshakeError,
    NoiseInvalidMessage,
    NoiseMaxNonceError,
    NoiseProtocolNameError,
    NoiseValidationError,
    NoiseValueError,
)

NoiseError = (
    NoiseHandshakeError,
    NoiseInvalidMessage,
    NoiseMaxNonceError,
    NoiseProtocolNameError,
    NoiseValidationError,
    NoiseValueError,
)

PROTOCOL_NAME = b"Noise_XX_25519_ChaChaPoly_BLAKE2s"


class CryptoError(Exception):
    """Base exception for cryptographic failures and verification errors."""


class TamperError(CryptoError):
    """Raised when ciphertext integrity or authentication tag check fails."""


class NoiseSession:
    """Manages Noise XX protocol state machine, encryption, decryption, and rekeying."""

    def __init__(
        self,
        is_initiator: bool,
        static_private_key: bytes | None = None,
        rekey_after_packets: int = 1000,
        rekey_after_seconds: float = 300.0,
    ) -> None:
        self.is_initiator = is_initiator
        self.rekey_after_packets = rekey_after_packets
        self.rekey_after_seconds = rekey_after_seconds

        self.static_private_key = static_private_key or os.urandom(32)
        self.session_id = f"sess-{os.urandom(4).hex()}"

        self._conn = NoiseConnection.from_name(PROTOCOL_NAME)
        self._conn.set_keypair_from_private_bytes(Keypair.STATIC, self.static_private_key)

        if is_initiator:
            self._conn.set_as_initiator()
        else:
            self._conn.set_as_responder()

        self._conn.start_handshake()

        self.tx_packet_count = 0
        self.rx_packet_count = 0
        self.last_rekey_time = time.monotonic()
        self.rekey_epoch = 1

    @property
    def handshake_finished(self) -> bool:
        finished: bool = self._conn.handshake_finished
        return finished

    def write_handshake_message(self, payload: bytes = b"") -> bytes:
        """Produce the next outbound handshake message."""
        try:
            msg: bytes = self._conn.write_message(payload)
            return msg
        except NoiseError as e:
            raise CryptoError(f"Noise handshake write failed: {e}") from e

    def read_handshake_message(self, message: bytes) -> bytes:
        """Consume an inbound handshake message."""
        try:
            payload: bytes = self._conn.read_message(message)
            return payload
        except (NoiseInvalidMessage, InvalidTag) as e:
            raise TamperError(f"Handshake authentication tag verification failed: {e}") from e
        except NoiseError as e:
            raise CryptoError(f"Noise handshake read failed: {e}") from e

    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt transport payload using ChaCha20-Poly1305 with monotonic nonce."""
        if not self.handshake_finished:
            raise CryptoError("Cannot encrypt before handshake completion")

        try:
            ciphertext: bytes = self._conn.encrypt(plaintext)
            self.tx_packet_count += 1
            return ciphertext
        except NoiseError as e:
            raise CryptoError(f"Encryption failed: {e}") from e

    def decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypt and verify transport payload. Raises TamperError on bit-flip / MAC error."""
        if not self.handshake_finished:
            raise CryptoError("Cannot decrypt before handshake completion")

        try:
            plaintext: bytes = self._conn.decrypt(ciphertext)
            self.rx_packet_count += 1
            return plaintext
        except NoiseInvalidMessage as e:
            raise TamperError(
                "Message authentication tag verification failed (tampered ciphertext)"
            ) from e
        except NoiseError as e:
            raise CryptoError(f"Decryption failed: {e}") from e

    def should_rekey(self) -> bool:
        """Check if packet thresholds or time limits require a cipher rekey."""
        if self.tx_packet_count >= self.rekey_after_packets:
            return True
        return time.monotonic() - self.last_rekey_time >= self.rekey_after_seconds

    def rekey_outbound(self) -> None:
        """Advance the outbound cipher key."""
        try:
            self._conn.rekey_outbound_cipher()
            self.tx_packet_count = 0
            self.last_rekey_time = time.monotonic()
            self.rekey_epoch += 1
        except NoiseError as e:
            raise CryptoError(f"Rekey outbound failed: {e}") from e

    def rekey_inbound(self) -> None:
        """Advance the inbound cipher key."""
        try:
            self._conn.rekey_inbound_cipher()
            self.rx_packet_count = 0
        except NoiseError as e:
            raise CryptoError(f"Rekey inbound failed: {e}") from e

    def get_telemetry(self) -> dict[str, Any]:
        """Return diagnostic crypto metadata for event emission."""
        return {
            "session_id": self.session_id,
            "cipher": "ChaCha20-Poly1305",
            "kdf": "BLAKE2s",
            "curve": "X25519",
            "epoch": self.rekey_epoch,
            "tx_count": self.tx_packet_count,
            "rx_count": self.rx_packet_count,
        }
