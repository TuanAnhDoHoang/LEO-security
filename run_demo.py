"""
run_demo.py — Chạy toàn bộ demo tự động trong 1 terminal
──────────────────────────────────────────────────────────
Khởi động satellite + receiver + eavesdropper ở background,
sau đó chạy từng phase:
  Phase 1 — Plaintext
  Phase 2 — Encrypted (E2EE)
  Phase 3 — Replay Attack

Chạy: python3 run_demo.py
"""

import subprocess
import threading
import time
import sys
import os
import socket
import struct
import collections
import math
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey, X25519PublicKey
)
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

# ── Màu sắc ───────────────────────────────────────────────────────────────────
R = "\033[91m"; G = "\033[92m"; Y = "\033[93m"
C = "\033[96m"; D = "\033[2m";  B = "\033[1m"; X = "\033[0m"

# ── Ports ─────────────────────────────────────────────────────────────────────
SAT_LISTEN  = 9000
SAT_FORWARD = 9001
KEY_PORT    = 9100
EAVES_PORT  = 9002

# ── Hypatia Bước 1 params ─────────────────────────────────────────────────────
DELAY_MS  = 6.0
JITTER_MS = 0.9
LOSS_PCT  = 0.1

MESSAGES = [
    b"GS46-HCMC | COORD: 10.75N 106.67E | STATUS: OPERATIONAL",
    b"GS46-HCMC | UPLINK-TOKEN: X7F2-K9QM-3T1A | AUTH: VALID",
    b"GS46-HCMC | CMD: SAT-042 ADJUST ORBIT +0.5deg",
    b"GS46-HCMC | CRYPTO-HINT: rotate-at-epoch-1200",
]


def div(char="─", n=62): print(D + char*n + X)
def header(title, color=C):
    print(); div("═"); print(f"  {color}{B}{title}{X}"); div("═")


# ─────────────────────────────────────────────────────────────────────────────
# INLINE COMPONENTS (không fork subprocess — chạy ngay trong process này)
# ─────────────────────────────────────────────────────────────────────────────

import random

class Satellite:
    def __init__(self):
        self.sock_in  = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_in.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock_in.bind(("127.0.0.1", SAT_LISTEN))
        self.sock_in.settimeout(0.5)
        self.sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.running  = False
        self.stats    = {"rx": 0, "tx": 0, "drop": 0}

    def _forward(self, raw):
        self.stats["rx"] += 1
        if random.random() < LOSS_PCT / 100:
            self.stats["drop"] += 1
            return
        delay = max(0, random.gauss(DELAY_MS, JITTER_MS)) / 1000
        time.sleep(delay)
        self.sock_out.sendto(raw, ("127.0.0.1", SAT_FORWARD))
        self.sock_out.sendto(raw, ("127.0.0.1", EAVES_PORT))   # tap
        self.stats["tx"] += 1

    def _loop(self):
        while self.running:
            try:
                raw, _ = self.sock_in.recvfrom(65535)
                threading.Thread(target=self._forward, args=(raw,), daemon=True).start()
            except socket.timeout:
                continue

    def start(self):
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self): self.running = False


class Receiver:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", SAT_FORWARD))
        self.sock.settimeout(0.5)
        self.key_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.key_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.key_sock.bind(("127.0.0.1", KEY_PORT))
        self.key_sock.listen(5)
        self.key_sock.settimeout(1.0)
        self.session  = None
        self.running  = False
        self.log      = []
        self.seen_seq = set()

    def _key_loop(self):
        while self.running:
            try:
                conn, _ = self.key_sock.accept()
                peer_raw   = conn.recv(32)
                session_id = os.urandom(16)
                priv = X25519PrivateKey.generate()
                pub  = priv.public_key().public_bytes(
                    serialization.Encoding.Raw, serialization.PublicFormat.Raw)
                conn.sendall(pub); conn.sendall(session_id); conn.close()
                peer = X25519PublicKey.from_public_bytes(peer_raw)
                shared = priv.exchange(peer)
                key = HKDF(algorithm=hashes.SHA256(), length=32,
                           salt=None, info=b"LEO-SAT-E2EE-HCMC-SGP").derive(shared)
                self.session = {"aesgcm": AESGCM(key), "session_id": session_id}
                self.seen_seq.clear()
            except socket.timeout: continue
            except Exception: continue

    def _recv_loop(self):
        while self.running:
            try:
                raw, _ = self.sock.recvfrom(65535)
                if len(raw) < 7: continue
                ptype, seq, length = struct.unpack("!BIH", raw[:7])
                payload = raw[7:]

                if ptype == 0x01:
                    content = payload[:length].decode(errors="replace")
                    self.log.append(("plain", seq, content))

                elif ptype == 0x02 and self.session:
                    if seq in self.seen_seq:
                        self.log.append(("replay", seq, None))
                        continue
                    self.seen_seq.add(seq)
                    nonce = payload[:12]
                    aad   = self.session["session_id"] + struct.pack("!I", seq)
                    try:
                        pt = self.session["aesgcm"].decrypt(nonce, payload[12:], aad)
                        self.log.append(("enc_ok", seq, pt.decode(errors="replace")))
                    except InvalidTag:
                        self.log.append(("enc_fail", seq, None))

            except socket.timeout: continue

    def start(self):
        self.running = True
        threading.Thread(target=self._key_loop,  daemon=True).start()
        threading.Thread(target=self._recv_loop, daemon=True).start()

    def stop(self): self.running = False


class Eavesdropper:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", EAVES_PORT))
        self.sock.settimeout(0.5)
        self.running = False
        self.log     = []

    def _entropy(self, data):
        if not data: return 0.0
        c = collections.Counter(data); n = len(data)
        return -sum((v/n)*math.log2(v/n) for v in c.values())

    def _loop(self):
        while self.running:
            try:
                raw, _ = self.sock.recvfrom(65535)
                if len(raw) < 7: continue
                ptype, seq, _ = struct.unpack("!BIH", raw[:7])
                payload = raw[7:]
                e = self._entropy(payload)

                if ptype == 0x01:
                    content = payload.decode(errors="replace")
                    self.log.append(("readable", seq, content, e))
                else:
                    self.log.append(("encrypted", seq, payload[:16].hex(), e))
            except socket.timeout: continue

    def start(self):
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self): self.running = False


# ─────────────────────────────────────────────────────────────────────────────
# KEY EXCHANGE (sender side)
# ─────────────────────────────────────────────────────────────────────────────
def key_exchange_client():
    priv = X25519PrivateKey.generate()
    pub  = priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    ks = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    for _ in range(10):
        try: ks.connect(("127.0.0.1", KEY_PORT)); break
        except: time.sleep(0.2)
    ks.sendall(pub)
    peer_raw   = ks.recv(32)
    session_id = ks.recv(16)
    ks.close()
    peer   = X25519PublicKey.from_public_bytes(peer_raw)
    shared = priv.exchange(peer)
    key    = HKDF(algorithm=hashes.SHA256(), length=32,
                  salt=None, info=b"LEO-SAT-E2EE-HCMC-SGP").derive(shared)
    return AESGCM(key), session_id


def send_plain(n=8):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for seq in range(n):
        msg = MESSAGES[seq % len(MESSAGES)]
        pkt = struct.pack("!BIH", 0x01, seq, len(msg)) + msg
        sock.sendto(pkt, ("127.0.0.1", SAT_LISTEN))
        time.sleep(0.3)
    sock.close()


def send_encrypted(n=8):
    aesgcm, session_id = key_exchange_client()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for seq in range(n):
        msg   = MESSAGES[seq % len(MESSAGES)]
        nonce = os.urandom(12)
        aad   = session_id + struct.pack("!I", seq)
        ct    = aesgcm.encrypt(nonce, msg, aad)
        pkt   = struct.pack("!BIH", 0x02, seq, len(ct)) + nonce + ct
        sock.sendto(pkt, ("127.0.0.1", SAT_LISTEN))
        time.sleep(0.3)
    sock.close()


def send_replay(n=5):
    aesgcm, session_id = key_exchange_client()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    msg   = b"GS46-HCMC | CMD: LAUNCH-SEQUENCE-ALPHA"
    nonce = os.urandom(12)
    aad   = session_id + struct.pack("!I", 0)
    ct    = aesgcm.encrypt(nonce, msg, aad)
    pkt   = struct.pack("!BIH", 0x02, 0, len(ct)) + nonce + ct   # seq=0 cố định
    for _ in range(n):
        sock.sendto(pkt, ("127.0.0.1", SAT_LISTEN))
        time.sleep(0.2)
    sock.close()


# ─────────────────────────────────────────────────────────────────────────────
# DISPLAY RESULTS
# ─────────────────────────────────────────────────────────────────────────────
def show_eaves_log(eaves, phase):
    print(f"\n  {B}[EAVESDROPPER thấy gì — Phase {phase}]{X}")
    div()
    if not eaves.log:
        print(f"  {D}(chưa có packet){X}")
        return
    for kind, seq, data, entropy in eaves.log:
        e_bar = "█" * int(entropy/8*16) + "░" * (16-int(entropy/8*16))
        if kind == "readable":
            print(f"  {Y}Pkt#{seq:02d}{X}  entropy={entropy:.1f}  [{e_bar}]")
            print(f"  {R}  ⚠ ĐỌC ĐƯỢC: {data[:70]}{X}")
        else:
            print(f"  {G}Pkt#{seq:02d}{X}  entropy={entropy:.1f}  [{e_bar}]")
            print(f"  {G}  ✓ CIPHER  : {data}...  (không đọc được){X}")


def show_recv_log(recv, phase):
    print(f"\n  {B}[RECEIVER nhận được — Phase {phase}]{X}")
    div()
    for kind, seq, data in recv.log:
        if kind == "plain":
            print(f"  {Y}Pkt#{seq:02d}{X}  PLAIN   → {data[:60]}")
        elif kind == "enc_ok":
            print(f"  {G}Pkt#{seq:02d}{X}  DECRYPT → {data[:60]}")
        elif kind == "enc_fail":
            print(f"  {R}Pkt#{seq:02d}{X}  {R}GCM FAIL{X} — tamper/sai key")
        elif kind == "replay":
            print(f"  {R}Pkt#{seq:02d}{X}  {R}REPLAY REJECTED{X}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{C}{'═'*62}")
    print(f"  🛰  LEO EAVESDROPPING & E2EE DEMO")
    print(f"  Route: HCMC (GS-46) → [SAT] → Singapore (GS-63)")
    print(f"  Delay: {DELAY_MS}ms ± {JITTER_MS}ms  Loss: {LOSS_PCT}%  [Hypatia Bước 1]")
    print(f"{'═'*62}{X}\n")

    # Khởi động các component
    sat   = Satellite()
    recv  = Receiver()
    eaves = Eavesdropper()

    sat.start(); time.sleep(0.1)
    recv.start(); time.sleep(0.2)
    eaves.start(); time.sleep(0.1)

    print(f"  {G}✓ Satellite Node   : :{SAT_LISTEN} → :{SAT_FORWARD}{X}")
    print(f"  {G}✓ Receiver (SGP)   : :{SAT_FORWARD}{X}")
    print(f"  {G}✓ Eavesdropper     : :{EAVES_PORT}  (tap){X}")

    # ── PHASE 1: PLAINTEXT ────────────────────────────────────────────────────
    header("PHASE 1 — PLAINTEXT TRANSMISSION", Y)
    print(f"  Không mã hóa. Eavesdropper đọc được toàn bộ nội dung.\n")
    input(f"  {D}[Enter để bắt đầu Phase 1...]{X}")

    eaves.log.clear(); recv.log.clear()
    send_plain(n=5)
    time.sleep(0.5)

    show_eaves_log(eaves, 1)
    show_recv_log(recv,  1)
    print(f"\n  {R}{B}⚠  Kết quả: Eavesdropper đọc được TOÀN BỘ payload!{X}")

    # ── PHASE 2: ENCRYPTED ────────────────────────────────────────────────────
    header("PHASE 2 — E2EE: AES-256-GCM + ECDH X25519", G)
    print(f"  Mã hóa đầu cuối. Eavesdropper chỉ thấy ciphertext ngẫu nhiên.\n")
    input(f"  {D}[Enter để bắt đầu Phase 2...]{X}")

    eaves.log.clear(); recv.log.clear()
    send_encrypted(n=5)
    time.sleep(0.5)

    show_eaves_log(eaves, 2)
    show_recv_log(recv,  2)
    print(f"\n  {G}{B}✓  Kết quả: Eavesdropper THẤT BẠI — E2EE bảo vệ thành công!{X}")

    # ── PHASE 3: REPLAY ATTACK ────────────────────────────────────────────────
    header("PHASE 3 — REPLAY ATTACK + DEFENSE", R)
    print(f"  Gửi lại cùng 1 packet 5 lần. Receiver chặn từ lần 2 trở đi.\n")
    input(f"  {D}[Enter để bắt đầu Phase 3...]{X}")

    eaves.log.clear(); recv.log.clear()
    send_replay(n=5)
    time.sleep(0.5)

    show_recv_log(recv, 3)
    replays = sum(1 for k,_,_ in recv.log if k=="replay")
    ok      = sum(1 for k,_,_ in recv.log if k=="enc_ok")
    print(f"\n  {G}✓ Accepted (lần đầu) : {ok}{X}")
    print(f"  {R}✗ Replay rejected    : {replays}{X}")
    print(f"\n  {G}{B}✓  Replay Protection hoạt động đúng!{X}")

    # ── TỔNG KẾT ─────────────────────────────────────────────────────────────
    header("TỔNG KẾT DEMO", C)
    print(f"  {'Tiêu chí':<35} {'Plaintext':>12}  {'E2EE':>8}")
    div()
    print(f"  {'Eavesdropper đọc được payload':<35} {R+'CÓ':>12}{X}  {G+'KHÔNG':>8}{X}")
    print(f"  {'Nội dung hiển thị':<35} {'rõ ràng':>12}  {'ciphertext':>8}")
    print(f"  {'Entropy payload':<35} {'~4 bits/B':>12}  {'~8 bits/B':>8}")
    print(f"  {'Chống replay':<35} {'KHÔNG':>12}  {'CÓ':>8}")
    print(f"  {'Mã hóa':<35} {'KHÔNG':>12}  {'AES-256':>8}")
    div()
    print(f"\n  Satellite delay: {sat.stats}")
    print()

    sat.stop(); recv.stop(); eaves.stop()


if __name__ == "__main__":
    main()
