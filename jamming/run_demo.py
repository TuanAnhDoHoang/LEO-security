from mininet.net import Mininet
from mininet.node import Controller
from mininet.cli import CLI
from mininet.log import setLogLevel, info
import os

def run_demo():
    # Khởi tạo mạng Mininet
    net = Mininet(controller=Controller)
    net.addController('c0')

    info('*** Đang đọc dữ liệu từ ground_stations.txt...\n')
    hosts = {}

    file_path = 'demo_do_an/ground_stations.txt'
    
    if not os.path.exists(file_path):
        info('LỖI: Không tìm thấy file dữ liệu. Hãy chắc chắn bạn đã tạo thư mục demo_do_an và copy file vào.\n')
        return

    # Đọc file chứa thông tin trạm mặt đất
    with open(file_path, 'r') as f:
        for line in f:
            data = line.strip().split(',')
            node_id = data[0]
            city_name = data[1]
            
            # Khởi tạo Node 0 (Tokyo) và Node 1 (Delhi) để demo
            if node_id in ['0', '1']:
                ip_addr = f'10.0.0.{int(node_id) + 1}'
                hosts[node_id] = net.addHost(f'h{node_id}', ip=ip_addr)
                info(f'-> Đã tạo trạm {city_name} (Node {node_id}) với IP: {ip_addr}\n')

    info('*** Đang khởi tạo Vệ tinh giả lập (Switch s1)...\n')
    s1 = net.addSwitch('s1')
    
    info('*** Đang thiết lập liên kết vô tuyến GSL...\n')
    net.addLink(hosts['0'], s1)
    net.addLink(hosts['1'], s1)

    info('*** Bắt đầu khởi động mạng LEO mô phỏng...\n')
    net.start()

    info('*** Mạng đã sẵn sàng! Chuyển sang giao diện Mininet.\n')
    CLI(net)

    info('*** Đang tắt mạng...\n')
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run_demo()
