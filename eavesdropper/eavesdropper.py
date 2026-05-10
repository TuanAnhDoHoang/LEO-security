import socket
import threading
import time
import struct
import argparse

# ── Defaults ──────────────────────────────────────────────────────────────────
EAVES_HOST_MININET = "10.0.0.1"
EAVES_HOST_LOCAL   = "127.0.0.1"
LISTEN_PORT        = 9002

RED   = "\033[91m"; GREEN  = "\033[92m"; CYAN  = "\033[96m"
AMBER = "\033[93m"; DIM    = "\033[2m";  BOLD  = "\033[1m"; RESET = "\033[0m"

CONFIG = {
    "eaves_host": EAVES_HOST_MININET,
    "dashboard": False
}

def log(msg):
    if CONFIG["dashboard"]:
        print(f"[EAVESDROPPER] {msg}", flush=True)
    else:
        print(msg, flush=True)

def parse_packet(raw):
    if len(raw) < 7: return None
    ptype, seq, length = struct.unpack("!BIH", raw[:7])
    return {"type": ptype, "seq": seq, "content": raw[7:]}

def display_packet(pkt):
    log(f"\n{BOLD}PACKET SNIFFED [Seq #{pkt['seq']:02d}]{RESET}")
    if pkt["type"] == 0x01:
        log(f"  Type    : {AMBER}{BOLD}PLAINTEXT (0x01){RESET}")
        log(f"  {RED}{BOLD}ĐỌC ĐƯỢC:{RESET}")
        try:
            for line in pkt["content"].decode().split("|"): log(f"    │ {line.strip()}")
        except: log(f"    │ {pkt['content']}")
    elif pkt["type"] == 0x02:
        log(f"  Type    : {GREEN}{BOLD}E2E ENCRYPTED (0x02){RESET}")
        log(f"  Cipher  : {DIM}{pkt['content'][:16].hex()}...{RESET}")
        log(f"  {GREEN}✓  Eavesdropping THẤT BẠI — E2EE bảo vệ{RESET}")
    elif pkt["type"] == 0x03:
        log(f"  Type    : {CYAN}{BOLD}LINK ENCRYPTED (0x03){RESET}")
        log(f"  {CYAN}✓  Eavesdropping THẤT BẠI — Link Security bảo vệ{RESET}")

def main():
    parser = argparse.ArgumentParser(description="LEO Eavesdropper Monitor")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--dashboard", action="store_true")
    args = parser.parse_args()

    CONFIG["eaves_host"] = EAVES_HOST_LOCAL if args.local else EAVES_HOST_MININET
    CONFIG["dashboard"] = args.dashboard

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((CONFIG["eaves_host"], LISTEN_PORT))

    log(f"{RED}{'═'*60}")
    log(f"  👁  EAVESDROPPER — Passive Monitor (Sniffing 10.0.0.1)")
    log(f"{'═'*60}{RESET}")
    log(f"  Listening on : {CONFIG['eaves_host']}:{LISTEN_PORT}")

    try:
        while True:
            raw, addr = sock.recvfrom(65535)
            pkt = parse_packet(raw)
            if pkt: display_packet(pkt)
    except KeyboardInterrupt: pass

if __name__ == "__main__":
    main()
