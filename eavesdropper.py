"""
eavesdropper.py — Passive Eavesdropper (Man-in-the-Middle observer)
───────────────────────────────────────────────────────────────────
Lắng nghe tất cả traffic qua port Satellite Node.
Phân tích packet: nếu plaintext → đọc được payload.
                  nếu encrypted → chỉ thấy ciphertext ngẫu nhiên.

Chạy: python3 eavesdropper.py
  (phải chạy TRƯỚC sender và receiver)
"""

import socket
import struct
import time
import sys
import math
import collections

SNIFF_HOST = "10.0.0.2"
SNIFF_PORT = 9002          # Tap vào sau Satellite Node (xem README)

RED   = "\033[91m"; GREEN  = "\033[92m"; CYAN  = "\033[96m"
AMBER = "\033[93m"; DIM    = "\033[2m";  BOLD  = "\033[1m"; RESET = "\033[0m"

# ─────────────────────────────────────────────────────────────────────────────
def entropy(data: bytes) -> float:
    """Shannon entropy — mã hóa tốt → ≈8.0 bits/byte."""
    if not data:
        return 0.0
    freq = collections.Counter(data)
    n = len(data)
    return -sum((c/n) * math.log2(c/n) for c in freq.values())


def entropy_bar(e: float, width=20) -> str:
    filled = int(e / 8.0 * width)
    bar = "█" * filled + "░" * (width - filled)
    color = GREEN if e > 7.0 else (AMBER if e > 4.0 else RED)
    return f"{color}[{bar}]{RESET} {e:.2f} bits/B"


def parse_packet(raw: bytes):
    """Trả về dict với thông tin parse được từ packet."""
    if len(raw) < 7:
        return None
    ptype, seq, length = struct.unpack("!BIH", raw[:7])
    payload_raw = raw[7:]

    result = {
        "type":        ptype,
        "seq":         seq,
        "length":      length,
        "payload_raw": payload_raw,
        "readable":    False,
        "content":     None,
        "nonce":       None,
        "ciphertext":  None,
    }

    if ptype == 0x01:           # PLAINTEXT
        result["readable"] = True
        result["content"]  = payload_raw[:length]

    elif ptype == 0x02:         # ENCRYPTED
        if len(payload_raw) >= 12:
            result["nonce"]      = payload_raw[:12]
            result["ciphertext"] = payload_raw[12:12+length]

    return result


def display_packet(pkt, count):
    ts = time.strftime("%H:%M:%S")
    raw_payload = pkt["payload_raw"]
    e = entropy(raw_payload)

    print(f"\n{DIM}{'─'*60}{RESET}")
    print(f"  {DIM}[{ts}]{RESET}  Packet #{count:04d}  "
          f"seq={pkt['seq']}  size={7+len(raw_payload)}B")
    print(f"  Entropy : {entropy_bar(e)}")

    if pkt["type"] == 0x01:     # ══ PLAINTEXT ══
        print(f"  Type    : {AMBER}{BOLD}PLAINTEXT (0x01){RESET}  ← không mã hóa!")
        print(f"  {RED}{'▼'*50}{RESET}")
        print(f"  {RED}{BOLD}ĐỌC ĐƯỢC:{RESET}")
        try:
            decoded = pkt["content"].decode("utf-8")
            for line in decoded.split("|"):
                print(f"    {RED}│{RESET}  {line.strip()}")
        except Exception:
            print(f"    {RED}│{RESET}  {pkt['content']}")
        print(f"  {RED}{'▲'*50}{RESET}")
        print(f"  {AMBER}⚠  Eavesdropping THÀNH CÔNG — dữ liệu lộ hoàn toàn{RESET}")

    elif pkt["type"] == 0x02:   # ══ ENCRYPTED ══
        print(f"  Type    : {GREEN}{BOLD}ENCRYPTED (0x02){RESET}  AES-256-GCM")
        if pkt["nonce"]:
            print(f"  Nonce   : {DIM}{pkt['nonce'].hex()}{RESET}  (12B, random per packet)")
        if pkt["ciphertext"]:
            ct_preview = pkt["ciphertext"][:24]
            print(f"  Cipher  : {DIM}{ct_preview.hex()}...{RESET}")
            print(f"  {GREEN}{'─'*50}{RESET}")
            print(f"  {GREEN}{BOLD}KHÔNG ĐỌC ĐƯỢC:{RESET}")
            print(f"    {GREEN}│{RESET}  Ciphertext: {ct_preview.hex()[:32]}...")
            print(f"    {GREEN}│{RESET}  Không có key → không thể decrypt")
            print(f"    {GREEN}│{RESET}  Nonce thay đổi mỗi packet → replay bị chặn")
            print(f"  {GREEN}{'─'*50}{RESET}")
            print(f"  {GREEN}✓  Eavesdropping THẤT BẠI — E2EE bảo vệ thành công{RESET}")

    else:
        print(f"  Type    : UNKNOWN (0x{pkt['type']:02x})")


def print_summary(plain_count, enc_count, total):
    print(f"\n{'═'*60}")
    print(f"  TỔNG KẾT EAVESDROPPING")
    print(f"{'═'*60}")
    print(f"  Tổng packet nghe được : {total}")
    print(f"  Plaintext đọc được    : {AMBER}{plain_count}{RESET}  "
          f"({plain_count/max(total,1)*100:.0f}%)")
    print(f"  Encrypted (thất bại)  : {GREEN}{enc_count}{RESET}  "
          f"({enc_count/max(total,1)*100:.0f}%)")
    if enc_count > 0:
        print(f"\n  {GREEN}→ E2EE hiệu quả: {enc_count}/{total} packet được bảo vệ{RESET}")
    if plain_count > 0:
        print(f"\n  {RED}→ CẢNH BÁO: {plain_count} packet bị lộ nội dung!{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((SNIFF_HOST, SNIFF_PORT))
    sock.settimeout(30.0)

    print(f"{RED}{'═'*60}")
    print(f"  👁  EAVESDROPPER — Passive Sniffer")
    print(f"{'═'*60}{RESET}")
    print(f"  Lắng nghe tại : {SNIFF_HOST}:{SNIFF_PORT}")
    print(f"  Entropy ≈ 4.x → plaintext  |  Entropy ≈ 8.0 → encrypted")
    print(f"\n  Chờ traffic...\n")

    count = plain_count = enc_count = 0

    try:
        while True:
            try:
                raw, addr = sock.recvfrom(65535)
            except socket.timeout:
                break

            count += 1
            pkt = parse_packet(raw)

            if pkt is None:
                print(f"  [?] Malformed packet #{count}")
                continue

            display_packet(pkt, count)

            if pkt["type"] == 0x01:
                plain_count += 1
            elif pkt["type"] == 0x02:
                enc_count += 1

    except KeyboardInterrupt:
        pass

    print_summary(plain_count, enc_count, count)


if __name__ == "__main__":
    main()
