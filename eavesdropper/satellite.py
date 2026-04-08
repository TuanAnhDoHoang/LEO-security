"""
satellite.py — Giả lập Satellite Node (LEO relay)
─────────────────────────────────────────────────
Nhận packet từ Ground Station, áp dụng delay/jitter/loss
giống tc netem, rồi forward đến đích.

Tham số từ Bước 1 (Hypatia):
  delay  = 6.0 ms  (one-way, HCMC→Singapore)
  jitter = 0.9 ms
  loss   = 0.1%

Chạy: python3 satellite.py
"""

import socket
import threading
import random
import time
import sys

# ── Cấu hình từ Bước 1 ────────────────────────────────────────────────────────
HYPATIA = {
    "route":       "HCMC (GS-46) → Singapore (GS-63)",
    "delay_ms":    6.0,
    "jitter_ms":   0.9,
    "loss_pct":    0.1,
    "corrupt_pct": 0.01,
}

SAT_LISTEN_HOST  = "10.0.0.1"
SAT_LISTEN_PORT  = 9000
SAT_FORWARD_HOST = "10.0.0.3"
SAT_FORWARD_PORT = 9001

CYAN  = "\033[96m"; AMBER = "\033[93m"
RED   = "\033[91m"; DIM   = "\033[2m"; RESET = "\033[0m"

stats = {"rx": 0, "tx": 0, "dropped": 0, "corrupted": 0}


class LEOLinkEmulator:
    """Giả lập kênh vô tuyến LEO: delay + jitter + loss + corruption."""

    def __init__(self, cfg):
        self.delay_s   = cfg["delay_ms"]    / 1000
        self.jitter_s  = cfg["jitter_ms"]   / 1000
        self.loss_p    = cfg["loss_pct"]    / 100
        self.corrupt_p = cfg["corrupt_pct"] / 100

    def apply(self, data):
        """None = dropped, bytes = delivered (possibly corrupted)."""
        if random.random() < self.loss_p:
            return None
        time.sleep(max(0.0, random.gauss(self.delay_s, self.jitter_s)))
        if random.random() < self.corrupt_p and data:
            ba = bytearray(data)
            ba[random.randrange(len(ba))] ^= 1 << random.randrange(8)
            return bytes(ba)
        return data


def forward_worker(raw, link, fwd_sock, fwd_addr):
    stats["rx"] += 1
    result = link.apply(raw)
    if result is None:
        stats["dropped"] += 1
        print(f"{RED}[SAT] DROP  #{stats['rx']:04d}  "
              f"(total drop={stats['dropped']}){RESET}")
        return
    if result != raw:
        stats["corrupted"] += 1
        print(f"{AMBER}[SAT] CORRUPT #{stats['rx']:04d}{RESET}")
    
    print(f"{DIM}[SAT] FWD #{stats['rx']:04d}  {len(result)}B → {fwd_addr[0]}{RESET}")

    try:
        fwd_sock.sendto(result, fwd_addr)
        fwd_sock.sendto(result, ("10.0.0.2", 9002))        
        stats["tx"] += 1
    except Exception as e:
        print(f"{RED}[SAT] Forward error: {e}{RESET}")


def main():
    link = LEOLinkEmulator(HYPATIA)

    listen_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listen_sock.bind((SAT_LISTEN_HOST, SAT_LISTEN_PORT))

    fwd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print(f"{CYAN}{'═'*58}")
    print(f"  🛰  SATELLITE NODE — LEO Relay")
    print(f"{'═'*58}{RESET}")
    print(f"  Route  : {HYPATIA['route']}")
    print(f"  Delay  : {HYPATIA['delay_ms']} ms ± {HYPATIA['jitter_ms']} ms  "
          f"[từ Hypatia Bước 1]")
    print(f"  Loss   : {HYPATIA['loss_pct']} %    Listen: :{SAT_LISTEN_PORT}"
          f"  → Forward: :{SAT_FORWARD_PORT}")
    print()

    try:
        while True:
            raw, _ = listen_sock.recvfrom(65535)
            threading.Thread(
                target=forward_worker,
                args=(raw, link, fwd_sock,
                      (SAT_FORWARD_HOST, SAT_FORWARD_PORT)),
                daemon=True
            ).start()
    except KeyboardInterrupt:
        print(f"\n{DIM}[SAT] rx={stats['rx']} tx={stats['tx']} "
              f"drop={stats['dropped']} corrupt={stats['corrupted']}{RESET}")


if __name__ == "__main__":
    main()
