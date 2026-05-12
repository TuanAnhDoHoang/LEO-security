#!/usr/bin/python
from mininet.net import Mininet
from mininet.node import Host
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.link import TCLink

class LEOTopo:
    def __init__(self):
        self.net = Mininet(controller=None, link=TCLink, autoStaticArp=True)

        # 4 node
        h_hcm  = self.net.addHost('h_hcm',  ip=None)
        h_sat1 = self.net.addHost('h_sat1', ip=None)
        h_sat2 = self.net.addHost('h_sat2', ip=None)
        h_sing = self.net.addHost('h_sing', ip=None)
        
        attacker = self.net.addHost('attacker', ip=None)
        
        # setup delay
        with open('config_hypatia/description.txt') as f:
            lines = f.readlines()
            max_gsl = float(lines[0].split('=')[1].strip())
            max_isl = float(lines[1].split('=')[1].strip())

        delay_gsl = f"{int(max_gsl / 3e8 * 1000)}ms"
        delay_isl = f"{int(max_isl / 3e8 * 1000)}ms"

        # link h and s
        self.net.addLink(h_hcm,  h_sat1, bw=1, delay=delay_gsl, loss=0.1, jitter='0.9ms', quantum=1000)
        self.net.addLink(h_sat1, h_sat2, bw=5, delay=delay_isl, loss=0.1, jitter='0.9ms', quantum=5000)
        self.net.addLink(h_sat2, h_sing, bw=5, delay=delay_gsl, loss=0.1, jitter='0.9ms', quantum=5000)

        # === add ATTACKER ===
        self.net.addLink(attacker, h_hcm, bw=1000, delay='1ms', loss=0, quantum=10000)

        self.net.build()
        self.net.start()

        # set ip
        """ 
        hcm<->sat1 10.0.1 (1)
        sat1<->sat2 10.0.2 (2)
        sat2<->sing 10.0.3 (3)
        """
        # (1)
        h_hcm.cmd('ip addr add 10.0.1.1/24 dev h_hcm-eth0')
        h_sat1.cmd('ip addr add 10.0.1.2/24 dev h_sat1-eth0')

        # (2)
        h_sat1.cmd('ip addr add 10.0.2.1/24 dev h_sat1-eth1')   
        h_sat2.cmd('ip addr add 10.0.2.2/24 dev h_sat2-eth0') 
        
        # (3)
        h_sat2.cmd('ip addr add 10.0.3.2/24 dev h_sat2-eth1')   
        h_sing.cmd('ip addr add 10.0.3.1/24 dev h_sing-eth0')

        # Attacker <-> HCM (subnet 10.0.100.0/24)
        attacker.cmd('ip addr add 10.0.100.100/24 dev attacker-eth0')
        h_hcm.cmd('ip addr add 10.0.100.1/24 dev h_hcm-eth1')

        # turn on interface
        for h in [h_hcm, h_sat1, h_sat2, h_sing,attacker]:
            for intf in h.intfNames():
                h.cmd(f'ip link set {intf} up')

        # IP forwarding satelline
        h_sat1.cmd('sysctl -w net.ipv4.ip_forward=1 > /dev/null 2>&1')
        h_sat2.cmd('sysctl -w net.ipv4.ip_forward=1 > /dev/null 2>&1')

        # Static Route
        h_hcm.cmd('ip route add default via 10.0.1.2')
        h_sat1.cmd('ip route add 10.0.3.0/24 via 10.0.2.2')
        h_sat2.cmd('ip route add 10.0.1.0/24 via 10.0.2.1')
        h_sing.cmd('ip route add default via 10.0.3.2')

        h_hcm.cmd('ip route add 10.0.100.0/24 dev h_hcm-eth1')

        # attacker's route hcm
        attacker.cmd('ip route add default via 10.0.100.1')


        print("===  DEMO LEO ===")
        print("HCM (10.0.1.1) ──GSL── Sat1 (10.0.1.2/10.0.2.1) ──ISL── Sat2 (10.0.2.2/10.0.3.2) ──GSL── Singapore (10.0.3.1)")

    def run(self):
        CLI(self.net)

if __name__ == '__main__':
    setLogLevel('info')
    topo = LEOTopo()
    topo.run()
