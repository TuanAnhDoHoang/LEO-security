import socket
import threading
import os
import struct
import argparse
import time
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography import x509

# ── Defaults ──────────────────────────────────────────────────────────────────
SAT_HOST_MININET = "10.0.0.1"
SAT_HOST_LOCAL   = "127.0.0.1"
SAT_PORT         = 9000 
EAVES_PORT       = 9002

KEY_HOST_MININET = "10.0.0.3"
KEY_HOST_LOCAL   = "127.0.0.1"
KEY_PORT         = 9100

GREEN = "\033[92m"; CYAN = "\033[96m"; AMBER = "\033[93m"
RED   = "\033[91m"; DIM  = "\033[2m";  RESET = "\033[0m"

PACKET_COUNT = 50
INTERVAL_S   = 0.5

MESSAGES = [
    b"GS46-HCMC | COORD: 10.75N 106.67E | STATUS: OPERATIONAL",
    b"GS46-HCMC | UPLINK-TOKEN: X7F2-K9QM-3T1A | AUTH: VALID",
    b"GS46-HCMC | CMD: SAT-042 ADJUST ORBIT +0.5deg",
]

CONFIG = {
    "sat_host": SAT_HOST_MININET,
    "key_host": KEY_HOST_MININET,
    "eaves_port": EAVES_PORT,
    "dashboard": False
}

def log(msg):
    if CONFIG["dashboard"]:
        print(f"[SENDER] {msg}", flush=True)
    else:
        print(msg, flush=True)

def load_certs():
    CERTS_DIR = os.path.join(os.path.dirname(__file__), "certs")
    with open(os.path.join(CERTS_DIR, "ca.crt"), "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read())
    with open(os.path.join(CERTS_DIR, "sender.crt"), "rb") as f:
        my_cert_raw = f.read()
    with open(os.path.join(CERTS_DIR, "sender.key"), "rb") as f:
        my_key = serialization.load_pem_private_key(f.read(), password=None)
    return ca_cert, my_cert_raw, my_key

def do_e2e_handshake(host, port):
    ca_cert, my_cert_raw, my_id_key = load_certs()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        
        e_priv = X25519PrivateKey.generate()
        e_pub  = e_priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        sig = my_id_key.sign(e_pub)
        
        tx = struct.pack("!I", len(my_cert_raw)) + my_cert_raw + struct.pack("!I", len(e_pub)) + e_pub + struct.pack("!I", len(sig)) + sig
        sock.sendall(tx)
        
        def rx_e(s, n):
            d = b''
            while len(d) < n:
                c = s.recv(n-len(d))
                if not c: raise EOFError
                d += c
            return d

        rlen = struct.unpack("!I", rx_e(sock, 4))[0]; rc = rx_e(sock, rlen)
        rplen = struct.unpack("!I", rx_e(sock, 4))[0]; rp = rx_e(sock, rplen)
        rsiglen = struct.unpack("!I", rx_e(sock, 4))[0]; rsig = rx_e(sock, rsiglen)
        sid = rx_e(sock, 16)
        sock.close()

        r_cert = x509.load_pem_x509_certificate(rc)
        ca_cert.public_key().verify(r_cert.signature, r_cert.tbs_certificate_bytes)
        r_cert.public_key().verify(rsig, rp)

        shared = e_priv.exchange(X25519PublicKey.from_public_bytes(rp))
        key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"LEO-SAT-E2EE-HCMC-SGP").derive(shared)
        return AESGCM(key), sid
    except Exception as e:
        log(f"{RED}E2EE Handshake failed: {e}{RESET}")
        return None, None

def send_plain():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    log(f"\n{AMBER}MODE: PLAINTEXT (Insecure){RESET}")
    for seq in range(PACKET_COUNT):
        msg = MESSAGES[seq % len(MESSAGES)]
        pkt = struct.pack("!BIH", 0x01, seq, len(msg)) + msg
        sock.sendto(pkt, (CONFIG["sat_host"], SAT_PORT))
        sock.sendto(pkt, (CONFIG["sat_host"], CONFIG["eaves_port"]))
        log(f"{AMBER}[TX #{seq:02d}]{RESET} PLAIN {len(pkt):>4}B")
        time.sleep(INTERVAL_S)

def send_encrypted():
    log(f"\n{CYAN}MODE: E2EE (End-to-End Encryption Only){RESET}")
    aes, sid = do_e2e_handshake(CONFIG["key_host"], KEY_PORT)
    if not aes: return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for seq in range(PACKET_COUNT):
        msg = MESSAGES[seq % len(MESSAGES)]
        nonce = os.urandom(12)
        aad = sid + struct.pack("!I", seq)
        ct = aes.encrypt(nonce, msg, aad)
        pkt = struct.pack("!BIH", 0x02, seq, len(ct)) + nonce + ct
        
        sock.sendto(pkt, (CONFIG["sat_host"], SAT_PORT))
        sock.sendto(pkt, (CONFIG["sat_host"], CONFIG["eaves_port"]))
        log(f"{GREEN}[TX #{seq:02d}]{RESET} E2EE  {len(pkt):>4}B")
        time.sleep(INTERVAL_S)

def main():
    parser = argparse.ArgumentParser(description="LEO Sender (E2EE Only)")
    parser.add_argument("mode", choices=["plain", "encrypted", "all"])
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--dashboard", action="store_true")
    args = parser.parse_args()

    CONFIG["sat_host"] = SAT_HOST_LOCAL if args.local else SAT_HOST_MININET
    CONFIG["key_host"] = KEY_HOST_LOCAL if args.local else KEY_HOST_MININET
    CONFIG["dashboard"] = args.dashboard

    log(f"{CYAN}{'═'*60}")
    log(f"  🚀 SENDER — Ground Station GS-46")
    log(f"{'═'*60}{RESET}")

    if args.mode == "plain": 
        send_plain()
    elif args.mode == "encrypted": 
        send_encrypted()
    else: # all
        send_plain()
        time.sleep(2)
        send_encrypted()

if __name__ == "__main__":
    main()
