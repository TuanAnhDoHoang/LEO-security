"""
receiver.py — Ground Station Singapore (GS-63)
────────────────────────────────────────────────────────────────
Nhận packet từ Satellite Node, giải mã (nếu encrypted),
xác thực HMAC/GCM tag, chống replay attack.

Đồng thời TAP một bản copy sang eavesdropper (port 9002)
để demo passive sniffing live.

Chạy: python3 receiver.py
"""

import socket
import struct
import os
import sys
import time
import threading
import collections
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey, X25519PublicKey
)
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

# ── Địa chỉ ───────────────────────────────────────────────────────────────────
RECV_HOST    = "10.0.0.3"
RECV_PORT    = 9001          # Satellite forward đến đây
KEY_HOST     = "10.0.0.3"
KEY_PORT     = 9100          # Kênh trao đổi key với sender
EAVES_HOST   = "10.0.0.2"
EAVES_PORT   = 9002          # TAP: copy packet cho eavesdropper

GREEN  = "\033[92m"; CYAN = "\033[96m"; AMBER = "\033[93m"
RED    = "\033[91m"; DIM  = "\033[2m";  BOLD  = "\033[1m"; RESET = "\033[0m"

REPLAY_WINDOW = 64           # bitmask window chống replay

# ─────────────────────────────────────────────────────────────────────────────
class ReplayFilter:
    """
    Sliding window replay protection.
    Reject bất kỳ seq nào đã thấy hoặc quá cũ (ngoài window).
    """
    def __init__(self, window=64):
        self.window   = window
        self.seen     = set()
        self.top_seq  = -1
        self.rejected = 0

    def check(self, seq) -> bool:
        """True = accept, False = reject (replay)."""
        if seq > self.top_seq:
            # Dịch window
            if self.top_seq >= 0:
                cutoff = seq - self.window
                self.seen = {s for s in self.seen if s >= cutoff}
            self.top_seq = seq
        elif seq < self.top_seq - self.window:
            self.rejected += 1
            return False   # quá cũ
        if seq in self.seen:
            self.rejected += 1
            return False   # đã thấy rồi
        self.seen.add(seq)
        return True


# ─────────────────────────────────────────────────────────────────────────────
class SessionState:
    """Trạng thái của một session E2EE."""
    def __init__(self, key: bytes, session_id: bytes):
        self.aesgcm     = AESGCM(key)
        self.session_id = session_id
        self.replay     = ReplayFilter(REPLAY_WINDOW)
        self.rx_ok      = 0
        self.rx_fail    = 0


# ─────────────────────────────────────────────────────────────────────────────
def do_key_exchange_server(key_sock) -> SessionState:
    """
    Chờ sender connect, trao đổi X25519 public key.
    Trả về SessionState với key đã derive.
    """
    conn, addr = key_sock.accept()
    print(f"{CYAN}[KEY] Sender kết nối từ {addr}{RESET}")

    peer_pub_raw = conn.recv(32)          # nhận pub key của sender
    session_id   = os.urandom(16)         # sinh session ID

    priv = X25519PrivateKey.generate()
    pub  = priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    conn.sendall(pub)                     # gửi pub key của mình
    conn.sendall(session_id)              # gửi session ID
    conn.close()

    peer_pub = X25519PublicKey.from_public_bytes(peer_pub_raw)
    shared   = priv.exchange(peer_pub)
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32, salt=None,
        info=b"LEO-SAT-E2EE-HCMC-SGP"
    ).derive(shared)

    print(f"{GREEN}[KEY] ECDH hoàn tất | session={session_id.hex()[:8]}...{RESET}")
    return SessionState(key, session_id)


# ─────────────────────────────────────────────────────────────────────────────
def handle_plain(seq, payload_raw, length, eaves_sock, raw):
    content = payload_raw[:length]
    eaves_sock.sendto(raw, (EAVES_HOST, EAVES_PORT))   # tap for eavesdropper

    print(f"\n{AMBER}[RX #{seq:02d}]{RESET} PLAINTEXT  {length}B")
    print(f"  {AMBER}⚠  KHÔNG mã hóa — payload lộ hoàn toàn:{RESET}")
    try:
        print(f"  └─ {content.decode()}")
    except Exception:
        print(f"  └─ {content}")


def handle_encrypted(seq, payload_raw, session: SessionState,
                      eaves_sock, raw):
    # Tap bản copy (ciphertext) cho eavesdropper trước khi decrypt
    eaves_sock.sendto(raw, (EAVES_HOST, EAVES_PORT))

    if len(payload_raw) < 12:
        print(f"{RED}[RX #{seq:02d}] ENCRYPTED — packet quá ngắn{RESET}")
        return

    nonce  = payload_raw[:12]
    ct_aad = payload_raw[12:]
    aad    = session.session_id + struct.pack("!I", seq)

    # Replay check
    if not session.replay.check(seq):
        print(f"\n{RED}[RX #{seq:02d}]{RESET} {RED}{BOLD}REPLAY REJECTED!{RESET}  "
              f"seq={seq} đã thấy rồi (reject #{session.replay.rejected})")
        return

    # Decrypt + verify GCM tag
    try:
        pt = session.aesgcm.decrypt(nonce, ct_aad, aad)
        session.rx_ok += 1
        print(f"\n{GREEN}[RX #{seq:02d}]{RESET} ENCRYPTED  "
              f"{len(payload_raw)+12}B → decrypt OK ✓")
        print(f"  {GREEN}└─ {pt.decode()}{RESET}")
    except InvalidTag:
        session.rx_fail += 1
        print(f"\n{RED}[RX #{seq:02d}]{RESET} {RED}GCM TAG INVALID — "
              f"packet bị tamper hoặc sai key!{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
def key_exchange_thread(key_sock, sessions, stop_event):
    """Thread riêng chờ key exchange mới."""
    key_sock.settimeout(1.0)
    while not stop_event.is_set():
        try:
            sess = do_key_exchange_server(key_sock)
            sessions["current"] = sess
        except socket.timeout:
            continue
        except Exception as e:
            if not stop_event.is_set():
                print(f"{DIM}[KEY] {e}{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
def main():
    # Socket nhận từ Satellite
    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    recv_sock.bind((RECV_HOST, RECV_PORT))
    recv_sock.settimeout(30.0)

    # Socket gửi tap cho eavesdropper
    eaves_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # TCP server cho key exchange
    key_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    key_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    key_sock.bind((KEY_HOST, KEY_PORT))
    key_sock.listen(5)

    sessions   = {"current": None}
    stop_event = threading.Event()

    kt = threading.Thread(
        target=key_exchange_thread,
        args=(key_sock, sessions, stop_event),
        daemon=True
    )
    kt.start()

    print(f"{GREEN}{'═'*58}")
    print(f"  📡 GROUND STATION — Singapore (GS-63)")
    print(f"{'═'*58}{RESET}")
    print(f"  Nhận từ  : :{RECV_PORT}  (Satellite forward)")
    print(f"  Key exch : :{KEY_PORT}   (TCP, X25519)")
    print(f"  Tap →    : :{EAVES_PORT} (Eavesdropper)")
    print(f"\n  Replay window : {REPLAY_WINDOW} packets")
    print(f"  Chờ packet...\n")

    rx_total = plain_total = enc_ok = enc_fail = 0

    try:
        while True:
            try:
                raw, _ = recv_sock.recvfrom(65535)
            except socket.timeout:
                break

            if len(raw) < 7:
                continue

            ptype, seq, length = struct.unpack("!BIH", raw[:7])
            payload_raw = raw[7:]
            rx_total += 1

            if ptype == 0x01:
                plain_total += 1
                handle_plain(seq, payload_raw, length, eaves_sock, raw)

            elif ptype == 0x02:
                sess = sessions.get("current")
                if sess is None:
                    print(f"{AMBER}[RX #{seq:02d}] ENCRYPTED nhưng chưa có session!{RESET}")
                    eaves_sock.sendto(raw, (EAVES_HOST, EAVES_PORT))
                else:
                    handle_encrypted(seq, payload_raw, sess, eaves_sock, raw)
            else:
                print(f"{DIM}[RX] Unknown type 0x{ptype:02x}{RESET}")

    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()

    # Tổng kết
    print(f"\n{'═'*58}")
    print(f"  TỔNG KẾT — Ground Station Singapore")
    print(f"{'═'*58}")
    sess = sessions.get("current")
    print(f"  Tổng nhận      : {rx_total}")
    print(f"  Plaintext      : {plain_total}  {AMBER}← lộ nội dung!{RESET}")
    if sess:
        print(f"  Encrypted OK   : {sess.rx_ok}  {GREEN}← E2EE bảo vệ{RESET}")
        print(f"  Decrypt fail   : {sess.rx_fail}  {RED}← tamper/sai key{RESET}")
        print(f"  Replay reject  : {sess.replay.rejected}  {GREEN}← chặn replay{RESET}")


if __name__ == "__main__":
    main()
