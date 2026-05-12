# satellite.py 
import socket
import sys


# if local: 
#     sat-a: localhost:9000 -> 9001
#     sat-b: localhost:9001 -> 9002 (receiver)
# if mininet:
#     sat-a: 10.0.1.2/10.0.2.1 port 9000
#     sat-b: 10.0.2.2/10.0.3.2 port 9000

if len(sys.argv) < 4:
    print("Usage: python3 satellite.py <my_listen_ip> <forward_ip> <port>")
    sys.exit(1)

listen_ip = sys.argv[1]
forward_ip = sys.argv[2]
port_listen = int(sys.argv[3])
port_forward = int(sys.argv[4])

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((listen_ip, port_listen))

print(f"[Satellite] Listening on {listen_ip}:{port_listen} → Forward to {forward_ip}:{port_forward}")

while True:
    data, addr = sock.recvfrom(4096)
    print(f"[Satellite] Forwarded {len(data)} bytes from {addr[0]}")
    sock.sendto(data, (forward_ip, port_forward))