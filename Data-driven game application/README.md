# Beijing Metro Route Builder Simulator

**Interactive Metro Network Planning & Operations Simulation**

An interactive, single-page web application for designing metro networks, simulating passenger operations, and receiving performance evaluations — all powered by real Beijing Metro AFC (Automatic Fare Collection) data from February 2018.

> **File:** `beijing_metro_game.html` — a fully self-contained single-page application

---

## Overview

This module is the interactive simulation system for the Beijing Metro data analysis project. Built on top of real passenger flow data from the project's first two stages (data parsing and graph construction), it provides a complete metro network planning and operations simulation environment with three core functions:

1. **Network Planning** — Design metro routes on a real geographic map
2. **Real-time Operations Feedback** — Monitor passenger flow, congestion, and complaints
3. **Evaluation & Adjustment** — Receive a comprehensive rating after each simulated day and refine your network

The application is a fully self-contained HTML file — no backend server required. It can run by simply double-clicking the file in any modern browser. After loading, click the **Start Game** button to begin.

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Base Map | Leaflet 1.9.4 with CARTO light tile layer |
| Heatmap | leaflet.heat plugin — demand intensity visualization |
| Rendering | Canvas overlay on Leaflet — draws routes, stations, trains, waiting passengers, and hover info |
| Data | Inline JavaScript constants: `STATIONS`, `EDGES`, `LAMBDA`, `DEST` |
| Simulation Engine | Pure JavaScript, frame-by-frame via `requestAnimationFrame` |
| Dependencies | Leaflet JS/CSS (CDN), leaflet.heat (CDN) — all loaded at runtime, no install needed |

### UI Layout

| Element | Position | Description |
|---------|----------|-------------|
| **HUD** (Heads-Up Display) | Top-left | Current clock, rating (1–5 stars), review count, passengers served, currently waiting, service rate, number of lines |
| **Controls** | Bottom-left | Build, Run, New Line, Close Loop, Undo, Append/Prepend, Heatmap toggle, Speed control, Reset |
| **Lines Panel** | Top-right | List of all lines with color indicators; select a line to edit, rename, add/remove trains, or delete |
| **Coverage Slider** | Bottom-left | Adjust station coverage radius (400–2500m) |
| **Toast Notifications** | Top-center | Pop-up feedback when complaints or praise occur |

---

## 1. Data Foundation

The application uses four structured data constants derived from the earlier stages of the project:

| Constant | Description |
|----------|-------------|
| `STATIONS` | ~318 real Beijing Metro stations with name, coordinates (`lng`/`lat`), line membership, transfer flag (`tr`), and daily passenger volume (`g`) |
| `EDGES` | Topological adjacency edges between stations (connected pairs and their line) — used to draw the real metro network as a base layer |
| `LAMBDA` | Per-station entry intensity curve: each station has a 72-point curve dividing a day into 72 time slots, recording entry intensity for each slot |
| `DEST` | Per-station OD (Origin-Destination) distribution: passengers departing from each station are probabilistically assigned to destination stations based on real flow data |

### Synthetic Passenger Demand

Areas not covered by real station data (suburbs, undeveloped areas) receive synthetic demand points:

- Generated on a grid across the map area
- Intensity follows an **exponential decay from city center**: `1000 + 2600 × e^(-distance_from_center / 20)`, with random perturbation
- Synthetic points too close to a real station are filtered to avoid double-counting
- Each synthetic point borrows OD distribution from nearby real stations, weighted by inverse square of distance

This ensures the simulation has non-zero demand across the entire map, not just at stations with real data.

---

## 2. Network Planning

### 2.1 Heatmap-Assisted Site Selection

Click **"Demand Heatmap"** to overlay a heatmap showing daily passenger volume across stations:
- **Blue** → Low demand
- **Green** → Medium demand
- **Orange** → High demand
- **Red** → Very high demand

Passenger volumes are compressed by a 0.6 power to prevent a few mega-stations from washing out the rest, making it easier to identify demand clusters.

### 2.2 Placing Stations and Connecting Lines

Click **"Build"** to enter build mode, then click on the map to place stations:

| Action | Result |
|--------|--------|
| Click on empty area | Creates a new station, added to the end of the current line |
| Click near an existing station (within 16px on screen) | Connects to that station, creating a **transfer** hub |
| Click the start station of the line | **Closes the loop**, making it a circular line |

After connecting two stations, the system **automatically deploys the first train** on the newly created line.

### 2.3 Editing Existing Lines

Select a line from the **"Lines"** panel (right side of screen):

| Action | Button | Description |
|--------|--------|-------------|
| Extend | (click on map) | Add stations to the currently selected line along its direction |
| Toggle append mode | **Append / Prepend** | Switch between adding stations to the tail or head of the line |
| Undo | **Undo** | Remove the last station added (also works to un-close a loop) |
| Delete line | **×** (per-line) | Remove the entire line and its trains |
| Rename | (click name) | Edit the line name directly |
| Change color | (color picker) | Change the line's display color |
| Add train | **+** | Deploy an additional train on the line (increases capacity, reduces wait time) |
| Remove train | **−** | Remove a train from the line |

### 2.4 Coverage Zones & Passenger Assignment

Each user-placed station has a **coverage radius** (adjustable via slider: 400–2500 meters, default 1000m):

- Every demand point (real or synthetic) is assigned to the **nearest station within its radius**
- Passengers at that demand point board from its assigned station
- Demand points **not covered** by any station become **latent demand**, shown as gray dots on the map
- Latent demand slowly decays over time, indicating unmet needs

> Larger radius = more coverage, but may miss critical demand clusters if stations are poorly placed.

---

## 3. Real-Time Operations Simulation

Click **"Run"** to start simulation. The clock starts at 06:00 and one "day" compresses to ~160 seconds of real time. Speed can be adjusted to 1×, 2×, or 4×.

### 3.1 Passenger Flow

The complete passenger lifecycle in the simulation:

1. **Generation** — Passengers are generated at each station according to the current time slot's `LAMBDA` intensity (cumulative probability)
2. **Destination Assignment** — Each passenger's destination is randomly drawn from the station's `DEST` distribution
3. **Reachability Check** — If the origin and destination are connected in the current network, the passenger queues at the origin station; otherwise they are counted as lost
4. **Boarding** — When a train arrives, passengers board if the optimal route uses this line; full trains (capacity: 10) cause passengers to wait for the next train
5. **Travel & Transfer** — Passengers ride to their destination or transfer at intermediate stations; the routing algorithm determines the best path
6. **Arrival** — Passengers reaching their destination are counted as **served**
7. **Give Up** — Passengers waiting longer than the limit (22 simulated seconds) leave the queue and are counted as lost

### 3.2 Train Movement

- Trains move along line segments at a fixed speed (3000m per simulation second)
- On reaching a station, trains **dwell** briefly before proceeding to the next segment
- **Non-loop lines**: trains reverse direction at the terminus
- **Loop lines**: trains cycle continuously
- **Multiple trains**: adding more trains to a line automatically spaces their intervals, effectively increasing frequency and reducing wait times

### 3.3 Complaint & Praise System

The system monitors operational quality in real time. When issues occur, passengers generate **complaints** that decrease the station's rating, accompanied by a pop-up notification:

| Complaint Type | Trigger Condition | Meaning |
|----------------|-------------------|---------|
| 🚇 **Crowded** | Queue at a station exceeds threshold (12 people) for extended time | Platform overcrowding, difficulty boarding |
| ⏱ **Slow** | Passenger waits too long and gives up | Headway too long, insufficient capacity |
| 🔄 **Detour** | Actual travel distance far exceeds straight-line distance | Route is excessively indirect |
| 🔀 **Transfer** | Single passenger transfers 2 or more times | Too many transfers needed |
| ❌ **Miss** | Destination has no station coverage | Critical demand point has no station |
| 📏 **Far** | Distance between two adjacent stations is too large | Station spacing excessive |

**Positive feedback** occurs when passengers have a smooth, fast trip, generating **praise** that slightly recovers the rating. The rating also slowly recovers over time naturally.

### 3.4 Real-Time HUD Metrics

| Metric | Description |
|--------|-------------|
| ⏰ **Clock** | Current simulation time |
| ⭐ **Rating** | 1–5 stars based on overall service quality |
| 💬 **Bad Reviews** | Cumulative complaint count |
| ✅ **Served** | Passengers successfully delivered |
| ⏳ **Waiting** | Passengers currently queued at stations |
| 📊 **Service Rate** | Served ÷ (Served + Lost) |
| 🚄 **Lines** | Number of metro lines in the network |

---

## 4. Evaluation & Adjustment

At the end of each simulated day, the system displays an **End-of-Day Evaluation Panel** with a comprehensive rating and detailed metrics.

### 4.1 Score Calculation

```
Total Score = Service Rate × 70 + min(1, Served / 600) × 15 + (Rating / 5) × 15
```

Range: 0–100

| Score | Grade | Description |
|-------|-------|-------------|
| ≥90 | **S** | Excellent — overall outstanding performance |
| 78–89 | **A** | Good — solid network performance |
| 66–77 | **B** | Acceptable — peak hours are tight |
| 52–65 | **C** | Below standard — service quality issues |
| <52 | **D** | Failing — network design clearly unreasonable |

**Weighting rationale:**
- **Service Rate (70%)** — whether passengers who need to travel are actually delivered; this is the primary metric
- **Throughput (15%)** — total volume served, capped at 600 per day
- **Passenger Rating (15%)** — overall satisfaction from complaints and praise

### 4.2 Evaluation Panel Details

The panel displays:
- **Grade & Score** — Overall rating for the day
- **Service Rate** — Percentage of passengers successfully delivered
- **Served / Overflow** — Passengers delivered vs. those who gave up
- **Avg Wait Time** — Average passenger wait time
- **Likes / Dislikes** — Count of positive and negative reviews
- **Complaint Breakdown** — Counts by type: crowded, slow, detour, transfer, miss, far
- **Uncovered Demand** — Total latent/unmet demand

### 4.3 Post-Evaluation Options

| Button | Action |
|--------|--------|
| **Continue ▶** | Proceed to the next day — simulation continues with current network |
| **Adjust Lines** | Return to build/edit mode to modify the network |

---

## 5. Core Algorithms

Three algorithms run whenever the network is modified and are queried repeatedly during simulation:

### 5.1 Shortest Path with Transfer Penalty (Routing)

Passenger routing is solved on a **state graph** where each state is a (station, line) pair:

- **Same line, adjacent stations**: edge weight = 1 (cost of riding one stop)
- **Same station, different lines**: edge weight = `TPEN` = 4 (cost of one transfer)

A Dijkstra search is performed from each destination station, producing a lookup table (`optLine`) that tells any passenger at any station which line to take next to reach the destination, and a reachability table (`reachA`).

Since the transfer penalty (4) is much larger than riding one stop (1), the routing algorithm naturally favors fewer-transfer routes — which also aligns with the "too many transfers" complaint detection.

### 5.2 Coverage Assignment

For each demand point (real or synthetic):
1. Scan all operational user-placed stations
2. Find the nearest station **within that station's coverage radius**
3. Assign the demand point (and its time-sliced passenger volume) to that station
4. Demand points not within any station's radius become **latent demand**

This recalculation runs automatically whenever the network or coverage radius changes.

### 5.3 Simulation Main Loop

Each animation frame advances the simulation clock:

1. **Generate passengers** — For each station, generate passengers per its LAMBDA intensity for the current time slot
2. **Move trains** — Advance each train along its line; when a train reaches a station, process boarding/alighting
3. **Check congestion** — Evaluate queue lengths at each station for overcrowding complaints
4. **Check wait timeouts** — Remove passengers who have exceeded the maximum wait time
5. **Update rating** — Recalculate rating based on complaints and praise accumulated this frame

Time is tracked in absolute simulated seconds, allowing wait times, detour distances, and other metrics to accumulate across frames.

---

## 6. Key Parameters

These constants in the code control the behavior of the simulation:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DAY` | 160 | One simulation day in real seconds |
| `CAP` | 10 | Maximum passengers per train |
| `TPEN` | 4 | Transfer penalty (equivalent to riding 4 stops) |
| `R` (Range) | 1000 m | Station coverage radius (adjustable 400–2500 m) |
| `THRESH` | 12 | Queue size threshold for "crowded" complaint |
| `WAIT_LIMIT` | 22 | Max passenger wait time before giving up (simulated seconds) |
| `SCALE` | 0.007 | Global passenger intensity scaling factor |
| `TRAIN_MPS` | 3000 | Train speed (meters per simulated second) |

---

## Quick Start

1. **Open the file** — Double-click `beijing_metro_game.html` in any modern browser (Chrome, Firefox, Edge recommended)
2. **Start** — Click **Start Game** on the welcome screen
3. **Build a network** — Click **Build**, then click on the map to place stations and connect them into lines
4. **Check demand** — Use **Demand Heatmap** to see where passenger demand is concentrated
5. **Run simulation** — Click **Run** to see your network in operation
6. **Review & refine** — At the end of each day, review the evaluation panel and click **Adjust Lines** to improve your network

---

## Project Context

This simulation is the final phase of a larger Beijing Metro data analysis project:

- **Phase 1** — Parse raw AFC CSV files, interpret field meanings, cross-validate
- **Phase 2** — Extract origin-destination records, build a weighted directed graph, aggregate by station and time period
- **Phase 3** *(this module)* — Interactive web-based simulation system for route planning and operations evaluation
