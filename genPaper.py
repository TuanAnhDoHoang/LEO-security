# generate_dynamic_state.py
import exputil
import satgenpy.satgen as satgen
import math

# ============================================================
# CẤU HÌNH - ĐÃ ĐIỀU CHỈNH ĐỂ KHỚP VỚI FILE CỦA BẠN
# ============================================================

NUM_ORBS = 72
NUM_SATS_PER_ORB = 22
TOTAL_SATS = NUM_ORBS * NUM_SATS_PER_ORB   # = 1584

INCLINATION_DEGREE = 53.0
ALTITUDE_M = 550000          # 550 km
ECCENTRICITY = 0.0000001
PHASE_DIFF = True

DYNAMIC_STATE_UPDATE_INTERVAL_MS = 100
SIMULATION_END_TIME_S = 200

GSL_MAX_QUEUE_SIZE_PKTS = 100
GSL_DATARATE_MEGABIT_PER_S = 10.0
ISL_MAX_QUEUE_SIZE_PKTS = 100
ISL_DATARATE_MEGABIT_PER_S = 10.0

GROUND_STATIONS_FILE = "satgenpy/data/ground_stations_cities_sorted_by_estimated_2025_pop_top_100.basic.txt"

OUTPUT_DIR = "dynamic_state_100ms_for_200s"

# ============================================================

EARTH_RADIUS_M = 6371000
ELEVATION_ANGLE_DEGREES = 25.0   # (không ảnh hưởng nhiều vì file description dùng max_gsl_length)

# Tính max GSL length (Hypatia thường dùng cách này)
MAX_GSL_LENGTH_M = math.sqrt(
    (ALTITUDE_M + EARTH_RADIUS_M)**2 - (EARTH_RADIUS_M * math.cos(math.radians(90 + ELEVATION_ANGLE_DEGREES)))**2
) - EARTH_RADIUS_M * math.sin(math.radians(90 + ELEVATION_ANGLE_DEGREES))
# Hoặc dùng giá trị bạn đã có trong description.txt
# MAX_GSL_LENGTH_M = 1089686.4181956202

local_shell = exputil.LocalShell()
local_shell.make_dir(OUTPUT_DIR, exist_ok=True)

# 1. Tạo TLEs
satgen.generate_tles_from_scratch_given_orbital_parameters(
    OUTPUT_DIR + "/tles.txt",
    "Starlink-550",           # Tên phải khớp
    NUM_ORBS,
    NUM_SATS_PER_ORB,
    PHASE_DIFF,
    INCLINATION_DEGREE,
    ECCENTRICITY,
    ALTITUDE_M,
)

# 2. Ground stations (copy từ file chuẩn của Hypatia)
satgen.generate_ground_stations(
    GROUND_STATIONS_FILE,
    OUTPUT_DIR + "/ground_stations.txt",
)

# 3. ISLs + Grid
satgen.generate_isls_plus_grid(
    OUTPUT_DIR + "/isls.txt",
    NUM_ORBS,
    NUM_SATS_PER_ORB,
)

# 4. GSL interfaces info
satgen.generate_gsl_interfaces_info(
    OUTPUT_DIR + "/gsl_interfaces_info.txt",
    TOTAL_SATS,
    satgen.read_ground_stations_basic(OUTPUT_DIR + "/ground_stations.txt"),
    1,   # num_gsl_interfaces_per_satellite
    1,   # num_gsl_interfaces_per_ground_station
    GSL_DATARATE_MEGABIT_PER_S,
    GSL_MAX_QUEUE_SIZE_PKTS,
    ISL_DATARATE_MEGABIT_PER_S,
    ISL_MAX_QUEUE_SIZE_PKTS,
)

# 5. Description.txt
with open(OUTPUT_DIR + "/description.txt", "w") as f:
    f.write(f"max_gsl_length_m={MAX_GSL_LENGTH_M}\n")
    f.write(f"max_isl_length_m=5016591.2330984278\n")   # giá trị bạn có

# 6. Generate Dynamic State (phần tốn thời gian nhất)
satgen.generate_dynamic_state(
    OUTPUT_DIR,
    0,                                           # start_time_ns
    SIMULATION_END_TIME_S * 1000 * 1000 * 1000, # end_time_ns
    DYNAMIC_STATE_UPDATE_INTERVAL_MS * 1000 * 1000,  # interval_ns
    MAX_GSL_LENGTH_M,
    ISL_MAX_QUEUE_SIZE_PKTS,
    "shortest_path",                             # routing algorithm
    False                                        # verbose
)

print("Hoàn thành! Output ở thư mục:", OUTPUT_DIR)
