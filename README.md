# 🚖 NYC Taxi Real-Time Streaming & Fleet Intelligence Operations Engine

Hệ thống xử lý luồng dữ liệu thời gian thực (**Real-Time Stream Processing & Telemetry Operations Engine**) quy mô lớn mô phỏng và giám sát toàn bộ hoạt động của đội xe **300+ đến 500+ taxi đang chạy đồng thời** (`MAX_CONCURRENT_TRIPS=350`/500) trên khắp New York City (265 Taxi Zones & 6 Boroughs). Hệ thống hỗ trợ đầy đủ **3 loại xe NYC TLC** (Yellow Cab, Green Boro Taxi, FHVHV Uber/Lyft), tích hợp thuật toán phân tích tranh chấp thị phần (**Gaussian Welford Online Z-Score & Fleet Power Map**), tính toán lộ trình đường phố thực tế (**OSRM Highway Routing**), và hiển thị trên **Live Cyberpunk Operations Dashboard 3D**.

---

## 🏛️ Kiến Trúc Hệ Thống (System Architecture)

```text
┌──────────────────────────────────────────────────────────────────────────────────┐
│  NYC TLC Taxi Data Ingestion & Live Simulator                                    │
│  ├── Quy mô: 300+ đến 500+ xe hoạt động liên tục (Concurrent In-Transit Fleet)   │
│  ├── 3 Loại xe TLC: 🟡 Yellow Taxi, 🟢 Green Boro Taxi, 🟣 FHVHV (Uber/Lyft)     │
│  ├── Mode 1: PARQUET_REPLAY (Phát lại dữ liệu thực tế TLC 19 canonical fields)   │
│  ├── Mode 2: SYNTHETIC_STREAM (Sinh luồng mô phỏng ngẫu nhiên trên 265 Zones)    │
│  └── Telemetry Generator (GPS Coordinates, Speed, Fare Rate, Progress)           │
└──────────────────────────────────────┬───────────────────────────────────────────┘
                                       │
                                       ▼ Topic: taxi.trips.live (3 Partitions)
┌──────────────────────────────────────────────────────────────────────────────────┐
│  Apache Kafka (KRaft Mode) (apache/kafka:3.8.0)                                  │
└──────────────────────────────────────┬───────────────────────────────────────────┘
                                       │
                                       ▼ Consumer Group: taxi-stream-processor-group
┌──────────────────────────────────────────────────────────────────────────────────┐
│  Apache Flink / Streaming Processor Engine                                       │
│  ├── 1. Sliding Window 60s trên 300+ xe active & 265 Taxi Zones                  │
│  ├── 2. Zone Density & Congestion Classifier (LOW, MODERATE, HEAVY, CRITICAL)    │
│  ├── 3. Fleet Power Map Engine (Gaussian Welford Online Dominance & Invasions)   │
│  └── 4. Periodic State Broadcaster (2s tick interval via Redis Pipeline)         │
└──────────────────────────────────────┬───────────────────────────────────────────┘
                                       │
                                       ▼ In-Memory State & Pub/Sub
┌──────────────────────────────────────────────────────────────────────────────────┐
│  Redis 7.2 In-Memory Data Store                                                  │
│  ├── Key-Value: `kv:latest_density_metrics`, `kv:power_map_snapshot` (TTL 10s)   │
│  ├── Hashes: `hash:realtime_kpis` (Events processed, Active fleet count)         │
│  └── Pub/Sub: `channel:density_metrics`                                          │
└──────────────────────────────────────┬───────────────────────────────────────────┘
                                       │
                                       ▼ Dynamic Polling (1-2s) & Real-time Visualizer
┌──────────────────────────────────────────────────────────────────────────────────┐
│  Streamlit Real-Time Fleet Operations Dashboard (Port 8501)                      │
│  ├── Tab 1: 🗺️ 3D Fleet Command Map (PyDeck 300+ Pins, OSRM Routing, Dispatch)   │
│  ├── Tab 2: 📈 Live Stream Telemetry & Trends (Kafka Waveforms, Fares, Donut)    │
│  └── Tab 3: ⚔️ Fleet Power Map (Territory Dominance, Welford Invasions Z > 2σ)   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack & Nhiệm Vụ Từng Công Nghệ

| Công nghệ | Phiên bản | Nhiệm vụ trong hệ thống |
|-----------|-----------|--------------------------|
| **Apache Kafka** | 3.8.0 (KRaft) | Message broker trung tâm. Nhận toàn bộ event từ Simulator, lưu đệm bền vững trong topic `taxi.trips.live` (3 partitions), đảm bảo không mất dữ liệu khi downstream chậm. Tách biệt hoàn toàn tốc độ produce (~20–100 event/s) và consume. |
| **Apache Flink / Stream Processor** | Custom Engine | Xử lý luồng dữ liệu thời gian thực: duy trì sliding window 60s, tổng hợp mật độ 265 zones, phân loại tắc nghẽn, tính toán Online Gaussian Welford dominance ratio và phát hiện xâm lấn thị phần (Invasion Alert). |
| **Redis** | 7.2-alpine | In-memory state store & pub/sub bus. Lưu snapshot density mới nhất (`kv:latest_density_metrics`), lưu snapshot bản đồ quyền lực (`kv:power_map_snapshot` với TTL 10s), bộ đếm KPI (`hash:realtime_kpis`), và phát tín hiệu qua `channel:density_metrics`. |
| **Python / AsyncIO** | 3.11+ | Runtime chính cho Simulator, Stream Processor và Data Loader. Sử dụng async/await và đa luồng để nạp dữ liệu mượt mà, không gây tắc nghẽn I/O. |
| **Streamlit** | latest | Framework dashboard hiện đại. Render giao diện Dark Enterprise Cyberpunk với `st_autorefresh` mỗi 1–2 giây, phân tách không gian tác chiến thành 3 tabs chuyên sâu. |
| **PyDeck (Deck.gl)** | latest | Thư viện bản đồ 3D hiệu năng cao. Vẽ 300–600 điểm xe theo loại taxi TLC, bản đồ nhiệt đón khách (Heatmap), radar neon vùng đông xe nhất, beacon sân bay và vẽ lộ trình xe đang chạy. |
| **Plotly** | latest | Trực quan hóa các biểu đồ sóng thời gian thực: tốc độ nạp sự kiện Kafka (Events/s Pulse), phân bổ điểm đón xe (Horizontal Bar), thị phần quận huyện (Donut Chart tối ưu nhãn), và xung dòng tiền doanh thu ($/giây). |
| **PyArrow** | latest | Đọc và parse file Parquet NYC TLC (`yellow_tripdata_*.parquet`) ở chế độ `PARQUET_REPLAY`. |
| **OSRM** | Public API | Open Source Routing Machine — tính toán lộ trình thực tế bám sát mạng lưới đường phố NYC (không phải đường chim bay) và đo lường chỉ số hiệu quả lộ trình (**Route Efficiency & Detour Score**). Fallback về lưới Manhattan nếu timeout. |
| **Docker / Compose** | latest | Đóng gói toàn bộ 5 services (Kafka, Redis, Simulator, Stream Processor, Dashboard) trong network ảo hóa riêng `taxi_stream_net`. |

---

## 📊 Nguồn Dữ Liệu & Schema Chuẩn Hóa

### 1. Hỗ Trợ 3 Đội Xe NYC TLC
Hệ thống phân biệt rõ ràng 3 phân lớp phương tiện chính thức:
- 🟡 **Yellow Cab (`YELLOW`)**: Xe taxi truyền thống khu vực trung tâm Manhattan & sân bay (Mã ID: `yt-*`, Màu: `#FACC15`).
- 🟢 **Green Boro Taxi (`GREEN`)**: Phục vụ Outer Boroughs (Brooklyn, Queens, Bronx, Staten Island) & Upper Manhattan (Mã ID: `gt-*`, Màu: `#22C55E`).
- 🟣 **FHVHV (`FHVHV`)**: High-Volume For-Hire Vehicle — Uber, Lyft, Via (Mã ID: `hv-*`, Màu: `#A855F7`).

### 2. Danh Mục 265 Taxi Zones NYC
Tập dữ liệu chuẩn hóa tại [`data/taxi_zones.json`](file:///run/media/pch1101/PCH/Build/DE/taxi_real_time/data/taxi_zones.json) bao gồm 265 phân vùng Taxi Zones chính thức từ NYC TLC:
- **Khu vực**: Manhattan, Brooklyn, Queens, Bronx, Staten Island, EWR (Newark) và các trung tâm trung chuyển hàng không quốc tế (Sân bay JFK, LaGuardia).
- **Thuộc tính**: Tọa độ địa lý chuẩn (`lat`, `lng`), phân vùng dịch vụ (`service_zone`), và trọng số nhu cầu gốc (`base_demand`).

### 3. Chuẩn Dữ Liệu 19 Cột TLC + Real-Time Telemetry
Mỗi sự kiện truyền phát qua Kafka tuân thủ đúng định dạng hồ dữ liệu TLC:
- **TLC Base**: `VendorID`, `tpep_pickup_datetime`, `tpep_dropoff_datetime`, `passenger_count`, `trip_distance`, `RatecodeID`, `store_and_fwd_flag`, `PULocationID`, `DOLocationID`, `payment_type`, `fare_amount`, `extra`, `mta_tax`, `tip_amount`, `tolls_amount`, `improvement_surcharge`, `total_amount`, `congestion_surcharge`, `Airport_fee`.
- **Real-Time Telemetry**: `trip_id`, `dataset_source`, `current_lat`, `current_lng`, `start_lat`, `start_lng`, `target_lat`, `target_lng`, `speed_mph`, `progress_ratio`, `fare_amount`, `timestamp`.

---

## 🧠 Thuật Toán & Xử Lý Luồng (Streaming Intelligence)

1. **Gaussian Welford Online Dominance & Invasion Detection Engine**:
   - Duy trì $Mean(\mu)$ và $Variance(\sigma^2)$ của tỷ trọng số lượng xe của từng đội taxi tại từng phân vùng trong 265 zones với thuật toán **Welford Online** ($O(1)$ Space Complexity).
   - Tính toán chỉ số xâm lấn theo độ lệch chuẩn:
     $$Z = \frac{Ratio_{current} - \mu}{\sigma}$$
   - Kích hoạt cảnh báo **Invasion Alert** khi $Z > 1.6\sigma$ hoặc $Z > 2.0\sigma$ (báo hiệu một đội xe đang bất ngờ chiếm lĩnh thị phần bất thường tại một phân vùng).
   - Xác định khu vực tranh chấp giằng co (**Contested Zones**) khi khoảng cách giữa 2 đội xe dẫn đầu $< 15\%$.

2. **Sliding Window Density & Congestion Classifier**:
   - Quản lý cửa sổ trượt 60 giây (`SLIDING_WINDOW_SECONDS=60`) để tính toán mật độ xe hoạt động trên từng phân vùng và quận huyện NYC theo thời gian thực.
   - Phân loại mức độ: `LOW` (< 3 xe), `MODERATE` (3–6 xe), `HEAVY` (7–11 xe), `CRITICAL` (≥ 12 xe).

3. **OSRM Route Interpolation & Route Efficiency Analyzer**:
   - Truy vấn Open Source Routing Machine (OSRM) để vẽ lộ trình thực tế bám sát các giao lộ đường phố New York.
   - Phân tích hiệu quả tuyến đường (**Route Efficiency & Detour Score**): Phân loại `OPTIMAL` ($\ge 90\%$), `MODERATE DETOUR` ($75\% - 89\%$), `HIGH DETOUR` ($< 75\%$).

---

## 🖥️ Giao Diện Live Operations Dashboard

Dashboard được thiết kế theo phong cách Dark Cyberpunk Enterprise, chia làm **3 không gian tác chiến chuyên sâu**:

### 1. 🗺️ Tab 1: 3D Fleet Command Map
- **Bản đồ 3D PyDeck tương tác**:
  - **Fleet Pins**: Vị trí đội xe theo thời gian thực với màu sắc chuẩn theo 3 loại taxi (Yellow, Green, FHVHV) hoặc dải màu tốc độ (Fluid $\rightarrow$ Normal $\rightarrow$ Congested).
  - **Pickup Demand Heatmap**: Bản đồ nhiệt mật độ đặt xe trên toàn thành phố với thanh trượt tùy chỉnh bán kính và cường độ sáng.
  - **#1 Busiest Zone Radar**: Vòng radar hào quang neon phát sáng đánh dấu khu vực đông xe nhất.
  - **Airport Hubs Radar**: Beacon định vị tím nổi bật tại 3 sân bay JFK, LaGuardia (LGA) và Newark (EWR).
  - **Camera Presets**: Chuyển nhanh góc nhìn (NYC Overview, Focus #1 Busiest Zone, Focus Airports, Manhattan Core, Brooklyn Hub).
- **Theo dõi xe đơn lẻ (Interactive Driver Focus & Tracking)**:
  - Hiển thị lộ trình OSRM: Đoạn đường đã đi (Cyan neon `#00F5FF`) và đoạn đường sắp đi (Crimson neon `#F43F5E`), kèm điểm đón (Pickup) và điểm trả (Dropoff).
  - Hiển thị HUD chi tiết: Tốc độ, tiến độ cuốc xe, cước phí, hiệu quả lộ trình (Detour Badge).
- **Fleet & Route Corridor Dispatch Panel**:
  - Tìm kiếm xe theo Trip ID / Khu vực / Quận.
  - Phân trang (6 xe/trang) với thanh cuộn mượt mà.
  - Nút **Track Vehicle** để khóa camera bản đồ trực tiếp vào xe đang di chuyển.

### 2. 📈 Tab 2: Live Stream Telemetry & Trends
- **Thanh trạng thái vận hành & 4 Thẻ KPIs Real-Time**:
  - **Active Fleet**: Giám sát **300+ đến 500+ xe taxi** hoạt động đồng thời trong cửa sổ trượt 60 giây.
  - **In-Flight Fare Flow**: Doanh thu cước phí đang lưu thông trên đường và đơn giá trung bình.
  - **Stream Events Processed**: Tổng số sự kiện luồng đã xử lý qua Kafka.
  - **Top Congestion Hotspot**: Khu vực có số lượng xe tập trung đông nhất.
- **4 Biểu đồ phân tích sóng thời gian thực (Plotly Dark)**:
  1. *Kafka Stream Ingestion Velocity*: Tốc độ nạp sự kiện vi mô (Events / Sec Pulse Spline).
  2. *Active Fleet Concentration by Top Pickup Zones*: Biểu đồ thanh ngang Top 8 điểm đón xe đông nhất.
  3. *Borough Fleet Market Share Distribution*: Biểu đồ Donut tỷ trọng quận huyện chuẩn mực (nhãn nằm ngang, tự căn chỉnh khoảng cách, không chồng đè Legend).
  4. *Real-Time Revenue Velocity*: Biểu đồ diện tích kép đo xung dòng tiền cước và phụ phí ($/giây).
- **Live Micro-Batch Stream Feed**: Bảng feed vi mô thời gian thực với các nhãn trạng thái động (`EXPRESS_SPEED`, `HEAVY_TRAFFIC`, `ARRIVING_SOON`, `CRUISING`).

### 3. ⚔️ Tab 3: Fleet Power Map
- **Thanh kiểm soát lãnh thổ (Territory Control Bar)**: Tỷ lệ % số zone mà Yellow, Green, FHVHV đang chiếm ưu thế tuyệt đối.
- **Bản đồ 3D Quyền Lực (PyDeck Power Map)**:
  - 265 Taxi Zones được tô màu theo đội xe thống trị (`dominant_fleet`), kích thước bán kính tỉ lệ thuận với lượng xe.
  - Vòng tròn đỏ phát xung cảnh báo tại các khu vực đang xảy ra **Invasion Alert** ($Z > 2.0\sigma$).
  - Vùng tranh chấp màu vàng neon (**Contested Zones**).
- **Live Invasion Feed & Battleground Hotspots**: Bảng theo dõi chi tiết các cuộc xâm lấn thị phần và các điểm nóng tranh chấp khốc liệt nhất.

---

## 🚀 Hướng Dẫn Cài Đặt & Khởi Chạy

### 1. Yêu cầu hệ thống
- **Docker** & **Docker Compose** đã được cài đặt và đang chạy.
- RAM tối thiểu: 4 GB.

### 2. Khởi chạy toàn bộ hệ thống
```bash
# Di chuyển vào thư mục dự án
cd /run/media/pch1101/PCH/Build/DE/taxi_real_time

# Build và khởi chạy tất cả các containers ở chế độ daemon
docker compose up -d --build
```

### 3. Truy cập Dashboard
Mở trình duyệt web và truy cập:
👉 **[http://localhost:8501](http://localhost:8501)**

---

## 🛠️ Quản Trị & Giám Sát Luồng (Operations & Debugging)

### Kiểm tra trạng thái containers:
```bash
docker compose ps
```

### Xem logs thời gian thực:
```bash
# Log phát sự kiện từ simulator
docker compose logs -f simulator

# Log xử lý luồng & thuật toán phân tích quyền lực thị phần
docker compose logs -f stream-processor

# Log giao diện dashboard
docker compose logs -f dashboard
```

### Khởi động lại dịch vụ khi cần:
```bash
docker compose restart dashboard
docker compose restart stream-processor
```

### Truy vấn dữ liệu trực tiếp trong Redis:
```bash
# Kiểm tra snapshot mật độ mới nhất
docker exec -it taxi-realtime-redis redis-cli GET kv:latest_density_metrics

# Kiểm tra snapshot bản đồ quyền lực
docker exec -it taxi-realtime-redis redis-cli GET kv:power_map_snapshot

# Kiểm tra bộ đếm KPIs tổng hợp
docker exec -it taxi-realtime-redis redis-cli HGETALL hash:realtime_kpis
```

---

## 📁 Cấu Trúc Thư Mục Dự Án

```text
taxi_real_time/
├── data/
│   └── taxi_zones.json            # Dữ liệu địa lý 265 Taxi Zones NYC chuẩn TLC
├── simulator/
│   ├── Dockerfile
│   ├── config.py                  # Cấu hình tần suất, tỷ lệ xe, source mode
│   ├── trip_generator.py          # Logic sinh sự kiện & nạp file Parquet
│   ├── kafka_producer.py          # Kafka Producer phát luồng sự kiện
│   └── requirements.txt
├── flink_processor/
│   ├── Dockerfile
│   ├── config.py                  # Cấu hình sliding window, intervals, Redis keys
│   ├── flink_streaming_job.py     # Flink Stream Engine, Density & Power Map (Welford)
│   └── requirements.txt
├── dashboard/
│   ├── Dockerfile
│   ├── config.py                  # Cấu hình kết nối Redis & Refresh Rate
│   ├── data_loader.py             # Lớp lấy dữ liệu từ Redis State
│   ├── app.py                     # Streamlit Live Multi-Tab Operations Center
│   └── requirements.txt
├── docker-compose.yml             # Khởi chạy Kafka 3.8, Redis 7.2, Simulator, Processor, Dashboard
├── DATA_FLOW.md                   # Tài liệu chi tiết luồng dữ liệu 5 tầng
├── .env.example                   # Biến môi trường mẫu
└── README.md                      # Tài liệu hướng dẫn toàn diện của dự án
```
