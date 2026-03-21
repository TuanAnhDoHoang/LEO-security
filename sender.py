"""
sender.py — Ground Station HCMC (GS-46)
─────────────────────────────────────────────────────────────────
Gửi dữ liệu qua Satellite Node đến Singapore (GS-63).

Mode:
  plain     — plaintext UDP, eavesdropper đọc được toàn bộ
  encrypted — AES-256-GCM + ECDH key exchange, eavesdropper thấy ciphertext
  replay    — gửi lại cùng 1 packet để test replay protection

Chạy:
  python3 sender.py plain
  python3 sender.py encrypted
  python3 sender.py replay
"""

import socket
import sys
import os
import time
import struct
import json
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ── Địa chỉ ───────────────────────────────────────────────────────────────────
SAT_HOST = "10.0.0.1"
SAT_PORT = 9000          # gửi đến Satellite Node
KEY_HOST = "10.0.0.3"
KEY_PORT = 9100          # kênh trao đổi public key với receiver

# ── Dữ liệu mẫu — nội dung "nhạy cảm" để minh họa eavesdropping ──────────────
MESSAGES = [
    b"GS46-HCMC | COORD: 10.75N 106.67E | STATUS: OPERATIONAL",
    b"GS46-HCMC | UPLINK-TOKEN: X7F2-K9QM-3T1A | AUTH: VALID",
    b"GS46-HCMC | CMD: SAT-042 ADJUST ORBIT +0.5deg",
    b"GS46-HCMC | CRYPTO-KEY-HINT: rotate-at-epoch-1200",
    b"GS46-HCMC | PAYLOAD: sensor_data_batch_2024_classified",
]

GREEN = "\033[92m"; CYAN = "\033[96m"; AMBER = "\033[93m"
RED   = "\033[91m"; DIM  = "\033[2m";  RESET = "\033[0m"

PACKET_COUNT = 10   # số packet mỗi lần chạy
INTERVAL_S   = 0.5  # giây giữa các packet


# ─────────────────────────────────────────────────────────────────────────────
# PACKET FORMAT
# ─────────────────────────────────────────────────────────────────────────────
def build_plain_packet(seq, payload):
    """
    [1B type=0x01][4B seq][2B len][payload]
    Không mã hóa — eavesdropper đọc được trực tiếp.
    """
    return struct.pack("!BIH", 0x01, seq, len(payload)) + payload


def build_encrypted_packet(seq, payload, aesgcm, session_id):
    """
    [1B type=0x02][4B seq][12B nonce][2B len_ct][ciphertext+tag]
    AES-256-GCM: authenticated encryption, replay-protected qua nonce.
    AAD (Additional Authenticated Data) = session_id + seq
      → đảm bảo packet không thể reuse sang session khác.
    """
    nonce = os.urandom(12)
    aad   = session_id + struct.pack("!I", seq)   # bind to this session+seq
    ct    = aesgcm.encrypt(nonce, payload, aad)
    return struct.pack("!BIH", 0x02, seq, len(ct)) + nonce + ct


# ─────────────────────────────────────────────────────────────────────────────
# KEY EXCHANGE — ECDH X25519
# ─────────────────────────────────────────────────────────────────────────────
def do_key_exchange():
    """
    1. Sender sinh private key
    2. Gửi public key đến receiver qua kênh riêng (port 9100)
    3. Nhận public key của receiver
    4. Tính shared secret → derive AES-256 key bằng HKDF
    """
    priv = X25519PrivateKey.generate()
    pub  = priv.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw
    )

    # Kết nối đến receiver để trao đổi key
    ks = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ks.connect((KEY_HOST, KEY_PORT))

    ks.sendall(pub)                      # gửi public key của mình
    peer_pub_raw = ks.recv(32)           # nhận public key của receiver
    session_id   = ks.recv(16)           # nhận session ID
    ks.close()

    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
    peer_pub = X25519PublicKey.from_public_bytes(peer_pub_raw)
    shared   = priv.exchange(peer_pub)

    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32, salt=None,
        info=b"LEO-SAT-E2EE-HCMC-SGP"
    ).derive(shared)

    print(f"{GREEN}[KEY] ECDH X25519 hoàn tất{RESET}")
    print(f"{DIM}  Shared secret (first 8B): {shared[:8].hex()}{RESET}")
    print(f"{DIM}  AES key (first 8B)      : {key[:8].hex()}{RESET}")
    print(f"{DIM}  Session ID              : {session_id.hex()}{RESET}")

    return key, session_id


# ─────────────────────────────────────────────────────────────────────────────
# MODES
# ─────────────────────────────────────────────────────────────────────────────
def run_plain(sock):
    print(f"\n{AMBER}{'─'*56}")
    print(f"  MODE: PLAINTEXT — Eavesdropper sẽ đọc được toàn bộ!")
    print(f"{'─'*56}{RESET}\n")

    for seq in range(PACKET_COUNT):
        msg = MESSAGES[seq % len(MESSAGES)]
        pkt = build_plain_packet(seq, msg)
        sock.sendto(pkt, (SAT_HOST, SAT_PORT))

        print(f"{AMBER}[TX #{seq:02d}]{RESET} PLAIN  "
              f"{len(pkt):>4}B  payload: {msg.decode()}")
        time.sleep(INTERVAL_S)


def run_encrypted(sock):
    print(f"\n{GREEN}{'─'*56}")
    print(f"  MODE: ENCRYPTED — AES-256-GCM + ECDH X25519")
    print(f"{'─'*56}{RESET}\n")

    print(f"{CYAN}[KEY] Bắt đầu ECDH key exchange...{RESET}")
    key, session_id = do_key_exchange()
    aesgcm = AESGCM(key)
    print()

    for seq in range(PACKET_COUNT):
        msg = MESSAGES[seq % len(MESSAGES)]
        pkt = build_encrypted_packet(seq, msg, aesgcm, session_id)
        sock.sendto(pkt, (SAT_HOST, SAT_PORT))

        # Hiển thị: payload thật vs những gì eavesdropper thấy
        # (nonce=12B + ciphertext bắt đầu sau header 7B)
        visible = pkt[7+12:7+12+16]  # 16B đầu của ciphertext
        print(f"{GREEN}[TX #{seq:02d}]{RESET} ENCR   "
              f"{len(pkt):>4}B  "
              f"eavesdropper thấy: {visible.hex()}...")
        time.sleep(INTERVAL_S)


def run_replay(sock):
    """
    Gửi cùng 1 packet 5 lần để demo replay attack.
    Receiver có replay window sẽ reject packet trùng seq.
    """
    print(f"\n{RED}{'─'*56}")
    print(f"  MODE: REPLAY ATTACK — gửi lại cùng 1 packet")
    print(f"{'─'*56}{RESET}\n")

    print(f"{CYAN}[KEY] Key exchange cho replay test...{RESET}")
    key, session_id = do_key_exchange()
    aesgcm = AESGCM(key)
    print()

    msg = b"GS46-HCMC | CMD: LAUNCH-SEQUENCE-ALPHA"
    pkt = build_encrypted_packet(0, msg, aesgcm, session_id)  # seq=0 cố định

    for i in range(5):
        sock.sendto(pkt, (SAT_HOST, SAT_PORT))
        print(f"{RED}[TX REPLAY #{i}]{RESET}  "
              f"Gửi lại packet seq=0 → receiver nên reject từ lần 2")
        time.sleep(0.3)


# ─────────────────────────────────────────────────────────────────────────────
def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "plain"

    print(f"{CYAN}{'═'*56}")
    print(f"  📡 GROUND STATION — HCMC (GS-46)")
    print(f"{'═'*56}{RESET}")
    print(f"  → Satellite : {SAT_HOST}:{SAT_PORT}")
    print(f"  → Route     : HCMC → Singapore (RTT ≈ 12ms, Hypatia)")
    print(f"  → Mode      : {mode.upper()}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    if mode == "plain":
        run_plain(sock)
    elif mode == "encrypted":
        run_encrypted(sock)
    elif mode == "replay":
        run_replay(sock)
    else:
        print(f"Usage: python3 sender.py [plain|encrypted|replay]")
        sys.exit(1)

    sock.close()
    print(f"\n{DIM}[TX] Xong.{RESET}")


if __name__ == "__main__":
    main()
