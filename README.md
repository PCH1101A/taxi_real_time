# 🚖 NYC Taxi Real-Time Streaming Pipeline

> **End-to-End Real-Time Data Engineering Pipeline** mô phỏng, xử lý luồng sự kiện tốc độ cao và giám sát trực quan hơn **500 xe taxi (Yellow, Green, FHVHV/Uber/Lyft)** hoạt động đồng thời trên **265 Taxi Zones** tại New York City.

---

## 🏛️ Kiến Trúc Hệ Thống (Architecture Overview)

```text
┌─────────────────┐       ┌─────────────────┐       ┌────────────────────┐       ┌────────────────┐       ┌──────────────────────┐
│    Simulator    │──────►│  Apache Kafka   │──────►│  Stream Processor  │──────►│   Redis 7.2    │──────►│ Streamlit Dashboard  │
│ (Parquet/Synth) │       │ (taxi.trips.live│       │  (Sliding Window / │       │ (State Store / │       │   (PyDeck 3D Map /   │
│                 │       │   6 Partitions) │       │ Dominance Analysis)│       │    PubSub)     │       │    Plotly Charts)    │
└─────────────────┘       └─────────────────┘       └────────────────────┘       └────────────────┘       └──────────────────────┘
```

1. **Simulator & Ingestion**: Phát lại dữ liệu thực tế từ NYC TLC Parquet (tháng 04/2026, 19 cột canonical) hoặc sinh dữ liệu ngẫu nhiên, sản sinh **50–100+ events/giây** đẩy vào Kafka qua kiến trúc Async Producer (`aiokafka`).
2. **Apache Kafka (KRaft)**: Message broker phân tán đệm luồng dữ liệu trên topic `taxi.trips.live` (6 partitions) với cơ chế nén `gzip` và retention tối ưu.
3. **Stream Processing Engine (Flink Job)**: Duy trì **Sliding Time Window 60s**, phân loại mức độ ùn tắc trên 265 zones, tính toán tỷ trọng chiếm lĩnh thị phần (`compute_zone_dominance`) và dọn dẹp xe stale.
4. **Redis In-Memory State Store**: Lưu snapshot trạng thái 265 zones (`kv:latest_density_metrics`), dữ liệu tranh chấp thị phần (`kv:power_map_snapshot` TTL 10s), và bộ đếm KPI (`hash:realtime_kpis`).
5. **Live Operations Dashboard**: Giao diện Streamlit Dark Cyberpunk tích hợp bản đồ 3D PyDeck tương tác, lộ trình đường phố thực tế OSRM, 4 biểu đồ Plotly thời gian thực, và phân tích quyền lực đội xe.

---

## 🛠️ Tech Stack & Công Nghệ

| Thành phần | Công nghệ / Phiên bản | Vai trò trong hệ thống |
|------------|------------------------|-------------------------|
| **Message Broker** | Apache Kafka 3.8.0 (KRaft) | Lưu đệm và phân phối luồng sự kiện vi mô tốc độ cao |
| **In-Memory Store** | Redis 7.2 Alpine | Lưu trữ state snapshot, Pub/Sub channel và bộ đếm KPI |
| **Streaming Engine** | Python 3.11 / AsyncIO / Flink Logic | Xử lý cửa sổ trượt 60s, phân loại tắc nghẽn và dominance ratio |
| **Producer & Ingestion** | AsyncIO + `aiokafka` + PyArrow | Đọc file Parquet 19 cột canonical và phát luồng sự kiện |
| **UI Dashboard** | Streamlit 1.38+ | Giao diện điều hành thời gian thực tự động làm mới |
| **3D Map Visualization** | PyDeck (Deck.gl) | Bản đồ 3D hiển thị vị trí xe, heatmap và radar neon |
| **Telemetry Analytics** | Plotly Express / Graph Objects | Biểu đồ sóng tốc độ nạp sự kiện, doanh thu và thị phần quận |
| **Routing Engine** | OSRM Driving API + Corridor Fallback | Dẫn đường bám sát mạng lưới đường bộ và cầu vượt NYC |
| **Containerization** | Docker & Docker Compose | Đóng gói và triển khai toàn bộ 5 dịch vụ chỉ với 1 lệnh |

---

## 🚀 Khởi Chạy Nhanh (Quick Start)

### 1. Yêu cầu môi trường
- Đã cài đặt **Docker** và **Docker Compose** (v2 trở lên).
- RAM trống tối thiểu: **4 GB** (khuyến nghị 8 GB).

### 2. Khởi chạy toàn bộ hệ thống
```bash
# Clone repository và di chuyển vào thư mục dự án
cd taxi_real_time

# Khởi chạy tất cả containers ở chế độ nền
docker compose up -d --build
```

### 3. Truy cập các cổng dịch vụ
- 🌐 **Live Operations Dashboard**: 👉 **[http://localhost:8501](http://localhost:8501)**
- ⚡ **Kafka External Port**: `localhost:19092` (cho kết nối bên ngoài máy host)
- 🔴 **Redis Server**: `localhost:6379`

---

## 🎮 Giao Diện Dashboard (3 Không Gian Tác Chiến)

Giao diện Dashboard tự động làm mới (`st_autorefresh` mỗi 1–2 giây) gồm 3 tabs chuyên sâu:

### 1. 🗺️ Tab 1: 3D Fleet Command Map
- **Bản đồ 3D PyDeck**: Hiển thị 500+ vị trí xe thời gian thực với màu chuẩn TLC (🟡 Yellow `#FACC15`, 🟢 Green `#22C55E`, 🟣 FHVHV `#A855F7`) hoặc theo dải tốc độ (Fluid / Normal / Congestion).
- **Pickup Demand Heatmap**: Bản đồ nhiệt mật độ đón khách tùy chỉnh bán kính và cường độ.
- **Radar Phát Sáng Neon**: Đánh dấu vùng đông xe nhất (#1 Busiest Zone) và 3 sân bay quốc tế (JFK, LGA, EWR).
- **Interactive Driver Focus HUD**: Tra cứu xe theo Trip ID/Borough, vẽ lộ trình thực tế qua **OSRM Driving Route Engine** (nhánh đã đi màu Cyan neon, nhánh sắp tới màu Crimson neon), tính điểm tối ưu quãng đường (**Route Efficiency & Detour Score**).

### 2. 📈 Tab 2: Live Stream Telemetry & Trends
- **4 Thẻ KPI Vận Hành**: Active Fleet, Doanh thu In-Flight ($), Tổng sự kiện nạp Kafka, Top Hotspot.
- **4 Biểu đồ phân tích thời gian thực (Plotly Dark)**:
  1. *Kafka Stream Ingestion Velocity*: Đo xung nhịp nạp sự kiện vi mô (Events / Sec).
  2. *Active Fleet Concentration*: Top 8 điểm đón xe đông nhất NYC.
  3. *Borough Market Share Distribution*: Biểu đồ Donut thị phần 5 quận (Manhattan, Brooklyn, Queens, Bronx, Staten Island).
  4. *Real-Time Revenue Velocity*: Biểu đồ diện tích kép đo tốc độ dòng tiền cước ($/sec).
- **Live Micro-Batch Stream Feed**: Bảng feed telemetry trực tiếp với các nhãn trạng thái động (`EXPRESS_SPEED`, `HEAVY_TRAFFIC`, `ARRIVING_SOON`, `CRUISING`).

### 3. ⚔️ Tab 3: Fleet Power Map
- **Territory Control Bar**: Tỷ lệ % số zone mà mỗi đội xe đang chiếm lĩnh.
- **PyDeck Dominance Map**: 265 Taxi Zones tô màu theo đội xe áp đảo, phát xung cảnh báo tại các khu vực tranh chấp (**Contested Zones**).
- **Live Invasion Feed & Battleground Hotspots**: Theo dõi chi tiết các điểm nóng cạnh tranh khốc liệt giữa Yellow Cab, Green Taxi và FHVHV (Uber/Lyft).

---

## ⚙️ Cấu Hình Môi Trường (Environment Variables)

Các biến môi trường chính được thiết lập trong [`docker-compose.yml`](file:///run/media/pch1101/PCH/Build/DE/taxi_real_time/docker-compose.yml) hoặc `.env`:

| Biến môi trường | Mặc định | Ý nghĩa |
|-----------------|----------|---------|
| `SOURCE_MODE` | `PARQUET_REPLAY` | Chế độ phát dữ liệu (`PARQUET_REPLAY` hoặc `SYNTHETIC_STREAM`) |
| `ENABLED_DATASETS` | `YELLOW,GREEN,FHVHV` | Danh sách 3 phân lớp xe được kích hoạt |
| `EVENTS_PER_SECOND` | `100.0` | Tốc độ sinh sự kiện tối đa của Simulator |
| `MAX_CONCURRENT_TRIPS` | `500` | Số lượng xe hoạt động đồng thời trên bản đồ |
| `SLIDING_WINDOW_SECONDS` | `60` | Thời gian cửa sổ trượt lưu trạng thái xe (giây) |
| `DENSITY_PUBLISH_INTERVAL` | `2.0` | Chu kỳ tổng hợp và ghi snapshot vào Redis (giây) |
| `REFRESH_INTERVAL_MS` | `2000` | Chu kỳ tự động làm mới của Dashboard Streamlit (mili-giây) |

---

## 🛠️ Lệnh Vận Hành & Gỡ Lỗi Thường Dùng

```bash
# 1. Kiểm tra trạng thái toàn bộ containers
docker compose ps

# 2. Xem logs thời gian thực của từng service
docker compose logs -f simulator
docker compose logs -f flink-processor
docker compose logs -f dashboard

# 3. Khởi chạy thử nghiệm Simulator ở chế độ Dry-Run (không cần Kafka/Docker)
python simulator/main.py --dry-run -n 50

# 4. Khởi động lại riêng Dashboard khi cập nhật mã nguồn
docker compose restart dashboard

# 5. Dừng và dọn dẹp hệ thống
docker compose down
```

---

## 📁 Cấu Trúc Thư Mục Dự Án

```text
taxi_real_time/
├── data/                         # Dữ liệu 265 Taxi Zones & file Parquet TLC tháng 04/2026
│   ├── DATA_DISCOVERY.md         # Báo cáo khám phá dữ liệu Parquet chi tiết
│   ├── fhvhv_tripdata_2026-04.parquet  (486 MB - High Volume FHV)
│   ├── green_tripdata_2026-04.parquet  (1.03 MB - Green Boro Taxi)
│   ├── yellow_tripdata_2026-04.parquet (61.8 MB - Yellow Cabs)
│   └── taxi_zones.json           # Metadata 265 Taxi Zones (tọa độ, quận, tên vùng)
├── simulator/                    # Trình sinh luồng dữ liệu & Kafka Producer
│   ├── generator/                # Module sinh lộ trình xe & tọa độ nội suy
│   ├── loaders/                  # Parquet loaders cho Yellow, Green, FHVHV
│   ├── models/                   # Pydantic schema TripEvent chuẩn hóa
│   ├── producer/                 # High-throughput async Kafka producer (aiokafka)
│   ├── zones/                    # Registry quản lý 265 Taxi Zones
│   ├── config.py                 # Cấu hình tham số Simulator
│   ├── main.py                   # Điểm khởi chạy Simulator (hỗ trợ --dry-run)
│   └── Dockerfile
├── flink_processor/              # Xử lý luồng, sliding window & phân tích thị phần
│   ├── config.py                 # Cấu hình Flink Job
│   ├── flink_streaming_job.py    # Sliding Window 60s, Zone Density & Redis Sink
│   └── Dockerfile
├── dashboard/                    # Giao diện điều hành trực quan Streamlit 3D
│   ├── app.py                    # Streamlit app (Tab 1 3D Map, Tab 2 Telemetry, Tab 3 Power Map)
│   ├── config.py                 # Cấu hình Dashboard
│   ├── data_loader.py            # Redis Client & Metadata loader
│   └── Dockerfile
├── docker-compose.yml            # Khởi tạo Kafka (KRaft), Redis, Simulator, Flink & Dashboard
├── DATA_FLOW.md                  # Tài liệu đặc tả kiến trúc luồng dữ liệu chuyên sâu
└── README.md                     # Tài liệu hướng dẫn sử dụng và tổng quan dự án
```

---

## 📖 Tài Liệu Tham Khảo Thêm
- Chi tiết kiến trúc luồng dữ liệu: 👉 [DATA_FLOW.md](file:///run/media/pch1101/PCH/Build/DE/taxi_real_time/DATA_FLOW.md)
- Báo cáo khám phá dữ liệu: 👉 [data/DATA_DISCOVERY.md](file:///run/media/pch1101/PCH/Build/DE/taxi_real_time/data/DATA_DISCOVERY.md)
- Nguồn dữ liệu chính thức: [NYC Taxi and Limousine Commission (TLC)](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
