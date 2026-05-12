import subprocess
import threading
import time
import sys
import os
import socket
import struct
import collections
import math
import random
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey, X25519PublicKey
)
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from cryptography import x509

# ── Màu sắc ───────────────────────────────────────────────────────────────────
R = "\033[91m"; G = "\033[92m"; Y = "\033[93m"
C = "\033[96m"; D = "\033[2m";  B = "\033[1m"; X = "\033[0m"

# ── Topology Config ─────────────────────────────────────────────────────────────
SAT_A_PORT = 9000
SAT_B_PORT = 9000
SAT_C_PORT = 9000
RECV_PORT  = 9001
EAVES_PORT = 9002
KEY_PORT   = 9100

MESSAGES = [
    b"GS46-HCMC | COORD: 10.75N 106.67E | STATUS: OPERATIONAL",
    b"GS46-HCMC | UPLINK-TOKEN: X7F2-K9QM-3T1A | AUTH: VALID",
    b"GS46-HCMC | CMD: SAT-042 ADJUST ORBIT +0.5deg",
]

def div(char="─", n=62): print(D + char*n + X)
def header(title, color=C):
    print(); div("═"); print(f"  {color}{B}{title}{X}"); div("═")

class TransparentRelay:
    def __init__(self, name, listen_port, fwd_port):
        self.name = name
        self.listen_port = listen_port
        self.fwd_port = fwd_port
        self.running = False

    def _loop(self):
        ds = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ds.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ds.bind(("127.0.0.1", self.listen_port))
        ds.settimeout(0.5)
        out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        while self.running:
            try:
                raw, _ = ds.recvfrom(65535)
                time.sleep(0.005) # Simulated delay
                out.sendto(raw, ("127.0.0.1", self.fwd_port))
            except socket.timeout: continue
    
    def start(self): self.running = True; threading.Thread(target=self._loop, daemon=True).start()
    def stop(self): self.running = False

def main():
    header("LEO E2EE-ONLY TOPOLOGY DEMO", C)
    print(f"  Topology: Sender → SAT-A → SAT-B → SAT-C → Receiver")
    print(f"  Security: End-to-End Encryption Only (Sender ↔ Receiver)")

    sat_a = TransparentRelay("SAT-A", SAT_A_PORT, SAT_B_PORT)
    sat_b = TransparentRelay("SAT-B", SAT_B_PORT, SAT_C_PORT)
    sat_c = TransparentRelay("SAT-C", SAT_C_PORT, RECV_PORT)
    
    sat_a.start(); sat_b.start(); sat_c.start()
    
    # Start Receiver process for E2EE handshake
    recv_proc = subprocess.Popen(["python3", "eavesdropper/receiver.py", "--local", "--dashboard"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(1)

    header("PHASE 1 — SECURE TRANSMISSION (E2EE)", G)
    # Start Sender process
    sender_proc = subprocess.Popen(["python3", "eavesdropper/sender.py", "encrypted", "--local", "--dashboard"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    # Monitor output
    def monitor(proc, prefix):
        for line in iter(proc.stdout.readline, ""):
            print(f"{prefix} {line.strip()}")
    
    threading.Thread(target=monitor, args=(sender_proc, f"{C}[SND]{X}"), daemon=True).start()
    threading.Thread(target=monitor, args=(recv_proc, f"{G}[REC]{X}"), daemon=True).start()
    
    time.sleep(10)
    sender_proc.terminate(); recv_proc.terminate()
    sat_a.stop(); sat_b.stop(); sat_c.stop()
    header("DEMO COMPLETE", C)

if __name__ == "__main__": main()
