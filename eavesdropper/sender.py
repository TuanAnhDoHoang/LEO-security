"""
sender.py — Ground Station HCMC (GS-46)
─────────────────────────────────────────────────────────────────
Gửi dữ liệu đến Singapore (GS-63).
"""

import socket
import sys
import os
import time
import struct
import argparse
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# ── Defaults ──────────────────────────────────────────────────────────────────
SAT_HOST_MININET = "10.0.0.1"
SAT_HOST_LOCAL   = "127.0.0.1"
SAT_PORT         = 9000

KEY_HOST_MININET = "10.0.0.3"
KEY_HOST_LOCAL   = "127.0.0.1"
KEY_PORT         = 9100

# ── Globals for config ────────────────────────────────────────────────────────
CONFIG = {
    "sat_host": SAT_HOST_MININET,
    "key_host": KEY_HOST_MININET,
    "dashboard": False
}

# ── Dữ liệu mẫu ───────────────────────────────────────────────────────────────
MESSAGES = [
    b"GS46-HCMC | COORD: 10.75N 106.67E | STATUS: OPERATIONAL",
    b"GS46-HCMC | UPLINK-TOKEN: X7F2-K9QM-3T1A | AUTH: VALID",
    b"GS46-HCMC | CMD: SAT-042 ADJUST ORBIT +0.5deg",
    b"GS46-HCMC | CRYPTO-KEY-HINT: rotate-at-epoch-1200",
    b"GS46-HCMC | PAYLOAD: sensor_data_batch_2024_classified",
]

GREEN = "\033[92m"; CYAN = "\033[96m"; AMBER = "\033[93m"
RED   = "\033[91m"; DIM  = "\033[2m";  RESET = "\033[0m"

PACKET_COUNT = 10
INTERVAL_S   = 0.5

def log(msg):
    if CONFIG["dashboard"]:
        print(f"[SENDER] {msg}", flush=True)
    else:
        print(msg, flush=True)

def build_plain_packet(seq, payload):
    return struct.pack("!BIH", 0x01, seq, len(payload)) + payload

def build_encrypted_packet(seq, payload, aesgcm, session_id):
    nonce = os.urandom(12)
    aad   = session_id + struct.pack("!I", seq)
    ct    = aesgcm.encrypt(nonce, payload, aad)
    return struct.pack("!BIH", 0x02, seq, len(ct)) + nonce + ct

CERTS_DIR = os.path.join(os.path.dirname(__file__), "certs")

def load_certs():
    with open(os.path.join(CERTS_DIR, "ca.crt"), "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read())
    with open(os.path.join(CERTS_DIR, "sender.crt"), "rb") as f:
        my_cert_raw = f.read()
    with open(os.path.join(CERTS_DIR, "sender.key"), "rb") as f:
        my_key = serialization.load_pem_private_key(f.read(), password=None)
    return ca_cert, my_cert_raw, my_key

def do_key_exchange():
    ca_cert, my_cert_raw, my_id_key = load_certs()
    ephem_priv = X25519PrivateKey.generate()
    ephem_pub  = ephem_priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    signature = my_id_key.sign(ephem_pub)
    tx_data = (struct.pack("!I", len(my_cert_raw)) + my_cert_raw +
               struct.pack("!I", len(ephem_pub)) + ephem_pub +
               struct.pack("!I", len(signature)) + signature)

    ks = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        ks.connect((CONFIG["key_host"], KEY_PORT))
    except Exception as e:
        log(f"{RED}[KEY] Không thể kết nối đến Receiver tại {CONFIG['key_host']}:{KEY_PORT}: {e}{RESET}")
        sys.exit(1)

    ks.sendall(tx_data)

    def recv_exact(s, n):
        data = b''
        while len(data) < n:
            chunk = s.recv(n - len(data))
            if not chunk: raise EOFError
            data += chunk
        return data

    try:
        r_cert_len = struct.unpack("!I", recv_exact(ks, 4))[0]
        r_cert_raw = recv_exact(ks, r_cert_len)
        r_pub_len  = struct.unpack("!I", recv_exact(ks, 4))[0]
        r_pub_raw  = recv_exact(ks, r_pub_len)
        r_sig_len  = struct.unpack("!I", recv_exact(ks, 4))[0]
        r_sig_raw  = recv_exact(ks, r_sig_len)
        session_id = recv_exact(ks, 16)
    except EOFError:
        log(f"{RED}[KEY] Receiver đóng kết nối sớm!{RESET}")
        sys.exit(1)
    finally:
        ks.close()

    try:
        peer_cert = x509.load_pem_x509_certificate(r_cert_raw)
        ca_cert.public_key().verify(peer_cert.signature, peer_cert.tbs_certificate_bytes)
        peer_id_pub = peer_cert.public_key()
        peer_id_pub.verify(r_sig_raw, r_pub_raw)
        log(f"{GREEN}[KEY] Đã xác thực Certificate của Receiver: "
              f"{peer_cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value}{RESET}")
    except Exception as e:
        log(f"{RED}[KEY] Xác thực thất bại: {e}{RESET}")
        sys.exit(1)

    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
    peer_ephem_pub = X25519PublicKey.from_public_bytes(r_pub_raw)
    shared = ephem_priv.exchange(peer_ephem_pub)
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"LEO-SAT-E2EE-HCMC-SGP").derive(shared)
    return key, session_id

def run_plain(sock):
    log(f"\n{AMBER}{'─'*56}")
    log(f"  MODE: PLAINTEXT — Eavesdropper sẽ đọc được toàn bộ!")
    log(f"{'─'*56}{RESET}\n")
    for seq in range(PACKET_COUNT):
        msg = MESSAGES[seq % len(MESSAGES)]
        pkt = build_plain_packet(seq, msg)
        sock.sendto(pkt, (CONFIG["sat_host"], SAT_PORT))
        log(f"{AMBER}[TX #{seq:02d}]{RESET} PLAIN  {len(pkt):>4}B  payload: {msg.decode()}")
        time.sleep(INTERVAL_S)

def run_encrypted(sock):
    log(f"\n{GREEN}{'─'*56}")
    log(f"  MODE: ENCRYPTED — AES-256-GCM + ECDH X25519")
    log(f"{'─'*56}{RESET}\n")
    log(f"{CYAN}[KEY] Bắt đầu ECDH key exchange...{RESET}")
    key, session_id = do_key_exchange()
    aesgcm = AESGCM(key)
    log("")
    for seq in range(PACKET_COUNT):
        msg = MESSAGES[seq % len(MESSAGES)]
        pkt = build_encrypted_packet(seq, msg, aesgcm, session_id)
        sock.sendto(pkt, (CONFIG["sat_host"], SAT_PORT))
        visible = pkt[7+12:7+12+16]
        log(f"{GREEN}[TX #{seq:02d}]{RESET} ENCR   {len(pkt):>4}B  eavesdropper thấy: {visible.hex()}...")
        time.sleep(INTERVAL_S)

def run_replay(sock):
    log(f"\n{RED}{'─'*56}")
    log(f"  MODE: REPLAY ATTACK — gửi lại cùng 1 packet")
    log(f"{'─'*56}{RESET}\n")
    log(f"{CYAN}[KEY] Key exchange cho replay test...{RESET}")
    key, session_id = do_key_exchange()
    aesgcm = AESGCM(key)
    log("")
    msg = b"GS46-HCMC | CMD: LAUNCH-SEQUENCE-ALPHA"
    pkt = build_encrypted_packet(0, msg, aesgcm, session_id)
    for i in range(5):
        sock.sendto(pkt, (CONFIG["sat_host"], SAT_PORT))
        log(f"{RED}[TX REPLAY #{i}]{RESET}  Gửi lại packet seq=0 → receiver nên reject từ lần 2")
        time.sleep(0.3)

def main():
    parser = argparse.ArgumentParser(description="LEO Satellite Sender (GS-46)")
    parser.add_argument("mode", choices=["plain", "encrypted", "replay", "all"], default="plain", nargs="?")
    parser.add_argument("--local", action="store_true", help="Run in local mode (127.0.0.1)")
    parser.add_argument("--dashboard", action="store_true", help="Prefix output for dashboard")
    args = parser.parse_args()

    CONFIG["sat_host"] = SAT_HOST_LOCAL if args.local else SAT_HOST_MININET
    CONFIG["key_host"] = KEY_HOST_LOCAL if args.local else KEY_HOST_MININET
    CONFIG["dashboard"] = args.dashboard

    log(f"{CYAN}{'═'*56}")
    log(f"  📡 GROUND STATION — HCMC (GS-46)")
    log(f"{'═'*56}{RESET}")
    log(f"  → SAT-A     : {CONFIG['sat_host']}:{SAT_PORT}")
    log(f"  → Mode      : {args.mode.upper()}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if args.mode == "plain": run_plain(sock)
    elif args.mode == "encrypted": run_encrypted(sock)
    elif args.mode == "replay": run_replay(sock)
    elif args.mode == "all":
        run_plain(sock)
        time.sleep(1)
        run_encrypted(sock)
        time.sleep(1)
        run_replay(sock)
    sock.close()
    log(f"\n{DIM}[TX] Xong.{RESET}")

if __name__ == "__main__":
    main()
