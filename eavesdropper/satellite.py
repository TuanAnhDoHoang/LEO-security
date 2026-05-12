import socket
import random
import time
import argparse

# ── Hypatia Steps ─────────────────────────────────────────────────────────────
HYPATIA = {"delay_ms": 6.0, "jitter_ms": 0.9, "loss_pct": 0.1, "corrupt_pct": 0.01}

# ── Addresses ─────────────────────────────────────────────────────────────────
LOCAL = "127.0.0.1"

CYAN  = "\033[96m"; AMBER = "\033[93m"
GREEN = "\033[92m"; RED   = "\033[91m"; DIM   = "\033[2m"; RESET = "\033[0m"

def relay_thread(recv_sock, fwd_host, fwd_port, sat_name):
    while True:
        try:
            raw, addr = recv_sock.recvfrom(65535)
            if not raw: continue
            
            # Simulated Latency & Loss
            time.sleep(max(0, random.gauss(HYPATIA["delay_ms"], HYPATIA["jitter_ms"])) / 1000)
            if random.random() < HYPATIA["loss_pct"] / 100:
                print(f"[{sat_name}] {RED}Packet dropped (simulated loss){RESET}", flush=True)
                continue

            # Forward packet transparently
            out_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            out_sock.sendto(raw, (fwd_host, fwd_port))
            
            ptype = raw[0]
            pname = {0x01: "PLAIN", 0x02: "E2EE"}.get(ptype, f"UNKNOWN({hex(ptype)})")
            print(f"[{sat_name}] {DIM}Relayed {pname} packet to {fwd_host}:{fwd_port}{RESET}", flush=True)
        except Exception as e:
            print(f"[{sat_name}] Error: {e}", flush=True)

def main():
    parser = argparse.ArgumentParser(description="LEO Satellite Relay (Transparent)")
    parser.add_argument("role", choices=["sat-a", "sat-b", "sat-c"])
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--dashboard", action="store_true")
    args = parser.parse_args()

    # ── Topology & Address Config ─────────────────────────────────────────────
    if args.role == "sat-a":
        sat_name = "SAT-A"
        listen_port = 9000
        fwd_host = LOCAL if args.local else "10.0.0.2"
        fwd_port = 9005 if args.local else 9000 # SAT-B
    elif args.role == "sat-b":
        sat_name = "SAT-B"
        listen_port = 9005 if args.local else 9000
        fwd_host = LOCAL if args.local else "10.0.0.3"
        fwd_port = 9006 if args.local else 9000 # SAT-C
    else: # sat-c
        sat_name = "SAT-C"
        listen_port = 9006 if args.local else 9000
        fwd_host = LOCAL if args.local else "10.0.0.3"
        fwd_port = 9007 if args.local else 9001 # Receiver

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((LOCAL if args.local else "0.0.0.0", listen_port))

    print(f"{CYAN}{'═'*60}")
    print(f"  🛰  {sat_name} — Transparent LEO Relay")
    print(f"{'═'*60}{RESET}")
    print(f"  Listening on : {listen_port}")
    print(f"  Forwarding to: {fwd_host}:{fwd_port}")

    relay_thread(sock, fwd_host, fwd_port, sat_name)

if __name__ == "__main__":
    main()
