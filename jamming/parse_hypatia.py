import networkx as nx

# ground stations
gs = {}
with open('/home/issei/workspace/leo/config_hypatia/ground_stations.txt', 'r') as f:
    for line in f:
        parts = line.strip().split(',')
        idx = int(parts[0])
        name = parts[1]
        if idx in [46, 63]:  # TP.HCM and Singapore
            gs[idx] = name

print("Ground stations demo:", gs)

# Đọc ISL (chỉ lấy vài cặp cho demo)
isl_graph = nx.Graph()
with open('isls.txt', 'r') as f:
    for line in f:
        if line.strip():
            a, b = map(int, line.strip().split())
            if a in [0,1,2] and b in [0,1,2]: 
                isl_graph.add_edge(a, b)

print("ISL demo:", list(isl_graph.edges()))

# GSL demo (
gsl = {46: [0], 63: [2]}  # GS46-Sat0, GS63-Sat2
print("GSL demo:", gsl)