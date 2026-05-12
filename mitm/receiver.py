"""
receiver.py — Ground Station Singapore (GS-63)
────────────────────────────────────────────────────────────────
Nhận packet từ SAT-B (nearest satellite).
"""

import socket
import struct
import os
import sys
import time
import threading
import argparse
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey, X25519PublicKey
)
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from cryptography import x509

# ── Defaults ──────────────────────────────────────────────────────────────────
RECV_HOST_MININET = "10.0.0.3"
RECV_HOST_LOCAL   = "127.0.0.1"
RECV_PORT         = 9001

KEY_HOST_MININET = "10.0.0.3"
KEY_HOST_LOCAL   = "127.0.0.1"
KEY_PORT         = 9100

GREEN  = "\033[92m"; CYAN = "\033[96m"; AMBER = "\033[93m"
RED    = "\033[91m"; DIM  = "\033[2m";  BOLD  = "\033[1m"; RESET = "\033[0m"

REPLAY_WINDOW = 64

CONFIG = {
    "recv_host": RECV_HOST_MININET,
    "key_host": KEY_HOST_MININET,
    "dashboard": False
}

def log(msg):
    if CONFIG["dashboard"]:
        print(f"[RECEIVER] {msg}", flush=True)
    else:
        print(msg, flush=True)

class ReplayFilter:
    def __init__(self, window=64):
        self.window   = window
        self.seen     = set()
        self.top_seq  = -1
        self.rejected = 0

    def check(self, seq) -> bool:
        if seq > self.top_seq:
            if self.top_seq >= 0:
                cutoff = seq - self.window
                self.seen = {s for s in self.seen if s >= cutoff}
            self.top_seq = seq
        elif seq < self.top_seq - self.window:
            self.rejected += 1
            return False
        if seq in self.seen:
            self.rejected += 1
            return False
        self.seen.add(seq)
        return True

class SessionState:
    def __init__(self, key: bytes, session_id: bytes):
        self.aesgcm     = AESGCM(key)
        self.session_id = session_id
        self.replay     = ReplayFilter(REPLAY_WINDOW)
        self.rx_ok      = 0
        self.rx_fail    = 0

CERTS_DIR = os.path.join(os.path.dirname(__file__), "certs")

def load_certs():
    with open(os.path.join(CERTS_DIR, "ca.crt"), "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read())
    with open(os.path.join(CERTS_DIR, "receiver.crt"), "rb") as f:
        my_cert_raw = f.read()
    with open(os.path.join(CERTS_DIR, "receiver.key"), "rb") as f:
        my_key = serialization.load_pem_private_key(f.read(), password=None)
    return ca_cert, my_cert_raw, my_key

def do_key_exchange_server(key_sock) -> SessionState:
    ca_cert, my_cert_raw, my_id_key = load_certs()
    try:
        conn, addr = key_sock.accept()
        log(f"{CYAN}[KEY] Sender kết nối từ {addr}{RESET}")
    except socket.timeout: return None

    def recv_exact(s, n):
        data = b''
        while len(data) < n:
            chunk = s.recv(n - len(data))
            if not chunk: raise EOFError
            data += chunk
        return data

    try:
        s_cert_len = struct.unpack("!I", recv_exact(conn, 4))[0]
        s_cert_raw = recv_exact(conn, s_cert_len)
        s_pub_len  = struct.unpack("!I", recv_exact(conn, 4))[0]
        s_pub_raw  = recv_exact(conn, s_pub_len)
        s_sig_len  = struct.unpack("!I", recv_exact(conn, 4))[0]
        s_sig_raw  = recv_exact(conn, s_sig_len)

        peer_cert = x509.load_pem_x509_certificate(s_cert_raw)
        ca_cert.public_key().verify(peer_cert.signature, peer_cert.tbs_certificate_bytes)
        peer_id_pub = peer_cert.public_key()
        peer_id_pub.verify(s_sig_raw, s_pub_raw)
        
        log(f"{GREEN}[KEY] Đã xác thực Certificate của Sender: "
              f"{peer_cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value}{RESET}")

        session_id = os.urandom(16)
        ephem_priv = X25519PrivateKey.generate()
        ephem_pub  = ephem_priv.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        my_sig = my_id_key.sign(ephem_pub)
        tx_data = (struct.pack("!I", len(my_cert_raw)) + my_cert_raw +
                   struct.pack("!I", len(ephem_pub)) + ephem_pub +
                   struct.pack("!I", len(my_sig)) + my_sig +
                   session_id)
        conn.sendall(tx_data)
        conn.close()

        peer_ephem_pub = X25519PublicKey.from_public_bytes(s_pub_raw)
        shared = ephem_priv.exchange(peer_ephem_pub)
        key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"LEO-SAT-E2EE-HCMC-SGP").derive(shared)
        log(f"{GREEN}[KEY] ECDH hoàn tất | session={session_id.hex()[:8]}...{RESET}")
        return SessionState(key, session_id)
    except Exception as e:
        log(f"{RED}[KEY] Key exchange thất bại: {e}{RESET}")
        conn.close()
        return None

def handle_plain(seq, payload_raw, length):
    content = payload_raw[:length]
    log(f"\n{AMBER}[RX #{seq:02d}]{RESET} PLAINTEXT  {length}B")
    log(f"  {AMBER}⚠  KHÔNG mã hóa — payload lộ hoàn toàn:{RESET}")
    try: log(f"  └─ {content.decode()}")
    except: log(f"  └─ {content}")

def handle_encrypted(seq, payload_raw, session: SessionState):
    if len(payload_raw) < 12: return
    nonce  = payload_raw[:12]
    ct_aad = payload_raw[12:]
    aad    = session.session_id + struct.pack("!I", seq)

    if not session.replay.check(seq):
        log(f"\n{RED}[RX #{seq:02d}]{RESET} {RED}{BOLD}REPLAY REJECTED!{RESET}  seq={seq}")
        return

    try:
        pt = session.aesgcm.decrypt(nonce, ct_aad, aad)
        session.rx_ok += 1
        log(f"\n{GREEN}[RX #{seq:02d}]{RESET} ENCRYPTED → decrypt OK ✓")
        log(f"  {GREEN}└─ {pt.decode()}{RESET}")
    except InvalidTag:
        session.rx_fail += 1
        log(f"\n{RED}[RX #{seq:02d}]{RESET} {RED}GCM TAG INVALID — packet bị tamper!{RESET}")

def key_exchange_thread(key_sock, sessions, stop_event):
    key_sock.settimeout(1.0)
    while not stop_event.is_set():
        sess = do_key_exchange_server(key_sock)
        if sess: sessions["current"] = sess

def main():
    parser = argparse.ArgumentParser(description="LEO Satellite Receiver (GS-63)")
    parser.add_argument("--local", action="store_true", help="Run in local mode")
    parser.add_argument("--dashboard", action="store_true", help="Prefix output")
    args = parser.parse_args()

    CONFIG["recv_host"] = RECV_HOST_LOCAL if args.local else RECV_HOST_MININET
    CONFIG["key_host"] = KEY_HOST_LOCAL if args.local else KEY_HOST_MININET
    CONFIG["dashboard"] = args.dashboard

    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    recv_sock.bind((CONFIG["recv_host"], RECV_PORT))
    recv_sock.settimeout(1.0)

    key_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    key_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    key_sock.bind((CONFIG["key_host"], KEY_PORT))
    key_sock.listen(5)

    sessions = {"current": None}
    stop_event = threading.Event()
    threading.Thread(target=key_exchange_thread, args=(key_sock, sessions, stop_event), daemon=True).start()

    log(f"{GREEN}{'═'*58}")
    log(f"  📡 GROUND STATION — Singapore (GS-63)")
    log(f"{'═'*58}{RESET}")
    log(f"  Nhận từ  : {CONFIG['recv_host']}:{RECV_PORT}")
    log(f"  Key exch : {CONFIG['key_host']}:{KEY_PORT}")

    rx_total = plain_total = 0
    try:
        while not stop_event.is_set():
            try: raw, _ = recv_sock.recvfrom(65535)
            except socket.timeout: continue
            if len(raw) < 7: continue
            ptype, seq, length = struct.unpack("!BIH", raw[:7])
            payload_raw = raw[7:]
            rx_total += 1
            if ptype == 0x01:
                plain_total += 1
                handle_plain(seq, payload_raw, length)
            elif ptype == 0x02:
                sess = sessions.get("current")
                if sess: handle_encrypted(seq, payload_raw, sess)
                else: log(f"{AMBER}[RX #{seq:02d}] ENCRYPTED nhưng chưa có session!{RESET}")
    except KeyboardInterrupt: pass
    finally: stop_event.set()

    log(f"\n{'═'*58}\n  TỔNG KẾT\n{'═'*58}")
    log(f"  Tổng nhận      : {rx_total}\n  Plaintext      : {plain_total}")
    sess = sessions.get("current")
    if sess:
        log(f"  Encrypted OK   : {sess.rx_ok}\n  Decrypt fail   : {sess.rx_fail}\n  Replay reject  : {sess.replay.rejected}")

if __name__ == "__main__":
    main()