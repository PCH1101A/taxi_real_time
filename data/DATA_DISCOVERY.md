# 🗂️ Data Discovery — NYC Taxi Real-Time Pipeline

> **Scope:** `d:\Build\DE\taxi_real_time\data\`
> **Discovered:** 2026-09-16
> **Period:** April 2026 (tháng 4/2026)

---

## 📁 Cấu Trúc Thư Mục

```
data/
├── yellow_tripdata_2026-04.parquet     (61.82 MB)
├── green_tripdata_2026-04.parquet      ( 1.03 MB)
├── fhvhv_tripdata_2026-04.parquet     (486.25 MB)
└── taxi_zones/
    ├── taxi_zones.shp   (Polygon geometry)
    ├── taxi_zones.dbf   (Attributes)
    ├── taxi_zones.shx   (Index)
    ├── taxi_zones.prj   (Projection)
    └── taxi_zones.cpg   (Encoding)
```

**Tổng dung lượng:** ~549 MB
**Nguồn dữ liệu:** https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page

---

## 🟡 1. Yellow Taxi — `yellow_tripdata_2026-04.parquet`

### Tổng quan

| Thuộc tính        | Giá trị                          |
|-------------------|----------------------------------|
| **Số dòng**       | 3,831,240                        |
| **Số cột**        | 20                               |
| **Row groups**    | 4                                |
| **Kích thước**    | 61.82 MB                         |
| **Khoảng thời gian** | 2026-04-01 → 2026-04-30       |
| **Format**        | Parquet (compressed)             |

### Schema

| Cột | Kiểu dữ liệu | Null Count | Ghi chú |
|-----|-------------|-----------|---------|
| `VendorID` | int32 | 0 | 1=CMT, 2=VeriFone, 6, 7 |
| `tpep_pickup_datetime` | timestamp[us] | 0 | Thời điểm đón khách |
| `tpep_dropoff_datetime` | timestamp[us] | 0 | Thời điểm trả khách |
| `passenger_count` | int64 | **799,786** | ~20.9% null |
| `trip_distance` | double | 0 | Miles |
| `RatecodeID` | int64 | **799,786** | ~20.9% null |
| `store_and_fwd_flag` | large_string | **799,786** | ~20.9% null |
| `PULocationID` | int32 | 0 | Pickup zone (1–263) |
| `DOLocationID` | int32 | 0 | Dropoff zone (1–263) |
| `payment_type` | int64 | 0 | 0–4 |
| `fare_amount` | double | 0 | USD |
| `extra` | double | 0 | |
| `mta_tax` | double | 0 | |
| `tip_amount` | double | 0 | |
| `tolls_amount` | double | 0 | |
| `improvement_surcharge` | double | 0 | |
| `total_amount` | double | 0 | USD |
| `congestion_surcharge` | double | **799,786** | ~20.9% null |
| `Airport_fee` | double | **799,786** | ~20.9% null |
| `cbd_congestion_fee` | double | 0 | NYC Central Business District fee |

### Thống kê giá trị

| Chỉ số | Min | Max | Mean |
|--------|-----|-----|------|
| `total_amount` | -1,278.40 | 1,452.66 | $30.00 |
| `trip_distance` | 0.00 | 281,576.08 (!) | 5.18 miles |

### Giá trị phân loại

| Cột | Giá trị |
|-----|---------|
| `VendorID` | 1, 2, 6, 7 |
| `passenger_count` | 0–9 |
| `payment_type` | 0, 1, 2, 3, 4 |
| `RatecodeID` | 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 99.0 |

> ⚠️ **Data Quality:** `trip_distance` max = 281,576 miles — outlier/data error nghiêm trọng.
> `total_amount` âm → có thể là hoàn tiền (refund/reversal).
> ~20.9% null ở `passenger_count`, `RatecodeID`, `store_and_fwd_flag`, `congestion_surcharge`, `Airport_fee`.

---

## 🟢 2. Green Taxi — `green_tripdata_2026-04.parquet`

### Tổng quan

| Thuộc tính        | Giá trị                          |
|-------------------|----------------------------------|
| **Số dòng**       | 44,238                           |
| **Số cột**        | 21                               |
| **Row groups**    | 1                                |
| **Kích thước**    | 1.03 MB                          |
| **Khoảng thời gian** | 2026-04-01 → 2026-04-30       |
| **Format**        | Parquet (compressed)             |

> Green taxi phục vụ ngoài Manhattan và các khu vực ngoại ô. Volume thấp hơn Yellow ~87 lần.

### Schema

| Cột | Kiểu dữ liệu | Null Count | Ghi chú |
|-----|-------------|-----------|---------|
| `VendorID` | int32 | 0 | 1, 2, 6 |
| `lpep_pickup_datetime` | timestamp[us] | 0 | |
| `lpep_dropoff_datetime` | timestamp[us] | 0 | |
| `store_and_fwd_flag` | large_string | 6,290 | ~14.2% null |
| `RatecodeID` | int64 | 6,290 | ~14.2% null |
| `PULocationID` | int32 | 0 | |
| `DOLocationID` | int32 | 0 | |
| `passenger_count` | int64 | 6,290 | ~14.2% null |
| `trip_distance` | double | 0 | |
| `fare_amount` | double | 0 | |
| `extra` | double | 0 | |
| `mta_tax` | double | 0 | |
| `tip_amount` | double | 0 | |
| `tolls_amount` | double | 0 | |
| `ehail_fee` | double | **44,238** | **100% null** — deprecated |
| `improvement_surcharge` | double | 0 | |
| `total_amount` | double | 0 | |
| `payment_type` | int64 | 6,290 | ~14.2% null |
| `trip_type` | int64 | 6,290 | 1=Street-hail, 2=Dispatch |
| `congestion_surcharge` | double | 6,290 | ~14.2% null |
| `cbd_congestion_fee` | double | 0 | |

### Thống kê giá trị

| Chỉ số | Min | Max | Mean |
|--------|-----|-----|------|
| `total_amount` | -171.00 | 675.10 | $25.41 |
| `trip_distance` | 0.00 | 95,906.47 (!) | 11.38 miles |

### Giá trị phân loại

| Cột | Giá trị |
|-----|---------|
| `VendorID` | 1, 2, 6 |
| `trip_type` | 1 (Street-hail), 2 (Dispatch) |

> ⚠️ **Data Quality:** `ehail_fee` = 100% null — cột deprecated, nên drop.
> `trip_distance` max = 95,906 miles — outlier nghiêm trọng.

---

## 🔵 3. For-Hire Vehicle High Volume (FHVHV) — `fhvhv_tripdata_2026-04.parquet`

### Tổng quan

| Thuộc tính        | Giá trị                          |
|-------------------|----------------------------------|
| **Số dòng**       | 20,995,953                       |
| **Số cột**        | 25                               |
| **Row groups**    | 21                               |
| **Kích thước**    | 486.25 MB                        |
| **Khoảng thời gian** | 2026-04-01 → 2026-04-30       |
| **Nhà cung cấp**  | Uber (HV0003), Lyft (HV0005)     |
| **Format**        | Parquet (compressed)             |

> Dataset lớn nhất — **~5.5x** số chuyến của Yellow Taxi. Đây là dữ liệu Ride-Share (không phải taxi truyền thống).

### Schema

| Cột | Kiểu dữ liệu | Null Count | Ghi chú |
|-----|-------------|-----------|---------|
| `hvfhs_license_num` | large_string | 0 | HV0003=Uber, HV0005=Lyft |
| `dispatching_base_num` | large_string | 0 | Mã cơ sở điều phối |
| `originating_base_num` | large_string | **5,594,175** | ~26.6% null |
| `request_datetime` | timestamp[us] | 0 | Thời điểm yêu cầu |
| `on_scene_datetime` | timestamp[us] | 0 | Tài xế đến nơi |
| `pickup_datetime` | timestamp[us] | 0 | Thực tế đón khách |
| `dropoff_datetime` | timestamp[us] | 0 | Thực tế trả khách |
| `PULocationID` | int32 | 0 | |
| `DOLocationID` | int32 | 0 | |
| `trip_miles` | double | 0 | |
| `trip_time` | int64 | 0 | Giây |
| `base_passenger_fare` | double | 0 | Cước cơ bản (USD) |
| `tolls` | double | 0 | |
| `bcf` | double | 0 | Black Car Fund |
| `sales_tax` | double | 0 | |
| `congestion_surcharge` | double | 0 | |
| `airport_fee` | double | 0 | |
| `tips` | double | 0 | |
| `driver_pay` | double | 0 | Lương tài xế (USD) |
| `shared_request_flag` | large_string | 0 | Y/N |
| `shared_match_flag` | large_string | 0 | Y/N |
| `access_a_ride_flag` | large_string | 0 | Y/N (MTA paratransit) |
| `wav_request_flag` | large_string | 0 | Y/N (Wheelchair) |
| `wav_match_flag` | large_string | 0 | Y/N |
| `cbd_congestion_fee` | double | 0 | NYC CBD fee |

### Thống kê giá trị

| Chỉ số | Min | Max | Mean |
|--------|-----|-----|------|
| `base_passenger_fare` | -222.34 | 1,445.92 | $27.24 |
| `trip_miles` | 0.00 | 1,468.15 | 4.87 miles |

### Giá trị phân loại

| Cột | Giá trị |
|-----|---------|
| `hvfhs_license_num` | `HV0003` (Uber), `HV0005` (Lyft) |
| `shared_request_flag` | Y, N |
| `wav_request_flag` | Y, N |

> ℹ️ FHVHV có 4 timestamp: `request_datetime` → `on_scene_datetime` → `pickup_datetime` → `dropoff_datetime`.
> Cho phép tính **wait time** và **ETA accuracy**.
> `originating_base_num` ~26.6% null — xảy ra khi chuyến không có base originator.

---

## 🗺️ 4. Taxi Zones — `taxi_zones/`

### Tổng quan

| Thuộc tính | Giá trị |
|------------|---------|
| **Loại file** | Shapefile (ESRI) |
| **Geometry** | Polygon (Shape Type 5) |
| **Số vùng** | **263 zones** |
| **Hệ tọa độ** | NAD 1983 StatePlane New York Long Island (FIPS 3104, Feet) |
| **Bounding Box** | (913175.11, 120121.88) → (1,067,382.51, 272,844.29) |

### Files

| File | Kích thước | Mô tả |
|------|-----------|-------|
| `taxi_zones.shp` | 1.51 MB | Geometry (polygon) |
| `taxi_zones.dbf` | 58.5 KB | Attribute table |
| `taxi_zones.shx` | 2.15 KB | Shape index |
| `taxi_zones.prj` | 0.55 KB | Projection definition |
| `taxi_zones.cpg` | 5 B | Character encoding |

### Attribute Schema (DBF)

| Field | Type | Length | Ghi chú |
|-------|------|--------|---------|
| `OBJECTID` | Numeric | 9 | Internal ID |
| `Shape_Leng` | Numeric | 24 | Chu vi polygon |
| `Shape_Area` | Numeric | 24 | Diện tích polygon |
| `zone` | Character | 80 | Tên vùng (e.g. "JFK Airport") |
| `LocationID` | Numeric | 9 | **Join key** → PULocationID / DOLocationID |
| `borough` | Character | 80 | Manhattan, Brooklyn, Queens, Bronx, Staten Island, EWR |

> 💡 `LocationID` là foreign key để join với `PULocationID`/`DOLocationID` trong các file parquet.
> 263 zones bao phủ toàn NYC + Newark Airport (EWR).

---

## 📊 Tổng Hợp So Sánh

| Dataset | Số chuyến | Kích thước | Nhà cung cấp | Phạm vi |
|---------|-----------|-----------|-------------|---------|
| Yellow Taxi | 3,831,240 | 61.82 MB | CMT, VeriFone | Toàn NYC (chủ yếu Manhattan) |
| Green Taxi | 44,238 | 1.03 MB | CMT, VeriFone | Ngoài Manhattan, outer boroughs |
| FHVHV (Uber/Lyft) | 20,995,953 | 486.25 MB | Uber, Lyft | Toàn NYC |
| **TỔNG** | **24,871,431** | **549.10 MB** | — | — |

---

## ⚠️ Vấn Đề Chất Lượng Dữ Liệu (Data Quality Issues)

### Outliers cần xử lý

| Dataset | Cột | Vấn đề |
|---------|-----|--------|
| Yellow | `trip_distance` | Max = 281,576 miles (không thực tế) |
| Green | `trip_distance` | Max = 95,906 miles (không thực tế) |
| Yellow / Green | `total_amount` | Giá trị âm (refund?) |
| FHVHV | `base_passenger_fare` | Giá trị âm (-222.34) |

### Null values đáng chú ý

| Dataset | Cột | Tỷ lệ null |
|---------|-----|-----------|
| Yellow | `passenger_count`, `RatecodeID`, `Airport_fee`, `congestion_surcharge` | ~20.9% |
| Green | `ehail_fee` | **100%** (deprecated — nên drop) |
| Green | `store_and_fwd_flag`, `RatecodeID`, `passenger_count` | ~14.2% |
| FHVHV | `originating_base_num` | ~26.6% |

### Timestamp anomalies

| Dataset | Vấn đề |
|---------|--------|
| Yellow | Min timestamp = 2001-01-01 (dữ liệu cũ lẫn vào) |
| Yellow | Có records pickup > 2026-04-30 |
| Green | Một số records ngoài khoảng tháng 4 |

---

## 🔗 Quan Hệ Giữa Các Dataset

```
┌─────────────────────────────────────────────────┐
│                  taxi_zones                      │
│   LocationID (263 zones) ◄──────────────────┐   │
└─────────────────────────────────────────────┼───┘
                                              │ JOIN
    ┌─────────────────┐    ┌──────────────────┴──────────────┐
    │  yellow_tripdata│    │  PULocationID / DOLocationID    │
    │  green_tripdata │────►  (present in all 3 datasets)    │
    │  fhvhv_tripdata │    └─────────────────────────────────┘
    └─────────────────┘
```

**Shared keys:**
- `PULocationID` → `taxi_zones.LocationID` (Pickup zone)
- `DOLocationID` → `taxi_zones.LocationID` (Dropoff zone)
- Timestamp columns → Stream partitioning / windowing
- `cbd_congestion_fee` → Có mặt trong cả 3 datasets (NYC CBD Congestion Pricing, effective Jan 2025)

---

## 🚀 Khuyến Nghị cho Streaming Pipeline

| Ưu tiên | Hành động |
|---------|-----------|
| P0 | **Filter outliers**: `trip_distance > 200` miles, timestamp ngoài khoảng ±1 ngày |
| P0 | **Watermark strategy**: FHVHV dùng `pickup_datetime`; Yellow dùng `tpep_pickup_datetime`; Green dùng `lpep_pickup_datetime` |
| P1 | **Drop deprecated columns**: `ehail_fee` (Green — 100% null) |
| P1 | **Broadcast join** `taxi_zones` (nhỏ — 1.5 MB shapefile) với stream chính |
| P2 | **Null handling**: `passenger_count` null → default = 1; `RatecodeID` null → default = 1 (Standard) |
| P2 | **Unify schema**: Chuẩn hóa tên cột pickup/dropoff datetime trước khi merge 3 streams |
| P3 | **Partition key**: `PULocationID` + `hour(pickup_datetime)` cho Kafka topic partitioning |
