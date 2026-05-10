# LEO Security Simulation — Mininet Topology

## 1. Mininet Setup
Topology: Linear, 3 nodes (10.0.0.1, 10.0.0.2, 10.0.0.3)
```bash
sudo mn --topo linear,3
```

## 2. Configuration (IP & Roles)
- **10.0.0.1**: Sender, Satellite A, Eavesdropper
- **10.0.0.2**: Satellite B
- **10.0.0.3**: Satellite C, Receiver

## 3. Run Components (Manual)

### Node 10.0.0.3 (h3)
```bash
h3 xterm -e "python3 receiver.py" &
h3 xterm -e "python3 satellite.py sat-c" &
```

### Node 10.0.0.2 (h2)
```bash
h2 xterm -e "python3 satellite.py sat-b" &
```

### Node 10.0.0.1 (h1)
```bash
h1 xterm -e "python3 satellite.py sat-a" &
h1 xterm -e "python3 eavesdropper.py" &
```

### Node 10.0.0.1 (h1) — Start Transmission
```bash
h1 xterm -e "python3 sender.py plain" &
h1 xterm -e "python3 sender.py encrypted" &
```

## 4. Automated Demo
On any node:
```bash
python3 run_demo.py
```
