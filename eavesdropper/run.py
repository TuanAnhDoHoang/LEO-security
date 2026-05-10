#!/usr/bin/python3

from mininet.net import Mininet
from mininet.node import Host
from mininet.topo import Topo
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.term import makeTerm

class LEOTopo(Topo):
    "Cấu trúc mạng LEO: h1 --- h2 --- h3"
    def build(self):
        # Thêm các host (Vệ tinh/Trạm đất)
        h1 = self.addHost('h1', ip='10.0.0.1/24')
        h2 = self.addHost('h2', ip='10.0.0.2/24')
        h3 = self.addHost('h3', ip='10.0.0.3/24')

        # Thêm các switch (Mininet cần switch để kết nối các host theo đường thẳng)
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')

        # Tạo liên kết: h1 <-> s1 <-> s2 <-> h3, h2 nối vào s1 hoặc s2
        self.addLink(h1, s1)
        self.addLink(s1, s2)
        self.addLink(h2, s1)
        self.addLink(h3, s2)

def run_simulation():
    "Khởi tạo mạng và chạy các script bảo mật"
    topo = LEOTopo()
    net = Mininet(topo=topo)
    net.start()

    h1, h2, h3 = net.get('h1', 'h2', 'h3')

    info("\n*** Đang khởi chạy các thành phần LEO...\n")

    # 1. Chạy Receiver và Sat-C trên h3 (Gom chung vào 1 terminal)
    info("h3: Khởi động Receiver & Satellite C\n")
    # Chúng ta dùng dấu ';' để chạy liên tiếp hoặc '&' để chạy song song trong cùng 1 xterm
    makeTerm(h3, title="Node h3 (Receiver & Sat-C)", 
             cmd="python3 receiver.py & python3 satellite.py sat-c; bash")

    # 2. Chạy Sat-B trên h2
    info("h2: Khởi động Satellite B\n")
    makeTerm(h2, title="Node h2 (Sat-B)", 
             cmd="python3 satellite.py sat-b; bash")

    # 3. Chạy Sat-A và Eavesdropper trên h1
    info("h1: Khởi động Satellite A & Eavesdropper\n")
    makeTerm(h1, title="Node h1 (Sat-A & Eavesdropper)", 
             cmd="python3 satellite.py sat-a & python3 eavesdropper.py; bash")

    # Chờ một chút để các dịch vụ khởi động xong
    import time
    time.sleep(2)

    # 4. Giao diện điều khiển (Input plain/encrypted)
    try:
        while True:
            mode = input("\nNhập chế độ gửi (plain/encrypted) hoặc 'exit': ").strip().lower()
            if mode == 'exit':
                break
            elif mode in ['plain', 'encrypted']:
                info(f"h1: Đang gửi gói tin {mode}...\n")
                # Chạy sender và in kết quả ra terminal
                output = h1.cmd(f'python3 sender.py {mode}')
                print(output)
            else:
                print("Lựa chọn không hợp lệ!")
    except KeyboardInterrupt:
        pass

    # Mở CLI nếu bạn muốn tương tác thủ công bằng lệnh Mininet
    # CLI(net)

    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run_simulation()
