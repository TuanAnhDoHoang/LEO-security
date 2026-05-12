#!/usr/bin/python
import socket
import struct
import threading
import time
import argparse
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


RECV_HOST_MININET = "10.0.3.1"
RECV_HOST_LOCAL   = "127.0.0.1"
RECV_PORT         = 9002
KEY_PORT          = 9100

KEY_PORT = 9100
UDP_PORT = 9000

# Lưu thời điểm bắt đầu toàn cục
START_TIME = time.time()

CONFIG = {
    "recv_host": RECV_HOST_MININET,
    "port": UDP_PORT,
    "dashboard": False
}

def get_ts(pktCount=0):
    """Trả về chuỗi thời gian trôi qua tính bằng giây: [+0.000s]"""
    elapsed = time.time() - START_TIME
    avg_time = elapsed / pktCount if pktCount > 0 else elapsed
    return f"[+{avg_time:07.3f}s]"

def key_exchange_listener(aesgcm_container):
    print(f"[RECEIVER] {get_ts()} Receiver đang lắng nghe TCP Key Exchange trên port {KEY_PORT}...")
    key_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    key_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    key_sock.bind(('', KEY_PORT))
    key_sock.listen(1)

    while True:
        conn, addr = key_sock.accept()
        print(f"[RECEIVER] {get_ts()} Nhận yêu cầu trao đổi khóa từ {addr}")

        try:
            peer_public = conn.recv(32)

            private_key = X25519PrivateKey.generate()
            public_key = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            conn.send(public_key)
            conn.close()

            # Tính toán shared key
            peer_public_key = X25519PublicKey.from_public_bytes(peer_public)
            shared = private_key.exchange(peer_public_key)
            key = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=None,
                info=b"LEO-SAT-E2EE"
            ).derive(shared)

            aesgcm_container[0] = AESGCM(key)
            print(f"[RECEIVER] {get_ts()} Trao đổi khóa THÀNH CÔNG! AES-256-GCM đã sẵn sàng.")
        except Exception as e:
            print(f"[RECEIVER] {get_ts()} Lỗi trao đổi khóa: {e}")

def udp_listener(aesgcm_container, stats_container):
    print(f"[RECEIVER] {get_ts()} Đang lắng nghe dữ liệu UDP trên port {CONFIG['port']}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(CONFIG["recv_host"], CONFIG["port"])
    sock.bind((CONFIG["recv_host"], CONFIG["port"]))

    # stats_container layout:
    #   [0] pktCount     - tổng số gói đã nhận
    #   [1] total_bytes  - tổng bytes đã nhận
    #   [2] first_recv_time - thời điểm nhận gói đầu tiên (None ban đầu)

    while True:
        data, addr = sock.recvfrom(4096)
        recv_time = time.time()  # Ghi nhận thời điểm nhận gói ngay lập tức

        # ── Ghi nhận thời điểm gói đầu tiên ──────────────────────────────────
        if stats_container[2] is None:
            stats_container[2] = recv_time
            print(f"[RECEIVER] {get_ts()} Nhận gói đầu tiên — bắt đầu tính thời gian trung bình.")

        stats_container[0] += 1
        stats_container[1] += len(data)
        pkt_count = stats_container[0]

        # ── Tính thời gian trung bình mỗi gói (tính từ gói đầu tiên) ─────────
        elapsed_since_first = recv_time - stats_container[2]
        # Khoảng thời gian từ gói đầu đến gói hiện tại / (số khoảng = pktCount - 1)
        # Nếu chỉ có 1 gói thì avg_interval = 0 (chưa có khoảng nào)
        avg_interval_ms = (elapsed_since_first / (pkt_count - 1) * 1000) if pkt_count > 1 else 0.0

        if len(data) < 7:
            continue

        pkt_type = data[0]

        # ── Gói tin đã mã hóa (0x02) ─────────────────────────────────────────
        if pkt_type == 0x02 and aesgcm_container[0] is not None:
            seq = struct.unpack("!I", data[1:5])[0]
            nonce = data[7:19]
            ct_tag = data[19:]
            try:
                plaintext = aesgcm_container[0].decrypt(nonce, ct_tag, data[0:5])
                print(
                    f"[RECEIVER] {get_ts(pkt_count)} "
                    f"Decrypted | seq={seq} | avg_interval={avg_interval_ms:.3f}ms | "
                    f"{plaintext.decode(errors='replace')}"
                )
            except Exception as e:
                print(
                    f"[RECEIVER] {get_ts(pkt_count)} "
                    f"Decrypt THẤT BẠI | avg_interval={avg_interval_ms:.3f}ms | {e}"
                )
        else:
            # ── Gói tin thô hoặc chưa có khóa ────────────────────────────────
            print(
                f"[RECEIVER] {get_ts(pkt_count)} "
                f"Gói tin thô {len(data)} bytes từ {addr} | avg_interval={avg_interval_ms:.3f}ms"
            )

def main():
    parser = argparse.ArgumentParser(description="LEO Receiver (E2EE Only)")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--dashboard", action="store_true")
    args = parser.parse_args()

    CONFIG["recv_host"] = RECV_HOST_LOCAL if args.local else RECV_HOST_MININET
    CONFIG["port"] = RECV_PORT if args.local else UDP_PORT
    CONFIG["dashboard"] = args.dashboard

    aesgcm_container = [None]
    stats_container = [0, 0, None]  # [pktCount, total_bytes, first_recv_time]

    # Khởi chạy luồng trao đổi khóa
    key_thread = threading.Thread(target=key_exchange_listener, args=(aesgcm_container,), daemon=True)
    key_thread.start()

    # Chạy listener chính (UDP)
    try:
        udp_listener(aesgcm_container, stats_container)
    except KeyboardInterrupt:
        pkt_count   = stats_container[0]
        total_bytes = stats_container[1]
        first_time  = stats_container[2]
        avg_size    = total_bytes / pkt_count if pkt_count > 0 else 0

        if first_time is not None and pkt_count > 1:
            elapsed_since_first = time.time() - first_time
            final_avg_interval_ms = elapsed_since_first / (pkt_count - 1) * 1000
        else:
            final_avg_interval_ms = 0.0

        print(f"\n{get_ts(pkt_count)} [RECEIVER] Đang dừng Receiver...")
        print(f"[RECEIVER] Total packets    : {pkt_count}")
        print(f"[RECEIVER] Total bytes      : {total_bytes}")
        print(f"[RECEIVER] Avg packet size  : {avg_size:.2f} bytes")
        print(f"[RECEIVER] Avg inter-packet : {final_avg_interval_ms:.3f} ms/gói")

if __name__ == "__main__":
    main()