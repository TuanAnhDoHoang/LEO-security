"""
eavesdropper.py — Eavesdropper (Active Relay / Man-in-the-Middle)
─────────────────────────────────────────────────────────────────
Nhận packet từ SAT-A, sniff/phân tích, rồi forward sang SAT-B.
"""

import socket
import struct
import time
import sys
import math
import threading
import collections
import argparse

# ── Defaults ──────────────────────────────────────────────────────────────────
EAVES_HOST_MININET = "10.0.0.2"
EAVES_HOST_LOCAL   = "127.0.0.1"

FWD_TO_B_HOST_MININET = "10.0.0.3"
FWD_TO_B_HOST_LOCAL   = "127.0.0.1"
FWD_TO_B_PORT         = 9003

FWD_TO_A_HOST_MININET = "10.0.0.1"
FWD_TO_A_HOST_LOCAL   = "127.0.0.1"
FWD_TO_A_PORT         = 9006

SNIFF_A_PORT = 9002
SNIFF_B_PORT = 9005

RED   = "\033[91m"; GREEN  = "\033[92m"; CYAN  = "\033[96m"
AMBER = "\033[93m"; DIM    = "\033[2m";  BOLD  = "\033[1m"; RESET = "\033[0m"

CONFIG = {
    "eaves_host": EAVES_HOST_MININET,
    "fwd_to_b": FWD_TO_B_HOST_MININET,
    "fwd_to_a": FWD_TO_A_HOST_MININET,
    "dashboard": False
}

def log(msg):
    if CONFIG["dashboard"]:
        print(f"[EAVESDROPPER] {msg}", flush=True)
    else:
        print(msg, flush=True)

def entropy(data: bytes) -> float:
    if not data: return 0.0
    freq = collections.Counter(data); n = len(data)
    return -sum((c/n) * math.log2(c/n) for c in freq.values())

def entropy_bar(e: float, width=20) -> str:
    filled = int(e / 8.0 * width)
    bar = "█" * filled + "░" * (width - filled)
    color = GREEN if e > 7.0 else (AMBER if e > 4.0 else RED)
    return f"{color}[{bar}]{RESET} {e:.2f} bits/B"

def parse_packet(raw: bytes):
    if len(raw) < 7: return None
    ptype, seq, length = struct.unpack("!BIH", raw[:7])
    payload_raw = raw[7:]
    res = {"type": ptype, "seq": seq, "length": length, "payload": payload_raw}
    if ptype == 0x01: res["content"] = payload_raw[:length]
    elif ptype == 0x02 and len(payload_raw) >= 12:
        res["nonce"] = payload_raw[:12]
        res["ciphertext"] = payload_raw[12:12+length]
    return res

def display_packet(pkt, count, direction):
    ts = time.strftime("%H:%M:%S")
    e = entropy(pkt["payload"])
    arrow = "→" if direction == "forward" else "←"
    log(f"\n{DIM}{'─'*50}{RESET}")
    log(f"  [{ts}] Pkt #{count:03d} seq={pkt['seq']} [{direction} {arrow}]")
    log(f"  Entropy : {entropy_bar(e)}")
    if pkt["type"] == 0x01:
        log(f"  Type    : {AMBER}{BOLD}PLAINTEXT (0x01){RESET}")
        log(f"  {RED}{BOLD}ĐỌC ĐƯỢC:{RESET}")
        try:
            for line in pkt["content"].decode().split("|"): log(f"    │ {line.strip()}")
        except: log(f"    │ {pkt['content']}")
        log(f"  {AMBER}⚠  Eavesdropping THÀNH CÔNG{RESET}")
    elif pkt["type"] == 0x02:
        log(f"  Type    : {GREEN}{BOLD}ENCRYPTED (0x02){RESET}")
        if "ciphertext" in pkt:
            log(f"  Cipher  : {DIM}{pkt['ciphertext'][:16].hex()}...{RESET}")
            log(f"  {GREEN}✓  Eavesdropping THẤT BẠI — E2EE bảo vệ{RESET}")

def relay_thread(recv_sock, fwd_sock, fwd_addr, direction, counter, stats_lock):
    while True:
        try: raw, _ = recv_sock.recvfrom(65535)
        except: continue
        with stats_lock:
            counter[0] += 1
            count = counter[0]
        pkt = parse_packet(raw)
        if pkt: display_packet(pkt, count, direction)
        try: fwd_sock.sendto(raw, fwd_addr)
        except: pass

def main():
    parser = argparse.ArgumentParser(description="LEO Eavesdropper")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--dashboard", action="store_true")
    args = parser.parse_args()

    CONFIG["eaves_host"] = EAVES_HOST_LOCAL if args.local else EAVES_HOST_MININET
    CONFIG["fwd_to_b"] = FWD_TO_B_HOST_LOCAL if args.local else FWD_TO_B_HOST_MININET
    CONFIG["fwd_to_a"] = FWD_TO_A_HOST_LOCAL if args.local else FWD_TO_A_HOST_MININET
    CONFIG["dashboard"] = args.dashboard

    sock_a = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_a.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock_a.bind((CONFIG["eaves_host"], SNIFF_A_PORT))
    
    sock_b = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_b.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock_b.bind((CONFIG["eaves_host"], SNIFF_B_PORT))

    fwd_to_b = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    fwd_to_a = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    log(f"{RED}{'═'*60}")
    log(f"  👁  EAVESDROPPER — MitM Active Relay")
    log(f"{'═'*60}{RESET}")
    log(f"  Sniff A  : {CONFIG['eaves_host']}:{SNIFF_A_PORT}")
    log(f"  Forward B: {CONFIG['fwd_to_b']}:{FWD_TO_B_PORT}")

    counter = [0, 0, 0]; lock = threading.Lock()
    threading.Thread(target=relay_thread, args=(sock_a, fwd_to_b, (CONFIG["fwd_to_b"], FWD_TO_B_PORT), "forward", counter, lock), daemon=True).start()
    threading.Thread(target=relay_thread, args=(sock_b, fwd_to_a, (CONFIG["fwd_to_a"], FWD_TO_A_PORT), "reverse", counter, lock), daemon=True).start()

    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: pass

if __name__ == "__main__":
    main()