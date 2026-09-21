# Luồng Dữ Liệu — NYC Taxi Real-Time Pipeline

```
Parquet / Synthetic ──► Kafka ──► Stream Processor (Flink) ──► Redis ──► Dashboard (Streamlit) ──► Browser
```

---

## TẦNG 1 — Simulator & Data Ingestion

**Files:** `simulator/trip_generator.py` · `simulator/kafka_producer.py` · `simulator/config.py`

- Hỗ trợ đầy đủ **3 loại taxi NYC TLC**:
  - 🟡 **Yellow Taxi (`YELLOW`):** Xe taxi truyền thống khu vực trung tâm Manhattan & sân bay (ID: `yt-*`).
  - 🟢 **Green Taxi (`GREEN`):** Boro Taxi phục vụ Outer Boroughs & Upper Manhattan (ID: `gt-*`).
  - 🟣 **FHVHV (`FHVHV`):** High-Volume For-Hire Vehicle — Uber, Lyft, Via (ID: `hv-*`).
- **2 Chế độ nạp dữ liệu (`SOURCE_MODE`)**:
  - `PARQUET_REPLAY`: Nạp và phát lại từ file dữ liệu thực tế NYC TLC Parquet 19 cột canonical.
  - `SYNTHETIC_STREAM`: Sinh dữ liệu ngẫu nhiên đa luồng theo trọng số phân bổ 265 Taxi Zones NYC (Yellow 40%, Green 10%, FHVHV 50%).
- **Vòng đời sự kiện chuyến xe (3 trạng thái)**:
  `TRIP_STARTED` ──► `LOCATION_PING` (Nội suy tọa độ GPS, tốc độ mph, cước phí lũy tiến) ──► `TRIP_COMPLETED`
- Duy trì đồng thời **300+ đến 500+ xe (`MAX_CONCURRENT_TRIPS`)**, sản sinh **20–100 events/giây** đẩy liên tục vào Kafka.

---

## TẦNG 2 — Message Broker (Apache Kafka)

**Topic:** `taxi.trips.live` · 3 Partitions · KRaft Mode (`apache/kafka:3.8.0`)

- Tiếp nhận toàn bộ event vi mô từ Simulator kèm metadata định danh (`dataset_source`, `trip_id`, `speed_mph`, `fare_amount`, `progress_ratio`, tọa độ GPS).
- **Phân tách tốc độ (Decoupling Buffer)**: Producer đẩy nhanh (20–100 evt/s), Consumer đọc ổn định theo batch, bảo toàn dữ liệu khi downstream tải nặng.
- Consumer Group: `taxi-stream-processor-group` với `auto_offset_reset=latest` (xử lý ngay dữ liệu mới nhất).

---

## TẦNG 3 — Stream Processing Engine (Apache Flink / Streaming Processor)

**Files:** `flink_processor/flink_streaming_job.py` · `flink_processor/config.py`

Mỗi sự kiện từ Kafka được nạp vào **`FlinkStreamEngine`**:
1. **Sliding Window 60s (`_vehicles`)**: Lưu trạng thái vị trí, tốc độ, cước phí và tiến trình di chuyển của từng xe. Tự động dọn dẹp các xe stale (không có ping > 60s) để tránh hiển thị "xe ma".
2. **Zone Density Aggregator (265 Zones)**: Phân loại mức độ ùn tắc theo 4 cấp độ (`LOW` < 3 xe, `MODERATE` 3–6 xe, `HEAVY` 7–11 xe, `CRITICAL` ≥ 12 xe).
3. **Bản Đồ Quyền Lực Đội Xe (Fleet Power Map Engine)**:
   - `ZonePowerTracker` ứng dụng **thuật toán Gaussian Welford Online** theo dõi tỷ lệ chiếm lĩnh thị phần ($Mean\ \mu$, $Variance\ \sigma^2$) của từng đội xe trên từng phân vùng với độ phức tạp không gian $O(1)$.
   - Tính **Invasion Z-Score**: $Z = \frac{Ratio_{current} - \mu}{\sigma}$. Phát hiện cảnh báo xâm lấn thị phần khi $Z > 1.6\sigma$ hoặc $Z > 2.0\sigma$.
   - Xác định khu vực tranh chấp (**Contested Zones** khi khoảng cách giữa 2 đội xe dẫn đầu < 15%).
4. **Phát tán trạng thái định kỳ (2s tick interval)**: Tổng hợp và ghi đồng bộ toàn bộ snapshot metrics vào Redis thông qua pipeline.

---

## TẦNG 4 — In-Memory State & Pub/Sub Store (Redis 7.2)

**Keys & Channels chính:**
- `kv:latest_density_metrics`: Lưu snapshot mật độ 265 zones, danh sách xe active, phân bố 3 đội xe và top điểm nóng.
- `kv:power_map_snapshot`: Lưu riêng danh sách `invasion_zones` và thống kê `territory_counts` (TTL 10s — tự hủy nếu luồng dừng để tránh dữ liệu rác).
- `hash:realtime_kpis`: Bộ đếm tổng sự kiện `total_events_processed`, tổng xe active `total_active_vehicles`, và timestamp cập nhật.
- `channel:density_metrics`: Kênh Pub/Sub phát tín hiệu real-time khi có snapshot mới.
- Đóng vai trò **điểm trung gian phi trạng thái duy nhất** kết nối Stream Processor và Dashboard.

---

## TẦNG 5 — Live Operations Dashboard (Streamlit & PyDeck)

**Files:** `dashboard/app.py` · `dashboard/data_loader.py` · `dashboard/config.py`

Dashboard tự động làm mới (`st_autorefresh` mỗi 1–2 giây) lấy dữ liệu từ Redis, hiển thị trên giao diện Dark Enterprise Cyberpunk gồm **3 Tabs chuyên sâu**:

### 1. 🗺️ Tab 1: 3D Fleet Command Map
- **Bản đồ 3D PyDeck tương tác**:
  - **Fleet Pins**: 300+ vị trí xe thời gian thực với màu sắc chuẩn TLC (🟡 Yellow `#FACC15`, 🟢 Green `#22C55E`, 🟣 FHVHV `#A855F7`) hoặc chế độ màu theo dải tốc độ (Fluid / Normal / Congestion).
  - **Pickup Demand Heatmap**: Bản đồ nhiệt mật độ đón khách với thanh trượt tùy chỉnh bán kính (`radius`) và cường độ sáng (`intensity`).
  - **#1 Busiest Zone Radar**: Radar hào quang neon phát sáng đánh dấu vùng tập trung đông xe nhất.
  - **Airport Hubs Radar**: Beacon định vị nổi bật tại 3 sân bay quốc tế (JFK, LGA, EWR).
- **Theo dõi xe đơn lẻ & HUD Chỉ Huy (Interactive Driver Focus)**:
  - Tích hợp **OSRM Driving Route Engine**: Lộ trình đường phố thực tế chia 2 nhánh màu (Đoạn đã đi: Cyan neon `#00F5FF`, Đoạn sắp tới: Crimson neon `#F43F5E`).
  - Phân tích hiệu suất tuyến đường (**Route Efficiency & Detour Score**): Phân loại `OPTIMAL` (≥90%), `MODERATE DETOUR` (75–89%), `HIGH DETOUR` (<75%).
- **Fleet Dispatch Panel**: Tìm kiếm xe theo Trip ID/Borough, phân trang mượt mà (6 xe/trang), nút bấm chuyển focus camera trực tiếp đến xe.

### 2. 📈 Tab 2: Live Stream Telemetry & Trends
- **Top Operations Banner & 4 Thẻ KPI**: Active Fleet (3 loại xe), Doanh thu In-Flight ($/trip), Kafka Stream Events, Top Hotspot.
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
- **Live Invasion Feed & Battleground Hotspots**: Bảng theo dõi chi tiết các cuộc xâm lấn thị phần và vùng cạnh tranh khốc liệt nhất.

---

## Sơ Đồ Kiến Trúc Luồng Tổng Thể

```
[ Parquet TLC / Synthetic Generator ]
                 │
                 ▼  JSON Telemetry (20–100 events/sec)
        ┌──────────────────┐
        │  Apache Kafka    │  Topic: taxi.trips.live (3 Partitions)
        └────────┬─────────┘
                 │ Consume (auto_offset_reset=latest)
                 ▼
        ┌────────────────────────────────────────────────────────┐
        │        Apache Flink / Streaming Processor              │
        │  ├── Sliding Window 60s (_vehicles state)              │
        │  ├── Zone Density & Congestion Classifier (265 Zones)  │
        │  └── ZonePowerTracker (Gaussian Welford Z-Score)       │
        └────────────────────────┬───────────────────────────────┘
                                 │ Pipeline SET / PUBLISH (2s Tick)
                                 ▼
        ┌────────────────────────────────────────────────────────┐
        │              Redis 7.2 In-Memory Store                 │
        │  ├── kv:latest_density_metrics                         │
        │  ├── kv:power_map_snapshot (TTL 10s)                   │
        │  └── hash:realtime_kpis                                │
        └────────────────────────┬───────────────────────────────┘
                                 │ Polling GET / HGETALL (1–2s)
                                 ▼
        ┌────────────────────────────────────────────────────────┐
        │        Streamlit Live Operations Dashboard             │
        │  ├── Tab 1: 🗺️ 3D Fleet Command Map (PyDeck + OSRM)    │
        │  ├── Tab 2: 📈 Live Stream Telemetry & Trends (Plotly) │
        │  └── Tab 3: ⚔️ Fleet Power Map (Territory Dominance)   │
        └────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
                      Web Browser (Port 8501)
```

---

## Bảng Tóm Tắt Đặc Tả Kỹ Thuật

| Thành phần | Cơ chế hoạt động | Đặc tả chi tiết |
|------------|------------------|-----------------|
| **Power Map Welford** | Thống kê Online $O(1)$ | Theo dõi dominance ratio của 3 đội xe tại từng zone; $Z > 1.6\sigma$ hoặc $2.0\sigma$ kích hoạt Invasion Alert |
| **Đệm Kafka** | KRaft 3 Partitions | Tách biệt hoàn toàn tốc độ nạp (20–100 evt/s) và chu kỳ render giao diện (2s) |
| **Quản lý Stale State** | Time-based Eviction | Tự động loại bỏ xe không có ping trong 60s để tránh hiện tượng "xe ma" |
| **Power Map Snapshot TTL** | In-Memory Expiration | `kv:power_map_snapshot` có TTL 10s, tự động làm sạch trạng thái khi luồng dừng |
| **OSRM Street Routing** | Highway Network Graph | Truy vấn OSRM API cho lộ trình bám sát mạng lưới đường phố NYC; fallback Manhattan Grid khi timeout |
