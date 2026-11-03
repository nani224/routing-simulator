"""Crypto tests: Noise test vectors, tamper detection, anti-replay, and nonce uniqueness."""

from __future__ import annotations

import os

import pytest
from hypothesis import given
from hypothesis import strategies as st
from phantomnet.tunnel.crypto import NoiseSession, TamperError
from phantomnet.tunnel.replay_window import ReplayWindow


def test_noise_handshake_vectors() -> None:
    """Verify Noise XX pattern test vector: exact lengths (32B, 96B, 64B) and completion."""
    init_key = os.urandom(32)
    resp_key = os.urandom(32)

    init = NoiseSession(is_initiator=True, static_private_key=init_key)
    resp = NoiseSession(is_initiator=False, static_private_key=resp_key)

    assert not init.handshake_finished
    assert not resp.handshake_finished

    # Msg 1: -> e (32 bytes)
    m1 = init.write_handshake_message()
    assert len(m1) == 32
    resp.read_handshake_message(m1)

    # Msg 2: <- e, ee, s, es (96 bytes)
    m2 = resp.write_handshake_message()
    assert len(m2) == 96
    init.read_handshake_message(m2)

    # Msg 3: -> s, se (64 bytes)
    m3 = init.write_handshake_message()
    assert len(m3) == 64
    resp.read_handshake_message(m3)

    assert init.handshake_finished
    assert resp.handshake_finished

    # Transport roundtrip
    plaintext = b"PHANTOMNET test vector transport data"
    ct = init.encrypt(plaintext)
    decrypted = resp.decrypt(ct)
    assert decrypted == plaintext


def test_tamper_detection_flip_one_bit() -> None:
    """Tamper test: flipping a single bit anywhere in ciphertext triggers TamperError."""
    init = NoiseSession(is_initiator=True)
    resp = NoiseSession(is_initiator=False)

    # Handshake
    resp.read_handshake_message(init.write_handshake_message())
    init.read_handshake_message(resp.write_handshake_message())
    resp.read_handshake_message(init.write_handshake_message())

    plaintext = b"Confidential stealth routing packet payload"
    ciphertext = init.encrypt(plaintext)

    # Test bit flips across multiple byte positions
    for bit_pos in (0, 1, 5, len(ciphertext) - 1):
        tampered = bytearray(ciphertext)
        tampered[bit_pos] ^= 0x01
        with pytest.raises(TamperError):
            resp.decrypt(bytes(tampered))


def test_anti_replay_window_rejection() -> None:
    """Replay test: resent frame sequence number must be rejected by sliding window."""
    win = ReplayWindow(window_size=64)

    assert win.check_and_update(1) is True
    assert win.check_and_update(2) is True
    assert win.check_and_update(3) is True

    # Replay sequence 2 -> must reject
    assert win.check_and_update(2) is False

    # Out of order but within window
    assert win.check_and_update(10) is True
    assert win.check_and_update(8) is True
    assert win.check_and_update(8) is False  # Replay of 8

    # Sequence far in advance
    assert win.check_and_update(100) is True
    # Sequence 1 is now older than window_size (100 - 64 = 36) -> must reject
    assert win.check_and_update(1) is False
    assert win.check_and_update(35) is False
    assert win.check_and_update(70) is True  # Within window of 100


@given(sequences=st.lists(st.integers(min_value=1, max_value=500), min_size=5, max_size=100))
def test_anti_replay_property(sequences: list[int]) -> None:
    """Property test: no duplicate sequence is ever accepted more than once."""
    win = ReplayWindow(window_size=128)
    seen_accepted: set[int] = set()

    for seq in sequences:
        accepted = win.check_and_update(seq)
        if accepted:
            assert seq not in seen_accepted
            seen_accepted.add(seq)


def test_nonce_uniqueness_property() -> None:
    """Verify that packet counters and nonces strictly increment and never repeat."""
    init = NoiseSession(is_initiator=True)
    resp = NoiseSession(is_initiator=False)

    resp.read_handshake_message(init.write_handshake_message())
    init.read_handshake_message(resp.write_handshake_message())
    resp.read_handshake_message(init.write_handshake_message())

    tx_counts: list[int] = []
    for i in range(50):
        init.encrypt(f"packet-{i}".encode())
        tx_counts.append(init.tx_packet_count)

    # Monotonically increasing with zero collisions
    assert tx_counts == list(range(1, 51))
    assert len(set(tx_counts)) == 50


def test_gate_d_padded_handshake_completion() -> None:
    """Gate D: Handshake payload padding succeeds, decrypts payload, and preserves transport."""
    init = NoiseSession(is_initiator=True)
    resp = NoiseSession(is_initiator=False)

    pad1 = os.urandom(128)
    pad2 = os.urandom(256)
    pad3 = os.urandom(64)

    # Msg 1 with 128B padding
    m1 = init.write_handshake_message(pad1)
    assert len(m1) == 32 + 128
    got_p1 = resp.read_handshake_message(m1)
    assert got_p1 == pad1

    # Msg 2 with 256B padding (encrypted payload in Noise XX Msg 2)
    m2 = resp.write_handshake_message(pad2)
    assert len(m2) == 96 + 256
    got_p2 = init.read_handshake_message(m2)
    assert got_p2 == pad2

    # Msg 3 with 64B padding (encrypted payload in Noise XX Msg 3)
    m3 = init.write_handshake_message(pad3)
    assert len(m3) == 64 + 64
    got_p3 = resp.read_handshake_message(m3)
    assert got_p3 == pad3

    assert init.handshake_finished
    assert resp.handshake_finished

    # Transport data after padded handshake
    msg = b"Transport data over padded Noise XX session"
    ct = init.encrypt(msg)
    pt = resp.decrypt(ct)
    assert pt == msg


def test_gate_d_padded_handshake_tamper() -> None:
    """Gate D: Tampering with padded handshake message payload triggers CryptoError."""
    init = NoiseSession(is_initiator=True)
    resp = NoiseSession(is_initiator=False)

    pad1 = os.urandom(100)
    m1 = bytearray(init.write_handshake_message(pad1))

    # In Msg 1, payload is cleartext (e only), so read_handshake_message accepts it.
    resp.read_handshake_message(bytes(m1))

    # Msg 2 has Poly1305 MAC over the encrypted payload. Tampering must fail.
    pad2 = os.urandom(150)
    m2 = bytearray(resp.write_handshake_message(pad2))
    m2[len(m2) - 10] ^= 0x01  # Flip bit in encrypted payload/MAC

    from phantomnet.tunnel.crypto import CryptoError

    with pytest.raises(CryptoError):
        init.read_handshake_message(bytes(m2))
