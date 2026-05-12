#!/usr/bin/python
import socket
import sys
import os
import time
import struct
import argparse
import threading
# Cryptography imports
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ==================== CẤU HÌNH ====================
SAT_HOST_MININET = "10.0.1.2"
SAT_HOST_LOCAL   = "127.0.0.1"
SAT_PORT         = 9000 
EAVES_PORT       = 9002

KEY_HOST_MININET = "10.0.0.3"
KEY_HOST_LOCAL   = "127.0.0.1"
KEY_PORT         = 9100

LISTEN_PORT      = 9999

# SAT_HOST = "10.0.1.2"
# SAT_PORT = 9000
# KEY_HOST = "10.0.3.1"
# KEY_PORT = 9100

MESSAGES = [
    b"GS46-HCMC | COORD: 10.75N 106.67E | STATUS: OPERATIONAL",
    b"GS46-HCMC | UPLINK-TOKEN: X7F2-K9QM-3T1A | AUTH: VALID",
    b"GS46-HCMC | CMD: SAT-042 ADJUST ORBIT +0.5deg",
]

CONFIG = {
    "sat_host": SAT_HOST_MININET,
    "key_host": KEY_HOST_MININET,
    "dashboard": False
}

def build_plain_packet(seq, payload):
    return struct.pack("!BIH", 0x01, seq, len(payload)) + payload

def build_encrypted_packet(seq, payload, aesgcm, session_id):
    """Tạo gói tin mã hóa AES-256-GCM"""
    nonce = os.urandom(12)
    aad = session_id + struct.pack("!I", seq)
    ct = aesgcm.encrypt(nonce, payload, aad)          
    return struct.pack("!BIH", 0x02, seq, len(ct)) + nonce + ct

def udp_listener():
    print(f"[SENDER] Listening on port {LISTEN_PORT}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', LISTEN_PORT))
    while True:
        data, addr = sock.recvfrom(4096)
        print(f"[SENDER] Received {len(data)} bytes on port {LISTEN_PORT} from {addr}: {data[:100]}...")

def do_key_exchange():
    print("[SENDER] Đang trao đổi khóa ECDH X25519...")
    private_key = X25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )

    # connect TCP to receiver exchange public key 
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((CONFIG["key_host"], KEY_PORT))
    sock.sendall(public_key)
    peer_public = sock.recv(32)
    sock.close()

    # create public key
    peer_public_key = X25519PublicKey.from_public_bytes(peer_public)
    shared = private_key.exchange(peer_public_key)

    # Derive AES-256 key
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"LEO-SAT-E2EE"
    ).derive(shared)

    print("[SENDER] Key exchange THÀNH CÔNG!")
    return key, public_key[:8]   # session_id

def run_encrypted(sock):
    key, session_id = do_key_exchange()
    aesgcm = AESGCM(key)
    print("=== MODE: ENCRYPTED (AES-256-GCM) ===")

    for seq in range(10):
        msg = MESSAGES[seq % len(MESSAGES)]
        pkt = build_encrypted_packet(seq, msg, aesgcm, session_id)
        sock.sendto(pkt, (CONFIG["sat_host"], SAT_PORT))
        print(f"[SENDER] [TX #{seq:02d}] Gửi encrypted {len(pkt)} bytes")
        time.sleep(0.5)

def run_plain(sock):
    print("=== MODE: PLAIN (không mã hóa) ===")
    for seq in range(300):
        msg = MESSAGES[seq % len(MESSAGES)]
        pkt = build_plain_packet(seq, msg)
        #sock.sendto(pkt, (SAT_HOST, SAT_PORT))
        sock.sendto(pkt, (CONFIG["sat_host"], SAT_PORT))
        print(f"[SENDER] [TX #{seq:02d}] Gửi plain {len(pkt)} bytes")
        time.sleep(0.5)

def main():
    parser = argparse.ArgumentParser(description="LEO Sender (E2EE Only)")
    parser.add_argument("mode", choices=["plain", "encrypted", "all"])
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--dashboard", action="store_true")
    args = parser.parse_args()

    CONFIG["sat_host"] = SAT_HOST_LOCAL if args.local else SAT_HOST_MININET
    CONFIG["key_host"] = KEY_HOST_LOCAL if args.local else KEY_HOST_MININET
    CONFIG["dashboard"] = args.dashboard

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Start listener thread
    listener_thread = threading.Thread(target=udp_listener, daemon=True)
    listener_thread.start()

    if args.mode == "plain": 
        run_plain(sock)
    elif args.mode == "encrypted": 
        run_encrypted(sock)
    else: # all
        run_plain(sock)
        time.sleep(2)
        run_encrypted(sock)

if __name__ == "__main__":
    main()