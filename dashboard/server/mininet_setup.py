#!/usr/bin/python3
import os
import sys
import time
from mininet.net import Mininet
from mininet.topo import LinearTopo
from mininet.link import TCLink
from mininet.log import setLogLevel

def setup_mininet():
    # Clean up first
    os.system("sudo mn -c > /dev/null 2>&1")
    
    print("Initializing Mininet (linear,3)...")
    topo = LinearTopo(k=3)
    net = Mininet(topo=topo, link=TCLink, controller=None)
    net.start()
    
    # Configure TC rules as requested
    # s1-eth2: link to s2
    # s2-eth2: link to s1
    # s2-eth3: link to s3
    # s3-eth2: link to s2
    
    print("Applying TC rules (6ms delay, 0.1% loss)...")
    os.system("sudo tc qdisc add dev s1-eth2 root netem delay 6ms 0.9ms distribution normal loss 0.1%")
    os.system("sudo tc qdisc add dev s2-eth2 root netem delay 6ms 0.9ms distribution normal loss 0.1%")
    os.system("sudo tc qdisc add dev s2-eth3 root netem delay 6ms 0.9ms distribution normal loss 0.1%")
    os.system("sudo tc qdisc add dev s3-eth2 root netem delay 6ms 0.9ms distribution normal loss 0.1%")

    # Expose namespaces for dashboard to use 'ip netns exec'
    os.system("sudo mkdir -p /var/run/netns")
    for h in net.hosts:
        os.system(f"sudo ln -sf /proc/{h.pid}/ns/net /var/run/netns/{h.name}")
        print(f"Linked namespace for {h.name} (PID {h.pid})")
    
    print("Mininet ready. IPs: h1=10.0.0.1, h2=10.0.0.2, h3=10.0.0.3")
    
    # Keep alive until interrupted
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print("Stopping Mininet...")
        net.stop()
        os.system("sudo mn -c > /dev/null 2>&1")

if __name__ == "__main__":
    setLogLevel('info')
    setup_mininet()
