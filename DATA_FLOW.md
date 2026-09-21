# 🌊 Kiến Trúc Luồng Dữ Liệu — NYC Taxi Real-Time Pipeline

> **Tài liệu đặc tả kiến trúc luồng dữ liệu thời gian thực (End-to-End Data Pipeline Architecture)**  
> Mô phỏng, xử lý luồng và trực quan hóa hơn 500 xe taxi di chuyển đồng thời trên 265 Taxi Zones tại New York City.

---

## 🏛️ Sơ Đồ Kiến Trúc Luồng Tổng Thể (End-to-End Architecture)

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                TẦNG 1: INGESTION & SIMULATOR                           │
│  ┌────────────────────────┐        ┌────────────────────────┐                          │
│  │ TLC Parquet Replay     │        │ Synthetic Generator    │                          │
│  │ (Yellow, Green, FHVHV) │        │ (Zone-weighted Spawner)│                          │
│  └───────────┬────────────┘        └───────────┬────────────┘                          │
│              └─────────────────┬───────────────┘                                       │
│                                ▼                                                       │
│                 [ asyncio.Queue (Buffer: 2000) ]                                       │
│                                │                                                       │
│                 [ AIOKafkaProducer (Batch: 50) ]                                       │
└────────────────────────────────┼───────────────────────────────────────────────────────┘
                                 │ JSON Telemetry Stream (50–100+ events/sec)
                                 ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                           TẦNG 2: MESSAGE BROKER (APACHE KAFKA)                        │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │ Topic: taxi.trips.live  |  6 Partitions  |  KRaft Mode (3.8.0)  |  Retention: 1h  │  │
│  └──────────────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────┼───────────────────────────────────────────────────────┘
                                 │ Consumer Group: taxi-flink-group-<ts> (auto_offset=latest)
                                 ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        TẦNG 3: STREAM PROCESSING ENGINE (APACHE FLINK)                 │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │ FlinkStreamEngine (Python Streaming Processor)                                   │  │
│  │  ├── In-Memory Sliding Window (60s State Window, Stale Eviction)                 │  │
│  │  ├── Zone Congestion Classifier (265 Zones: LOW / MODERATE / HEAVY / CRITICAL)   │  │
│  │  ├── Fleet Power & Dominance Engine (Territory Ratios & Battleground Status)     │  │
│  │  └── Snapshot Aggregator (Micro-batch Trigger: 2.0s Interval)                    │  │
│  └──────────────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────┼───────────────────────────────────────────────────────┘
                                 │ Redis Pipeline Write (SET / PUBLISH / HSET)
                                 ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        TẦNG 4: IN-MEMORY STATE & PUB/SUB STORE (REDIS 7.2)             │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │  • kv:latest_density_metrics   → JSON Snapshot 265 zones + active vehicles list  │  │
│  │  • kv:power_map_snapshot       → Territory dominance & invasion zones (TTL 10s)  │  │
│  │  • hash:realtime_kpis          → Operational counters & engine metadata           │  │
│  │  • channel:density_metrics     → Pub/Sub real-time broadcast channel              │  │
│  └──────────────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────┼───────────────────────────────────────────────────────┘
                                 │ Polling Query / In-Memory Cache (1–2s Interval)
                                 ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                      TẦNG 5: LIVE OPERATIONS DASHBOARD (STREAMLIT + PYDECK)            │
│  ┌─────────────────────────┬──────────────────────────┬─────────────────────────────┐  │
│  │ Tab 1: 3D Fleet Map     │ Tab 2: Stream Telemetry  │ Tab 3: Fleet Power Map      │  │
│  │ • PyDeck 3D Pin Layers  │ • Ingestion Pulse Chart  │ • Territory Control Bar     │  │
│  │ • Pickup Demand Heatmap │ • Top Hotspots Ranking   │ • Dominance Bubble Map      │  │
│  │ • Busiest / Hub Radars  │ • Borough Donut Share    │ • Contested Battlegrounds   │  │
│  │ • OSRM Street Router    │ • Revenue Velocity Area  │ • Live Invasion Alert Feed  │  │
│  │ • Focus Driver HUD      │ • Micro-Batch Event Feed │                             │  │
│  └─────────────────────────┴──────────────────────────┴─────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Chi Tiết 5 Tầng Xử Lý (5-Stage Pipeline Details)

### 📌 TẦNG 1 — Simulator & Data Ingestion
- **Mã nguồn:** [`simulator/main.py`](file:///run/media/pch1101/PCH/Build/DE/taxi_real_time/simulator/main.py) · [`simulator/generator/`](file:///run/media/pch1101/PCH/Build/DE/taxi_real_time/simulator/generator) · [`simulator/loaders/`](file:///run/media/pch1101/PCH/Build/DE/taxi_real_time/simulator/loaders) · [`simulator/models/`](file:///run/media/pch1101/PCH/Build/DE/taxi_real_time/simulator/models) · [`simulator/producer/`](file:///run/media/pch1101/PCH/Build/DE/taxi_real_time/simulator/producer) · [`simulator/zones/`](file:///run/media/pch1101/PCH/Build/DE/taxi_real_time/simulator/zones)
- **Đặc điểm vận hành**:
  1. **Hỗ trợ 3 phân lớp Taxi NYC TLC**:
     - 🟡 **Yellow Taxi (`YELLOW`)**: Taxi truyền thống tập trung tại Manhattan & sân bay (ID: `yt-*`). Trọng số mặc định: **40%**.
     - 🟢 **Green Taxi (`GREEN`)**: Boro Taxi phục vụ Outer Boroughs & Upper Manhattan (ID: `gt-*`). Trọng số mặc định: **10%**.
     - 🟣 **FHVHV (`FHVHV`)**: High-Volume For-Hire Vehicles (Uber / Lyft) phủ khắp 5 quận (ID: `hv-*`). Trọng số mặc định: **50%**.
  2. **2 Cơ chế nạp dữ liệu (`SOURCE_MODE`)**:
     - `PARQUET_REPLAY`: Nạp trực tiếp từ file Parquet tháng 04/2026 với 19 cột canonical chuẩn TLC (`yellow_tripdata_2026-04.parquet`, `green_tripdata_2026-04.parquet`, `fhvhv_tripdata_2026-04.parquet`).
     - `SYNTHETIC_STREAM`: Sinh hành trình ngẫu nhiên dựa trên trọng số phân bố 265 Taxi Zones và mô hình toán học vận tốc theo giờ.
  3. **Kiến trúc Producer bất đồng bộ (Dual-Task Async Architecture)**:
     - **Task A (`_event_generator`)**: Khởi tạo chuyến xe mới hoặc tính toán bước nhảy tọa độ (interpolation) cho xe đang chạy, đẩy vào `asyncio.Queue` (buffer max 2000).
     - **Task B (`_batch_sender`)**: Hút dữ liệu từ hàng đợi theo lô (`BATCH_SIZE=50`) và gửi fire-and-forget qua `aiokafka.AIOKafkaProducer`.
  4. **Vòng đời sự kiện (3-State Lifecycle)**:
     $$\text{TRIP\_STARTED (progress=0.0)} \longrightarrow \text{LOCATION\_PING (0.0 < progress < 1.0)} \longrightarrow \text{TRIP\_COMPLETED (progress=1.0)}$$

---

### 📌 TẦNG 2 — Message Broker (Apache Kafka KRaft)
- **Image:** `apache/kafka:3.8.0` (KRaft mode — không cần cụm Zookeeper riêng biệt).
- **Topic chính:** `taxi.trips.live`
- **Thông số cấu hình tối ưu:**
  - **Partitions:** `6` (đảm bảo khả năng scale song song nhiều consumer instances).
  - **Replication Factor:** `1` (môi trường single-node container).
  - **Log Retention:** `3600000 ms` (1 giờ) / `512 MB` (ngăn tràn bộ nhớ đệm ổ cứng).
  - **Compression:** `gzip` (giảm tải băng thông truyền mạng).
  - **Init Hook:** Container `taxi-realtime-kafka-init` tự động kiểm tra broker sẵn sàng và khởi tạo topic với partition/retention tương ứng.

---

### 📌 TẦNG 3 — Stream Processing Engine (Apache Flink / Streaming Job)
- **Mã nguồn:** [`flink_processor/flink_streaming_job.py`](file:///run/media/pch1101/PCH/Build/DE/taxi_real_time/flink_processor/flink_streaming_job.py) · [`flink_processor/config.py`](file:///run/media/pch1101/PCH/Build/DE/taxi_real_time/flink_processor/config.py)
- **Các thành phần xử lý trọng tâm**:
  1. **Sliding Time Window (60s State Window)**:
     - Duy trì trạng thái vị trí, tốc độ, cước phí, tọa độ xuất phát/đích của từng `trip_id`.
     - Cơ chế **Stale Eviction**: Tự động dọn dẹp các xe không có ping mới vượt quá `SLIDING_WINDOW_SECONDS` (60s) hoặc nhận event `DROP_OFF` / `progress_ratio >= 1.0`.
  2. **Zone Density & Congestion Classifier (265 Zones)**:
     - Phân loại mật độ ùn tắc thời gian thực trên từng Zone theo 4 cấp bậc:
       - 🟢 `LOW`: $< 3$ xe
       - 🟡 `MODERATE`: $3 \le \text{xe} \le 6$
       - 🟠 `HEAVY`: $7 \le \text{xe} \le 11$
       - 🔴 `CRITICAL_CONGESTION`: $\ge 12$ xe
  3. **Fleet Territory Dominance & Power Map Algorithm**:
     - Hàm `compute_zone_dominance()` phân tích tỷ trọng số lượng xe của 3 đội tại từng Zone:
       - `dominant_fleet`: Đội xe chiếm số lượng cao nhất trong zone.
       - `dominance_ratio`: Tỷ lệ chiếm hữu ($\frac{\text{Count}_{\text{dom}}}{\text{Total}}$).
       - `battle_status`:
         - `EMPTY`: 0 xe trong zone.
         - `DOMINATED`: Đội dẫn đầu nắm giữ $\ge 50\%$ hoặc có khoảng cách áp đảo.
         - `CONTESTED`: Top 2 đội xe chênh lệch $\le 1$ xe hoặc khoảng cách thị phần $< 20\%$.
         - `BALANCED`: Phân bổ đồng đều giữa các đội xe.
  4. **Micro-batch Redis Sink Trigger**:
     - Định kỳ mỗi `DENSITY_PUBLISH_INTERVAL` (2.0s), engine tính toán toàn bộ snapshot và đẩy đồng bộ xuống Redis bằng `Pipeline`.

---

### 📌 TẦNG 4 — In-Memory State & Pub/Sub Store (Redis 7.2)
- **Image:** `redis:7.2-alpine` (Cổng `6379`).
- **Data Contract & Key Structure**:

| Redis Key / Channel | Kiểu dữ liệu | TTL | Nội dung mô tả |
|---------------------|--------------|-----|----------------|
| `kv:latest_density_metrics` | String (JSON) | Không | Snapshot toàn bộ 265 zones, danh sách xe active (tọa độ, tốc độ, tiến trình), phân bố quận huyện và 3 đội xe. |
| `kv:power_map_snapshot` | String (JSON) | **10s** | Danh sách các zone tranh chấp (`invasion_zones`) và số lượng zone mỗi đội xe nắm quyền (`territory_counts`). Tự hủy nếu pipeline ngừng hoạt động. |
| `hash:realtime_kpis` | Hash | Không | Bộ đếm KPI vận hành: `total_active_vehicles`, `total_events_processed`, `last_density_update`, `engine`. |
| `channel:density_metrics` | Pub/Sub Channel | N/A | Kênh broadcast snapshot theo chu kỳ 2s cho các client lắng nghe trực tiếp. |

---

### 📌 TẦNG 5 — Live Operations Dashboard (Streamlit & PyDeck 3D)
- **Mã nguồn:** [`dashboard/app.py`](file:///run/media/pch1101/PCH/Build/DE/taxi_real_time/dashboard/app.py) · [`dashboard/data_loader.py`](file:///run/media/pch1101/PCH/Build/DE/taxi_real_time/dashboard/data_loader.py) · [`dashboard/config.py`](file:///run/media/pch1101/PCH/Build/DE/taxi_real_time/dashboard/config.py)
- **Giao diện Cyberpunk Dark Enterprise với 3 Không Gian Tác Chiến**:

```text
┌────────────────────────────────────────────────────────────────────────────────┐
│  🚕 NYC REAL-TIME TAXI TELEMETRY COMMAND CENTER                                │
│  [ Active Fleet: 500 ] [ In-Flight Fare: $8,450 ] [ Ingested: 120,400 evts ]   │
├────────────────────────────────────────────────────────────────────────────────┤
│  [ Tab 1: 🗺️ 3D Fleet Command Map ]                                            │
│  • PyDeck 3D Scatterplot Pin Layer (Màu sắc chuẩn TLC / Dải màu tốc độ)        │
│  • Hexagon & Heatmap Layer (Mật độ đón khách với thanh trượt radius/intensity) │
│  • Radar Beacons (Phát xung neon tại #1 Busiest Zone & 3 Sân bay JFK/LGA/EWR)  │
│  • OSRM Street Router: Vẽ tuyến đường đi thực tế qua mạng lưới phố NYC         │
│  • Driver Focus HUD & Detour Efficiency Score (OPTIMAL / MODERATE / HIGH)      │
│  • Paginated Fleet Dispatch Drawer (6 xe/trang, tra cứu theo ID/Borough)       │
├────────────────────────────────────────────────────────────────────────────────┤
│  [ Tab 2: 📈 Live Stream Telemetry & Trends ]                                  │
│  • 4 Khối biểu đồ Plotly Dark:                                                 │
│    1. Ingestion Velocity Spline (Events/sec theo thời gian thực)               │
│    2. Top 8 Pickup Hotspots Bar Chart (Điểm đón xe nhộn nhịp nhất)             │
│    3. Borough Market Share Donut Chart (Tỷ trọng phân bổ 5 quận)               │
│    4. Revenue Velocity Area Chart ($/sec dòng tiền cước và phụ phí)            │
│  • Live Micro-Batch Stream Feed (Bảng chi tiết gắn nhãn động telemetry)        │
├────────────────────────────────────────────────────────────────────────────────┤
│  [ Tab 3: ⚔️ Fleet Power Map ]                                                 │
│  • Territory Dominance Bar (% số Zone mỗi đội Yellow/Green/FHVHV thống trị)    │
│  • PyDeck 3D Dominance Bubble Map (Bán kính tỉ lệ với số xe, màu theo đội)     │
│  • Radar phát xung cảnh báo tại các khu vực tranh chấp (Contested Zones)       │
│  • Battleground Hotspots Table & Live Invasion Feed                            │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📋 Đặc Tả Schema Dữ Liệu Sự Kiện (Canonical Event Schema)

Mỗi thông điệp truyền trên topic Kafka `taxi.trips.live` tuân thủ nghiêm ngặt Pydantic Model [`TripEvent`](file:///run/media/pch1101/PCH/Build/DE/taxi_real_time/simulator/models/trip_event.py):

```json
{
  "trip_id": "yt-202604-000142",
  "dataset_source": "YELLOW",
  "event_type": "LOCATION_PING",
  "pickup_datetime": "2026-04-12T14:30:00",
  "dropoff_datetime": "2026-04-12T14:48:00",
  "PULocationID": 237,
  "DOLocationID": 161,
  "pickup_zone_name": "Upper East Side South",
  "pickup_borough": "Manhattan",
  "dropoff_zone_name": "Midtown Center",
  "dropoff_borough": "Manhattan",
  "current_lat": 40.7682,
  "current_lng": -73.9621,
  "passenger_count": 1,
  "trip_distance": 2.45,
  "total_amount": 16.50,
  "progress_ratio": 0.42,
  "timestamp": 1776004245.12,
  "datetime_utc": "2026-04-12T18:30:45.120000+00:00"
}
```

---

## ⚡ Chỉ Số Hiệu Năng & Độ Trễ (Performance Benchmarks)

| Hạng mục | Thông số cam kết | Cơ chế kỹ thuật đảm bảo |
|----------|-------------------|--------------------------|
| **Tốc độ sinh sự kiện (Simulator)** | $50 - 100+$ events/sec | `asyncio.Queue` + `aiokafka` Fire-and-forget Batching |
| **Độ trễ truyền Kafka (Broker Latency)** | $< 5\text{ ms}$ | Kafka 3.8.0 KRaft mode nội bộ Docker Network |
| **Chu kỳ xử lý Stream (Flink Window)** | $2.0\text{ s}$ Tick | Sliding Memory Window $60\text{s}$ + Redis Pipeline Write |
| **Độ trễ cập nhật Dashboard (UI Refresh)** | $1 - 2\text{ s}$ | `st_autorefresh` + In-memory Redis Cache Query |
| **Thời gian dọn dẹp trạng thái Stale** | $60\text{ s}$ timeout / $10\text{ s}$ TTL | Tự động loại bỏ xe mất tín hiệu và snapshot hết hạn |
