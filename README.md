# 🚖 NYC Taxi Real-Time Streaming Pipeline

> **End-to-End Real-Time Data Engineering & Mission Control Platform** mô phỏng, xử lý luồng sự kiện tốc độ cao (**400+ events/giây**) và giám sát trực quan 3D hơn **500 xe taxi (Yellow, Green, FHVHV / Uber & Lyft)** hoạt động đồng thời trên **265 Taxi Zones** tại New York City.

---

## 🏛️ Kiến Trúc Hệ Thống (Architecture Overview)

Hệ thống được thiết kế theo mô hình **6 Tầng Microservices** chạy độc lập trên Docker Network, truyền dữ liệu thời gian thực từ Parquet raw data đến WebGL 3D Dashboard:

```text
┌─────────────────┐       ┌─────────────────┐       ┌────────────────────┐
│    Simulator    │──────►│  Apache Kafka   │──────►│  Flink Processor   │
│ (Parquet Replay │       │  (KRaft Mode    │       │ (Sliding Window 60s│
│  400 events/s)  │       │  6 Partitions)  │       │  Congestion Engine)│
└─────────────────┘       └─────────────────┘       └────────────────────┘
                                                               │
                                                               ▼
┌─────────────────┐       ┌─────────────────┐       ┌────────────────────┐
│ Web Dashboard   │◄──────│   API Gateway   │◄──────│     Redis 7.2      │
│ (React + Deck.gl│  WSS  │ (FastAPI + WSS  │ Cache │  (In-Memory State  │
│  ECharts 60 FPS)│       │  Fan-out Engine)│  Poll │   & Pub/Sub Store) │
└─────────────────┘       └─────────────────┘       └────────────────────┘
```

1. **Simulator & Ingestion (`simulator/`)**: Đọc song song dữ liệu Parquet thực tế từ NYC TLC (Yellow, Green, FHVHV) hoặc tự động nội suy tọa độ bám sát mạng lưới đường bộ OSRM, sản sinh luồng **400 sự kiện/giây** (`aiokafka` Async Producer).
2. **Message Broker (`kafka/`)**: Apache Kafka 3.8.0 vận hành ở chế độ **KRaft** (không cần Zookeeper), topic `taxi.trips.live` với 6 partitions, nén `gzip` và cơ chế retention thông minh chống tràn disk.
3. **Stream Processing Engine (`flink_processor/`)**: Duy trì **Sliding Time Window 60s**, phân loại mức độ tắc nghẽn 265 zones, tính toán thị phần kiểm soát (`compute_zone_dominance`), doanh thu in-flight và dọn dẹp xe stale.
4. **In-Memory State & Pub/Sub Store (`redis/`)**: Redis 7.2 Alpine lưu trữ snapshot mật độ (`kv:latest_density_metrics`), dữ liệu tranh chấp thị phần (`kv:power_map_snapshot` TTL 10s), và bộ đếm KPI vận hành (`hash:realtime_kpis`).
5. **Real-Time API Gateway (`api_gateway/`)**: FastAPI + Uvicorn đảm nhiệm broadcast WebSockets tần số cao (`/ws/fleet`, `/ws/kpis`) đến các Web client, kiêm proxy dẫn đường OSRM (`/api/route`).
6. **Mission Control Web SPA (`web_dashboard/`)**: Single Page Application xây dựng trên React 18, Vite, Deck.gl 9.0 (WebGL 3D 60 FPS), Apache ECharts 5.5, Zustand và phong cách thiết kế **Dark Cyberpunk / NASA Mission Control**.

---

## 🛠️ Tech Stack & Công Nghệ

| Tầng kiến trúc | Công nghệ / Thư viện | Vai trò kỹ thuật trong hệ thống |
|----------------|----------------------|-----------------------------------|
| **Event Producer** | Python 3.11, AsyncIO, `aiokafka`, PyArrow | Đọc file Parquet 19 cột canonical, mô phỏng lộ trình xe 400 events/giây |
| **Message Broker** | Apache Kafka 3.8.0 (KRaft Mode) | Đệm luồng phân tán chịu lỗi cao trên 6 partitions |
| **Stream Processor** | Python 3.11, Sliding Window Engine | Phân tích cửa sổ trượt 60s, phát hiện điểm nóng và tỷ trọng chiếm lĩnh |
| **In-Memory Store** | Redis 7.2 Alpine | Bộ đếm KPI nguyên tử, lưu trữ snapshot toàn bộ 265 zones & Pub/Sub channel |
| **API Gateway** | FastAPI, Uvicorn, WebSockets, HTTPX | WebSocket fan-out phục vụ đồng thời nhiều client, OSRM routing proxy |
| **Frontend Framework** | React 18, TypeScript, Vite | Nền tảng SPA tối ưu render với thời gian build siêu tốc |
| **3D Geospatial Engine** | Deck.gl 9.0, MapLibre GL | Hiển thị 500+ xe 3D GPU-accelerated 60 FPS, Heatmap, Arc & Radar Layers |
| **Analytics & Charts** | Apache ECharts 5.5, `echarts-for-react` | Biểu đồ sóng Telemetry, Boxplot, Radar Spider và Matrix Heatmap |
| **State Management** | Zustand 4.5 | Quản lý state luồng dữ liệu thời gian thực không gây giật lag |
| **Routing Engine** | OSRM Driving Engine API | Tìm đường phố thực tế bám sát mạng lưới giao thông New York City |
| **Styling & UI Tokens** | Vanilla CSS + Cyberpunk Glassmorphism | Thiết kế tuân thủ tiêu chuẩn [DESIGN.md](file:///run/media/pch1101/PCH/Build/DE/taxi_real_time/DESIGN.md) với font JetBrains Mono & Plus Jakarta Sans |
| **Containerization** | Docker & Docker Compose v2 | Đóng gói toàn bộ 6 dịch vụ microservices độc lập |

---

## 🚀 Khởi Chạy Nhanh (Quick Start)

### 1. Yêu cầu hệ thống
- **Docker Engine** 24.0+ và **Docker Compose** v2 trở lên.
- RAM trống tối thiểu: **4 GB** (khuyến nghị 8 GB để vận hành trơn tru cả Kafka và Flink).

### 2. Khởi động toàn bộ cụm dịch vụ
```bash
# Di chuyển vào thư mục dự án
cd taxi_real_time

# Khởi chạy tất cả containers ở chế độ nền
docker compose up -d --build
```

### 3. Cổng truy cập dịch vụ
| Dịch vụ | Địa chỉ URL / Port | Mô tả |
|---------|---------------------|-------|
| 🌐 **Mission Control Web SPA** | [http://localhost:3000](http://localhost:3000) | Giao diện điều hành thời gian thực React + Deck.gl 3D |
| ⚡ **API Gateway (Swagger UI)** | [http://localhost:8080/docs](http://localhost:8080/docs) | REST API Docs, kiểm tra trạng thái WebSocket `/ws/fleet` |
| 📡 **Kafka Broker External** | `localhost:19092` | Cổng kết nối Kafka cho client ngoài máy host |
| 🔴 **Redis Server** | `localhost:6379` | Truy vấn Redis CLI / Key-Value Store |

---

## 🎮 Khám Phá Dashboard (3 Không Gian Tác Chiến)

Giao diện điều hành được chia thành 3 màn hình chuyên biệt qua thanh điều hướng `TabNav`:

### 1. 🗺️ Tab 1: 3D Fleet Command Map
- **3D Deck.gl Engine (60 FPS):** Hiển thị trực quan 500+ xe đang lăn bánh với màu sắc đặc trưng:
  - 🟡 **Yellow Cab** (`#FACC15`)
  - 🟢 **Green Boro Taxi** (`#22C55E`)
  - 🟣 **FHVHV / Uber & Lyft** (`#A855F7`)
- **Tùy biến hiển thị màu xe:** Chuyển đổi linh hoạt giữa *Loại xe (Taxi Type)*, *Dải tốc độ (Speed MPH)*, *Cước phí (Fare)* hoặc *Hiệu suất (Efficiency)*.
- **Layers tương tác cao:** Bật/tắt linh hoạt *Bản đồ nhiệt đón khách (Demand Heatmap)*, *Radar phát sáng vùng đông nhất (#1 Busiest Zone)*, và *3 Sân bay quốc tế (JFK, LGA, EWR)*.
- **Interactive Driver Focus HUD:** Nhấp chọn bất kỳ xe nào để mở HUD chi tiết: vẽ lộ trình thực tế qua OSRM (nhánh đã đi màu Neon Cyan, nhánh sắp tới màu Crimson), tự động tính **Độ trễ & Điểm tối ưu lộ trình (Route Detour Score)**.

### 2. 📈 Tab 2: Live Stream Telemetry & Trends
- **4 Thẻ KPI Thời Gian Thực:**
  - *Active Fleet Deployed* (Số xe thực tế đang di chuyển)
  - *Ingestion Throughput* (Nhịp nạp sự kiện vi mô Kafka/Flink)
  - *In-Flight Fare Revenue* (Tổng doanh thu các cuốc xe đang chạy trên đường)
  - *Fleet Average Speed* (Vận tốc trung bình và cảnh báo tắc nghẽn)
- **Hàng 3 Biểu Đồ Phân Tích Cân Bằng (Height 260px đồng bộ):**
  1. **Top Congested Pickup Hubs (Hotspots Bar Chart):** Xếp hạng 8 điểm nóng tập trung lượng xe đón trả khách đông nhất.
  2. **Streaming Throughput & Velocity:** Biểu đồ sóng kép với trục Y tự động co giãn (`scale: true`). Hiển thị nhịp thở xử lý `ops/s` và vận tốc `MPH`, kèm nút chuyển đổi tức thì sang chế độ phân bổ **Borough Load**.
  3. **Fare Value Distribution ($ USD):** Biểu đồ Histogram liên tục kết hợp đường mật độ phân phối cước phí, hỗ trợ chuyển đổi *Histogram* và *Density*.
- **Micro-Batch Live Trip Feed:** Bảng cập nhật dữ liệu vi mô thời gian thực với tính năng **Click-to-Inspect** — nhấp vào bất kỳ dòng nào để camera 3D lập tức bay tới định vị xe trên bản đồ.

### 3. 📊 Tab 3: Fleet Analytics & Deep Intelligence
- **3-Fleet Scoreboard:** Bảng điểm so sánh trực diện thị phần, doanh thu trung bình, vận tốc và tỷ lệ cuốc xe giữa Yellow, Green và FHVHV.
- **Borough Transition Matrix Heatmap:** Ma trận nhiệt trực quan hóa các luồng dịch chuyển đón - trả khách giữa 5 quận (Manhattan, Queens, Brooklyn, Bronx, Staten Island).
- **5-Axis Fleet Performance Radar:** Biểu đồ mạng nhện so sánh toàn diện 5 chỉ số: Tốc độ trung bình, Cước bình quân, Mật độ phủ sóng, Điểm đón sân bay, và Doanh thu trên dặm.
- **Fare Outlier Box Plot & Trip Bubble Scatter:** Phân tích độ lệch chuẩn cước phí và mối tương quan giữa Quãng đường - Thời gian - Cước phí.

---

## ⚙️ Cấu Hình Môi Trường (Environment Variables)

Các tham số cấu hình chính được quản lý tập trung trong file [`docker-compose.yml`](file:///run/media/pch1101/PCH/Build/DE/taxi_real_time/docker-compose.yml):

| Biến môi trường | Dịch vụ | Giá trị khuyến nghị | Ý nghĩa vận hành |
|-----------------|---------|----------------------|------------------|
| `SOURCE_MODE` | `simulator` | `PARQUET_REPLAY` | Chế độ phát dữ liệu (`PARQUET_REPLAY` hoặc `SYNTHETIC_STREAM`) |
| `ENABLED_DATASETS` | `simulator` | `YELLOW,GREEN,FHVHV` | Kích hoạt cả 3 dòng xe truyền thống và công nghệ |
| `EVENTS_PER_SECOND` | `simulator` | `400.0` | Tốc độ phát luồng sự kiện vi mô mục tiêu |
| `BATCH_SIZE` | `simulator` | `100` | Số lượng sự kiện đóng gói trong một micro-batch |
| `MAX_CONCURRENT_TRIPS` | `simulator` | `400` | Số lượng cuốc xe hoạt động đồng thời trên bản đồ |
| `SLIDING_WINDOW_SECONDS` | `flink-processor` | `60` | Khung thời gian cửa sổ trượt phân tích mật độ xe |
| `DENSITY_PUBLISH_INTERVAL`| `flink-processor` | `2.0` | Chu kỳ tổng hợp và cập nhật snapshot xuống Redis (giây) |
| `REDIS_URL` | `api-gateway`, `flink` | `redis://redis:6379/0` | Chuỗi kết nối mạng nội bộ đến Redis State Store |

---

## 🛠️ Lệnh Vận Hành & Gỡ Lỗi Thường Dùng

```bash
# 1. Kiểm tra trạng thái hoạt động của toàn bộ cụm 6 containers
docker compose ps

# 2. Theo dõi logs trực tiếp của từng microservice
docker compose logs -f simulator           # Logs phát sự kiện Kafka
docker compose logs -f flink-processor     # Logs xử lý cửa sổ trượt Flink
docker compose logs -f api-gateway         # Logs WebSocket & REST API
docker compose logs -f web-dashboard       # Logs Nginx Web Server

# 3. Chạy thử nghiệm Simulator ở chế độ Dry-Run độc lập (không cần Docker)
python simulator/main.py --dry-run -n 50

# 4. Rebuild và cập nhật nhanh Web Dashboard khi sửa đổi code giao diện
docker compose build web-dashboard && docker compose up -d --no-deps web-dashboard

# 5. Dừng và giải phóng tài nguyên hệ thống
docker compose down
```

---

## 📁 Cấu Trúc Thư Mục Dự Án (Repository Structure)

```text
taxi_real_time/
├── data/                         # Dữ liệu 265 Taxi Zones & file Parquet TLC tháng 04/2026
│   ├── DATA_DISCOVERY.md         # Báo cáo khám phá dữ liệu Parquet chi tiết
│   ├── fhvhv_tripdata_2026-04.parquet  (486 MB - High Volume FHV Uber/Lyft)
│   ├── green_tripdata_2026-04.parquet  (1.03 MB - Green Boro Taxi)
│   ├── yellow_tripdata_2026-04.parquet (61.8 MB - Yellow Cabs)
│   └── taxi_zones.json           # Metadata 265 Taxi Zones (tọa độ, quận, tên vùng)
├── simulator/                    # Trình sinh luồng sự kiện vi mô & Kafka Producer
│   ├── generator/                # Module nội suy lộ trình xe & tọa độ OSRM
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
├── api_gateway/                  # FastAPI Gateway & WebSocket Server
│   ├── routers/                  # Router điều hướng (routes, metrics, websockets)
│   ├── services/                 # Redis async subscriber & OSRM client
│   ├── main.py                   # Điểm khởi chạy FastAPI & fan-out engine
│   ├── requirements.txt
│   └── Dockerfile
├── web_dashboard/                # Giao diện Mission Control Web SPA (React + Deck.gl + ECharts)
│   ├── src/
│   │   ├── components/
│   │   │   ├── analytics/        # Scoreboard, Heatmap, Radar, Boxplot, Scatter
│   │   │   ├── layout/           # TopBar, TabNav, Sidebar
│   │   │   ├── map/              # Deck.gl 3D FleetMap & Layers
│   │   │   ├── telemetry/        # KpiCards, ZoneConcentration, ThroughputVelocityChart, FareHistogram
│   │   │   └── views/            # TelemetryTab, AnalyticsTab
│   │   ├── hooks/                # WebSocket hooks: useFleetWS, useKpiWS
│   │   ├── store/                # Zustand store (useFleetStore)
│   │   ├── lib/                  # Type definitions & Deck.gl layers helper
│   │   └── App.tsx
│   ├── nginx.conf                # Nginx reverse proxy & static file serving
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml            # Khởi tạo Kafka (KRaft), Redis, Simulator, Flink, API & Web SPA
├── DATA_FLOW.md                  # Tài liệu đặc tả luồng dữ liệu chuyên sâu (Data Contract & Schemas)
├── DESIGN.md                     # Đặc tả hệ thống thiết kế Dark Cyberpunk & Design Tokens
└── README.md                     # Tài liệu hướng dẫn sử dụng và tổng quan dự án
```

---

## 📖 Tài Liệu Tham Khảo Thêm
- **Đặc tả luồng dữ liệu & Data Contracts:** 👉 [DATA_FLOW.md](file:///run/media/pch1101/PCH/Build/DE/taxi_real_time/DATA_FLOW.md)
- **Hệ thống Design Tokens & Cyberpunk Theme:** 👉 [DESIGN.md](file:///run/media/pch1101/PCH/Build/DE/taxi_real_time/DESIGN.md)
- **Báo cáo khám phá dữ liệu Parquet:** 👉 [data/DATA_DISCOVERY.md](file:///run/media/pch1101/PCH/Build/DE/taxi_real_time/data/DATA_DISCOVERY.md)
- **Nguồn dữ liệu chính thức:** [NYC Taxi and Limousine Commission (TLC)](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
