import socket
import threading
import os
import struct
import argparse
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from cryptography import x509

# ── Defaults ──────────────────────────────────────────────────────────────────
RECV_HOST_MININET = "10.0.0.3"
RECV_HOST_LOCAL   = "127.0.0.1"
RECV_PORT         = 9001
KEY_PORT          = 9100

GREEN  = "\033[92m"; CYAN = "\033[96m"; AMBER = "\033[93m"
RED    = "\033[91m"; DIM  = "\033[2m";  BOLD  = "\033[1m"; RESET = "\033[0m"

CONFIG = {
    "recv_host": RECV_HOST_MININET,
    "dashboard": False
}

def log(msg):
    if CONFIG["dashboard"]:
        print(f"[RECEIVER] {msg}", flush=True)
    else:
        print(msg, flush=True)

def load_certs():
    CERTS_DIR = os.path.join(os.path.dirname(__file__), "certs")
    with open(os.path.join(CERTS_DIR, "ca.crt"), "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read())
    with open(os.path.join(CERTS_DIR, "receiver.crt"), "rb") as f:
        my_cert_raw = f.read()
    with open(os.path.join(CERTS_DIR, "receiver.key"), "rb") as f:
        my_key = serialization.load_pem_private_key(f.read(), password=None)
    return ca_cert, my_cert_raw, my_key

class SessionState:
    def __init__(self, key, session_id):
        self.aesgcm = AESGCM(key)
        self.session_id = session_id

def do_handshake_server(key_sock) -> SessionState:
    ca_cert, my_cert_raw, my_id_key = load_certs()
    try:
        conn, addr = key_sock.accept()
        log(f"{CYAN}[KEY] E2EE Handshake kết nối từ {addr}{RESET}")
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
        log(f"{GREEN}[KEY] Handshake hoàn tất | session={session_id.hex()[:8]}...{RESET}")
        return SessionState(key, session_id)
    except Exception as e:
        log(f"{RED}[KEY] Handshake thất bại: {e}{RESET}")
        conn.close()
        return None

def handle_plain(seq, raw, length):
    msg = raw[:length].decode(errors='replace')
    log(f"\n{AMBER}[RX #{seq:02d}]{RESET} {AMBER}{BOLD}PLAINTEXT (INSECURE){RESET}")
    log(f"  {AMBER}└─ {msg}{RESET}")

def handle_encrypted(seq, raw, session):
    nonce = raw[:12]
    ciphertext = raw[12:]
    aad = session.session_id + struct.pack("!I", seq)
    try:
        pt = session.aesgcm.decrypt(nonce, ciphertext, aad)
        log(f"\n{GREEN}[RX #{seq:02d}]{RESET} {GREEN}{BOLD}E2EE DECRYPTED{RESET}")
        log(f"  {GREEN}└─ {pt.decode()}{RESET}")
    except InvalidTag:
        log(f"\n{RED}[RX #{seq:02d}]{RESET} {RED}GCM TAG INVALID — packet bị tamper!{RESET}")

def main():
    parser = argparse.ArgumentParser(description="LEO Receiver (E2EE Only)")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--dashboard", action="store_true")
    args = parser.parse_args()

    CONFIG["recv_host"] = RECV_HOST_LOCAL if args.local else RECV_HOST_MININET
    r_port = 9007 if args.local else RECV_PORT
    bind_host = RECV_HOST_LOCAL if args.local else "0.0.0.0"
    CONFIG["dashboard"] = args.dashboard

    try:
        recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        recv_sock.bind((bind_host, r_port))
        recv_sock.settimeout(1.0)

        key_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        key_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        key_sock.bind((bind_host, KEY_PORT))
        key_sock.listen(5)
        key_sock.settimeout(1.0)
    except Exception as e:
        log(f"{RED}[ERROR] Không thể bind socket: {e}{RESET}")
        return

    sessions = {"current": None}
    stop_event = threading.Event()

    def key_thread():
        while not stop_event.is_set():
            sess = do_handshake_server(key_sock)
            if sess: sessions["current"] = sess

    threading.Thread(target=key_thread, daemon=True).start()

    log(f"{GREEN}{'═'*60}")
    log(f"  📡 RECEIVER — E2EE Only Ground Station")
    log(f"{'═'*60}{RESET}")
    log(f"  Listening on : {r_port}")
    log(f"  E2EE Handshake: {KEY_PORT}")

    try:
        while True:
            try: raw, _ = recv_sock.recvfrom(65535)
            except socket.timeout: continue
            if len(raw) < 7: continue
            
            ptype, seq, length = struct.unpack("!BIH", raw[:7])
            if ptype == 0x01:
                handle_plain(seq, raw[7:], length)
            elif ptype == 0x02:
                sess = sessions.get("current")
                if sess: handle_encrypted(seq, raw[7:], sess)
                else: log(f"{AMBER}[RX #{seq:02d}] E2EE packet nhận được nhưng chưa có session!{RESET}")
    except KeyboardInterrupt: pass
    finally: stop_event.set()

if __name__ == "__main__":
    main()
