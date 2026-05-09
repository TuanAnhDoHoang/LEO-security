"""
satellite.py — Giả lập Satellite Node (LEO relay)
─────────────────────────────────────────────────
Giả lập delay, jitter, loss, và corruption.
"""

import socket
import threading
import random
import time
import sys
import argparse

# ── Hypatia Steps ─────────────────────────────────────────────────────────────
HYPATIA = {"delay_ms": 6.0, "jitter_ms": 0.9, "loss_pct": 0.1, "corrupt_pct": 0.01}

# ── Addresses ─────────────────────────────────────────────────────────────────
SATA_LISTEN_MININET = "10.0.0.1"; SATA_FWD_MININET = "10.0.0.2"
SATB_LISTEN_MININET = "10.0.0.3"; SATB_FWD_MININET = "10.0.0.3"
LOCAL = "127.0.0.1"

CYAN  = "\033[96m"; AMBER = "\033[93m"
RED   = "\033[91m"; DIM   = "\033[2m"; RESET = "\033[0m"

class LEOLinkEmulator:
    def __init__(self, cfg):
        self.delay_s = cfg["delay_ms"]/1000; self.jitter_s = cfg["jitter_ms"]/1000
        self.loss_p = cfg["loss_pct"]/100; self.corrupt_p = cfg["corrupt_pct"]/100
    def apply(self, data):
        if random.random() < self.loss_p: return None
        time.sleep(max(0.0, random.gauss(self.delay_s, self.jitter_s)))
        if random.random() < self.corrupt_p and data:
            ba = bytearray(data); ba[random.randrange(len(ba))] ^= 1 << random.randrange(8)
            return bytes(ba)
        return data

stats = {"rx": 0, "tx": 0, "dropped": 0}

def forward_worker(raw, link, fwd_sock, fwd_addr, sat_name, dashboard):
    stats["rx"] += 1
    result = link.apply(raw)
    p = f"[{sat_name}] " if dashboard else ""
    if result is None:
        stats["dropped"] += 1
        print(f"{p}{RED}DROP #{stats['rx']}{RESET}", flush=True)
        return
    print(f"{p}{DIM}FWD #{stats['rx']} {len(result)}B → {fwd_addr[0]}:{fwd_addr[1]}{RESET}", flush=True)
    try: fwd_sock.sendto(result, fwd_addr); stats["tx"] += 1
    except Exception as e: print(f"{p}{RED}Error: {e}{RESET}", flush=True)

def main():
    parser = argparse.ArgumentParser(description="LEO Satellite Relay")
    parser.add_argument("role", choices=["sat-a", "sat-b"])
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--dashboard", action="store_true")
    args = parser.parse_args()

    if args.role == "sat-a":
        sat_name, listen_host = "SAT-A", (LOCAL if args.local else SATA_LISTEN_MININET)
        listen_port, fwd_host, fwd_port = 9000, (LOCAL if args.local else SATA_FWD_MININET), 9002
    else:
        sat_name, listen_host = "SAT-B", (LOCAL if args.local else SATB_LISTEN_MININET)
        listen_port, fwd_host, fwd_port = 9003, (LOCAL if args.local else SATB_FWD_MININET), 9001

    link = LEOLinkEmulator(HYPATIA)
    listen_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listen_sock.bind((listen_host, listen_port))
    fwd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    p = f"[{sat_name}] " if args.dashboard else ""
    print(f"{p}{CYAN}🛰 {sat_name} started on {listen_host}:{listen_port}{RESET}", flush=True)

    try:
        while True:
            raw, _ = listen_sock.recvfrom(65535)
            threading.Thread(target=forward_worker, args=(raw, link, fwd_sock, (fwd_host, fwd_port), sat_name, args.dashboard), daemon=True).start()
    except KeyboardInterrupt: pass

if __name__ == "__main__":
    main()
