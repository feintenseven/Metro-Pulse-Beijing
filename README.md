# Beijing Metro AFC Data Analysis & Interactive Simulation System

A data analysis and interactive simulation project built on real Beijing Metro AFC (Automatic Fare Collection) card data from February 2018. The project covers data parsing, statistical hypothesis testing, passenger behavior profiling with K-Means clustering, and an interactive metro route planning simulation game.

> **Data period:** February 21–27, 2018 (Spring Festival return period — from the 7th day to the 15th day of the lunar new year, 7 days total)
> **Raw data volume:** 9.64 GB, 4,609 CSV files

---

## Project Structure

```
final_metro_project/
├── Data-driven game application/
│   ├── beijing_metro_game.html       # Interactive metro simulation game
│   ├── README.md                     # Game documentation
│   └── ReadMe.md                     # Original Chinese documentation
├── Card data analysis and HTML-based visualization/
│   ├── card_analysis.py              # Card-level behavior analysis script
│   ├── card_analysis_3.py            # Alternative version of card analysis
│   ├── card_analysis_report.html     # Auto-generated HTML report
│   ├── card_analysis_report_2.html   # Alternative HTML report
│   └── card_behavior_analysis_conclusions.md  # Analysis conclusions
├── EDA and Data Visualization/
│   ├── metro_step1.py                # Metro map rendering (pygame)
│   ├── hub_heatmap.py                # Transport hub heatmap generation
│   ├── hypothesis_01_commute_flow/
│   │   └── analysis.py               # Commute flow directionality study
│   ├── hypothesis_02_transport_hubs/
│   │   └── analysis.py               # Hub passenger flow pattern study
│   ├── heatmaps/                     # Generated heatmap HTML files
│   ├── *_stations_coords.json        # Station coordinate data
│   ├── *_hub_flow_data.json          # Hub flow data
│   ├── *_hub_destinations.json       # Hub destination data
│   └── meta.json                     # Dataset metadata
└── Data/
    └── data.txt                      # Data description (sensitive info omitted)
```

---

## 1. Data Processing

### 1.1 Raw Data Parsing

The original CSV files have **34 columns with no column headers**. Column meanings were determined through an iterative process of sampling, guessing, and cross-validating. During this process, **8 errors** were discovered in the original data documentation, including:
- Card ID (column 7) mislabeled as "transaction amount"
- Fare (column 26) mislabeled as "ride duration"

### 1.2 Data Specifications

| Metric | Value |
|--------|-------|
| Raw data volume | 9.64 GB, 34 archives, 4,609 CSV files |
| Valid trip records | ~25.78 million |
| Unique card IDs (passengers) | 6.48 million |
| Active passengers (>=3 trips) | 3.17 million |
| Metro stations | 318 (all with coordinates) |
| Network topology edges | 355 |
| OD flow records | ~8.45 million (7 days, 20-min windows) |

### 1.3 Missing Data Imputation

19 station IDs (e.g., "Line 14 #45") lacked Chinese station names. Of these, 9 were identified by comparing with line alignments. 10 intermediate stations on Line 14 were kept as numbered IDs for topological connectivity only.

---

## 2. Statistical Analysis & Hypothesis Testing

### 2.1 Commute Flow Directionality

Tests whether peak-hour flows between residential and work areas match expected patterns during the Spring Festival return period:

- **Morning peak (7:00–10:00):** residential areas → work areas (net positive)
- **Evening peak (17:00–20:00):** work areas → residential areas (net positive)

**Methods:** Binomial tests for directional dominance, morning-vs-evening contrast analysis, daily ratio trends, and time-series heatmaps for key commute pairs (e.g., Huilongguan → Xi'erqi, Tiantongyuan → Guomao).

### 2.2 Transport Hub Passenger Flow Patterns

Analyzes return-flow surges at Beijing's major transport hubs (Beijing Station, Beijing West Station, Beijing South Station, T2/T3 Airport Terminals):

- **Hypothesis 1:** Net exit flow > 0 for all hubs (passengers returning to Beijing)
- **Hypothesis 2:** Net exit flow declines from Feb 22 to Feb 28 as the return peak subsides
- **Hypothesis 3:** Afternoon/evening peaks dominate hub exit flow

**Methods:** One-sided t-tests for net exit flow, linear regression for trend analysis, hourly pattern analysis, and 8 visualization figures.

### 2.3 Individual Card Behavior Analysis

Profiles individual passenger behavior from 6.48M card IDs using K-Means clustering:

- **Data volume reduction:** Only cards with >=3 trips (3.17M cards) enter analysis
- **Clustering:** Random sample of 50k cards, 9 feature dimensions, MiniBatchKMeans (k=5)
- **Cluster results:**

| Type | Description | Estimated Proportion |
|------|-------------|---------------------|
| 🕐 Fixed Commuters | Regular peak-hour commuters, fixed routes, high weekday frequency | Largest group |
| 🌆 Light Commuters | Weekday-oriented, relatively fixed time, diverse routes | Second largest |
| 🧭 Flexible Travelers | Scattered travel times, non-peak, diverse routes | Moderate |
| 🎉 Weekend Leisure | Weekend/non-workday focused, afternoon-heavy, lower fares | Smaller group |
| 🚄 Long-distance Heavy Users | Long distance, high fare, low frequency (suburban/migrant) | Smallest group |

**Key findings:**
- ~1.01M passengers (32% of active) show strong commuting patterns
- Weekday trips are ~3× weekend trips
- Entry time distribution shows a clear bimodal peak (7–8 AM and 6–7 PM)
- Fare concentrated in 3–5 CNY range (short-to-medium distance)
- Most common ride duration: 20–40 minutes

---

## 3. Interactive Simulation Game

`beijing_metro_game.html` — a fully self-contained single-page application for designing metro networks and simulating operations in real time.

### Core Features

| Feature | Description |
|---------|-------------|
| **Network Planning** | Place stations on a real Leaflet map, connect them into metro lines, create loops |
| **Demand Heatmap** | Overlay passenger flow intensity to guide station placement |
| **Real-time Simulation** | Run a full day in ~160 seconds with passengers generated from real OD data |
| **Complaint System** | 6 complaint types (crowded, slow, detour, transfer, miss, far) with real-time feedback |
| **Evaluation** | End-of-day S/A/B/C/D rating with detailed metrics and breakdowns |
| **Line Editing** | Add/remove stations, rename, change colors, adjust train frequency |

### Technology

- **Map:** Leaflet 1.9.4 + CARTO tiles
- **Heatmap:** leaflet.heat plugin
- **Rendering:** Canvas overlay
- **Simulation:** Pure JavaScript, `requestAnimationFrame` loop
- **No backend required** — just double-click the HTML file

See [Data-driven game application/README.md](Data-driven%20game%20application/README.md) for complete documentation.

---

## 4. How to Run

### Environment Setup

```bash
pip install scikit-learn numpy folium
```

The simulation game requires no installation — open directly in a browser.

### Running Analysis Modules

**Card-level behavior analysis:**
```bash
# Place card_analysis.py in the directory containing AFC_*.CSV files
python card_analysis.py
# Output: card_analysis_report.html
```

**Commute flow hypothesis test:**
```bash
python "EDA and Data Visualization/hypothesis_01_commute_flow/analysis.py"
```

**Transport hub hypothesis test:**
```bash
python "EDA and Data Visualization/hypothesis_02_transport_hubs/analysis.py"
```

**Hub heatmap generation:**
```bash
python "EDA and Data Visualization/hub_heatmap.py"
```

### Running the Simulation Game

Simply open `Data-driven game application/beijing_metro_game.html` in any modern browser (Chrome, Firefox, Edge recommended).

---

## 5. Key Technical Challenges

| Challenge | Solution |
|-----------|----------|
| **Untagged raw data** | Iterative sampling → guessing → cross-validation; found 8 documentation errors |
| **Massive data (6.48M cards)** | Filter irregular travelers (>=3 trips), MiniBatchKMeans, lightweight tuple storage |
| **Missing station names** | Cross-reference with line alignments; 9 of 19 identified |
| **Simulation passenger generation** | Two-layer demand model: real OD for covered areas, interpolation for uncovered areas |
| **Loop line topology** | Special pathfinding for circular lines, direction-aware editing |

---

## 6. Data Samples

### stations.csv (318 entries)
```
station_id, name, display_name, lines, lng, lat, is_transfer
0, Line14#45, Line14#45, , 116.335091, 39.863273, 0
15, Qilizhuang, Qilizhuang, Line14|Line9, 116.311875, 39.865, 1
100, Guomao, Guomao, Line1|Line10, 116.461, 39.909, 1
```

### od_flows.csv (~8.45M entries)
```
date, window_idx, time_range, source, target, flow
20180222, 18, 06:00-06:20, Huilongguan, Xi'erqi, 312
20180222, 18, 06:00-06:20, Tiantongyuan, Guomao, 87
```

---

## Notes

- The first run of card_analysis.py takes approximately **10 minutes**; progress is printed every 100 files
- Heatmap HTML files require an internet connection (Leaflet tiles loaded from CDN)
- `od_flows.csv` is ~391 MB — do not open directly with Excel, use Python for analysis
- Synthetic passenger demand points are generated for areas not covered by real station data, using exponential decay from city center and interpolation from nearby stations
