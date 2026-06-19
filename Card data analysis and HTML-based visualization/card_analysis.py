# -*- coding: utf-8 -*-
"""
Beijing Metro AFC Data — Individual Card Analysis (Optimized)
===============================================================
Performance optimizations for 6.48M card IDs:
  - Only analyze cards with >=3 trips (filter out occasional single riders)
  - Random sampling for clustering on very large datasets (max 50k cards)
  - Aggregate during reading to reduce memory footprint

Run: python card_analysis.py
Dependencies: pip install scikit-learn numpy
"""

import os, sys, csv, glob, json, random
from collections import defaultdict, Counter
from datetime import datetime

try:
    import numpy as np
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans, MiniBatchKMeans
    HAS_ML = True
except ImportError:
    HAS_ML = False
    print("Note: sklearn not installed, skipping clustering. pip install scikit-learn numpy")

# ========== Column indices ==========
COL_CARD     = 6
COL_FLAG     = 9
COL_LINE_IN  = 11
COL_STA_IN   = 12
COL_TIME_IN  = 13
COL_LINE_OUT = 14
COL_STA_OUT  = 15
COL_TIME_OUT = 3
COL_FARE     = 25

LINE_NAMES = {
    '1':'1号线','2':'2号线','4':'4号线','5':'5号线','6':'6号线',
    '7':'7号线','8':'8号线','9':'9号线','10':'10号线','13':'13号线',
    '14':'14号线','15':'15号线','16':'16号线','89':'大兴机场线',
    '90':'大兴线','91':'亦庄线','92':'燕房线','93':'大兴线',
    '94':'机场快轨','95':'房山线','96':'西郊线','97':'八通线','98':'S1线',
}

def line_name(code):
    return LINE_NAMES.get(str(code), f'Line_{code}')

def parse_time(s):
    if not s or len(s) < 14:
        return None
    try:
        return datetime.strptime(s.strip(), '%Y%m%d%H%M%S')
    except:
        return None

# ========== 1. Load Data ==========
def load_data():
    here = os.path.dirname(os.path.abspath(__file__))
    files = []
    for root, dirs, fnames in os.walk(here):
        for fn in fnames:
            if fn.upper().startswith('AFC_') and fn.upper().endswith('.CSV'):
                files.append(os.path.join(root, fn))
    files = sorted(files)

    if not files:
        print("❌ No AFC_*.CSV files found.")
        sys.exit(1)

    day_folders = sorted(set(os.path.basename(os.path.dirname(f)) for f in files))
    print(f"📂 Found {len(files)} files, covering {len(day_folders)} days")

    # First pass: store lightweight tuples only to save memory
    # (date_str, weekday, hour_in, min_in, sta_in, sta_out, duration, fare)
    raw = defaultdict(list)
    skipped = total = 0

    print(f"⏳ Reading ({len(files)} files)…")
    for fi, fn in enumerate(files, 1):
        if fi % 100 == 0 or fi == len(files):
            print(f"   {fi}/{len(files)} files, {total:,} valid records")
        try:
            with open(fn, encoding='utf-8', errors='ignore') as f:
                for row in csv.reader(f):
                    if len(row) < 26:
                        continue
                    if row[COL_FLAG] != '2':
                        continue
                    card = row[COL_CARD].strip()
                    if not card.isdigit():
                        continue
                    t_in  = parse_time(row[COL_TIME_IN])
                    t_out = parse_time(row[COL_TIME_OUT])
                    if not t_in or not t_out:
                        skipped += 1; continue
                    dur = (t_out - t_in).total_seconds() / 60
                    if dur < 1 or dur > 180:
                        skipped += 1; continue
                    try:
                        fare = int(row[COL_FARE])
                    except:
                        fare = 0
                    raw[card].append((
                        t_in.strftime('%Y-%m-%d'),
                        t_in.weekday(),
                        t_in.hour,
                        t_in.minute,
                        row[COL_STA_IN].strip(),
                        row[COL_STA_OUT].strip(),
                        round(dur, 1),
                        fare,
                    ))
                    total += 1
        except Exception as e:
            print(f"   ⚠️  Skipped file {os.path.basename(fn)}: {e}")

    print(f"✅ Read complete: {total:,} records, {len(raw):,} cards, {skipped:,} skipped")

    # Only keep cards with >=3 trips (filter out occasional single riders, significantly reducing analysis volume)
    trips = {c: v for c, v in raw.items() if len(v) >= 3}
    print(f"📊 Cards with >=3 trips: {len(trips):,} ({len(trips)/len(raw)*100:.1f}%), moving to further analysis")
    return trips, total, len(raw)

# ========== 2. Commuter Detection ==========
def detect_commuters(trips, min_days=4):
    commuters = {}
    n = len(trips)
    for i, (card, ts) in enumerate(trips.items()):
        if i % 200000 == 0:
            print(f"   Commuter detection progress {i:,}/{n:,}…")
        dates = set(t[0] for t in ts)
        if len(dates) < min_days:
            continue
        weekday_ts = [t for t in ts if t[1] < 5]
        if len(weekday_ts) < 2:
            continue
        od_cnt = Counter((t[4], t[5]) for t in ts)
        top_od, top_cnt = od_cnt.most_common(1)[0]
        od_ratio = top_cnt / len(ts)
        peak_am = sum(1 for t in weekday_ts if 6 <= t[2] <= 9)
        peak_pm = sum(1 for t in weekday_ts if 17 <= t[2] <= 20)
        peak_ratio = (peak_am + peak_pm) / max(len(weekday_ts), 1)
        if od_ratio >= 0.35 and peak_ratio >= 0.4:
            am_h = [t[2] + t[3]/60 for t in weekday_ts if 6 <= t[2] <= 9]
            std_am = float(np.std(am_h)) if HAS_ML and len(am_h) >= 2 else None
            commuters[card] = {
                'days': len(dates),
                'total_trips': len(ts),
                'top_od': top_od,
                'od_ratio': round(od_ratio, 2),
                'peak_ratio': round(peak_ratio, 2),
                'std_am': round(std_am, 2) if std_am is not None else None,
                'avg_duration': round(sum(t[6] for t in ts)/len(ts), 1),
                'avg_fare': round(sum(t[7] for t in ts)/len(ts)/100, 1),
            }
    return commuters

# ========== 3. Feature Extraction & Clustering (Sampling) ==========
def build_features(trips, max_sample=50000):
    cards_all = list(trips.keys())
    if len(cards_all) > max_sample:
        print(f"   Card count {len(cards_all):,}, random sampling {max_sample:,} cards for clustering…")
        random.seed(42)
        cards_all = random.sample(cards_all, max_sample)

    cards, X = [], []
    for card in cards_all:
        ts = trips[card]
        n = len(ts)
        dates = len(set(t[0] for t in ts))
        avg_tpd = n / max(dates, 1)
        hours = [t[2] + t[3]/60 for t in ts]
        avg_h = sum(hours)/n
        std_h = float(np.std(hours)) if HAS_ML else 0
        wd_r  = sum(1 for t in ts if t[1] < 5) / n
        am_r  = sum(1 for t in ts if 6 <= t[2] <= 9) / n
        pm_r  = sum(1 for t in ts if 17 <= t[2] <= 20) / n
        avg_d = sum(t[6] for t in ts) / n
        avg_f = sum(t[7] for t in ts) / n / 100
        od_c  = Counter((t[4], t[5]) for t in ts).most_common(1)[0][1] / n
        cards.append(card)
        X.append([avg_tpd, avg_h, std_h, wd_r, am_r, pm_r, avg_d, avg_f, od_c])
    return cards, X

CLUSTER_LABELS = {
    0: ('🕐 Fixed Commuters',  '#4A90D9', 'Regular morning/evening peak, fixed route, high weekday frequency'),
    1: ('🌆 Light Commuters',  '#5BB55A', 'Weekday-oriented, relatively fixed time but diverse routes'),
    2: ('🧭 Flexible Travelers',  '#F5A623', 'Scattered travel times, not concentrated in peak hours'),
    3: ('🎉 Weekend Leisure',  '#9B59B6', 'More weekend/non-workday travel, afternoon-focused'),
    4: ('🚄 Long-distance Heavy Users','#E74C3C', 'Long travel distance per trip, high fare, low frequency'),
}

def cluster_passengers(cards, X, n_clusters=5):
    if not HAS_ML or len(cards) < n_clusters:
        return {}
    Xarr = np.array(X)
    scaler = StandardScaler()
    Xs = scaler.fit_transform(Xarr)
    # Use MiniBatchKMeans — much faster than KMeans for large datasets
    km = MiniBatchKMeans(n_clusters=n_clusters, random_state=42, n_init=5, batch_size=10000)
    labels = km.fit_predict(Xs)
    centers = scaler.inverse_transform(km.cluster_centers_)
    FEAT = {'trips':0,'hour':1,'std':2,'weekday':3,'am':4,'pm':5,'dur':6,'fare':7,'conc':8}
    def score(c):
        return {
            0: c[FEAT['weekday']]*2 + c[FEAT['am']] + c[FEAT['pm']] - c[FEAT['std']] + c[FEAT['conc']],
            1: c[FEAT['weekday']] + .5*c[FEAT['am']] + .5*c[FEAT['pm']] - .5*c[FEAT['std']],
            2: -c[FEAT['am']] - c[FEAT['pm']] + c[FEAT['std']] + (1-c[FEAT['conc']]),
            3: -c[FEAT['weekday']] + (c[FEAT['hour']]-12)/12,
            4: c[FEAT['dur']]/60 + c[FEAT['fare']]/5 - c[FEAT['trips']],
        }
    assigned, used = {}, set()
    for ki in range(n_clusters):
        sc = score(centers[ki])
        for t in sorted(sc, key=lambda x: -sc[x]):
            if t not in used:
                assigned[ki] = t; used.add(t); break
        if ki not in assigned:
            assigned[ki] = ki
    return {card: {'cluster_id': int(labels[i]), 'type_id': assigned.get(int(labels[i]), int(labels[i]))}
            for i, card in enumerate(cards)}

# ========== 4. Heavy Users & Anomalies ==========
def analyze_heavy_users(trips, top_n=20):
    stats = []
    for card, ts in trips.items():
        dates = set(t[0] for t in ts)
        stats.append({
            'card': card[-4:], 'total': len(ts), 'days': len(dates),
            'avg_per_day': round(len(ts)/len(dates), 1),
            'avg_fare': round(sum(t[7] for t in ts)/len(ts)/100, 1),
            'avg_dur':  round(sum(t[6] for t in ts)/len(ts), 1),
        })
    stats.sort(key=lambda x: -x['total'])
    return stats[:top_n]

def detect_anomalies(trips):
    anomalies = []
    for card, ts in trips.items():
        by_date = defaultdict(int)
        for t in ts:
            by_date[t[0]] += 1
        max_day = max(by_date.values())
        if max_day >= 6 or len(by_date) == 7:
            anomalies.append({
                'card': card[-4:], 'total': len(ts),
                'max_per_day': max_day, 'active_days': len(by_date),
                'reason': '6+ trips in one day' if max_day >= 6 else '7 consecutive days of travel',
            })
    anomalies.sort(key=lambda x: -x['max_per_day'])
    return anomalies[:15]

# ========== 5. Statistics ==========
def compute_stats(trips, total_all, total_cards_all, commuters, cluster_map):
    total_trips = sum(len(ts) for ts in trips.values())
    hour_dist = Counter()
    weekday_cnt = weekend_cnt = 0
    fare_dist = Counter()
    dur_dist  = Counter()
    for ts in trips.values():
        for t in ts:
            hour_dist[t[2]] += 1
            if t[1] < 5: weekday_cnt += 1
            else:         weekend_cnt += 1
            if t[7] > 0:
                fare_dist[(t[7]//100)*100] += 1
            dur_dist[(int(t[6])//10)*10] += 1

    type_dist = Counter(v['type_id'] for v in cluster_map.values())
    cluster_dist = [{'type_id':k,'count':v,'label':CLUSTER_LABELS[k][0],'color':CLUSTER_LABELS[k][1]}
                    for k,v in sorted(type_dist.items())]

    return {
        'total_cards_all': total_cards_all,
        'total_cards': len(trips),
        'total_trips_all': total_all,
        'total_trips': total_trips,
        'commuter_cnt': len(commuters),
        'commuter_pct': round(len(commuters)/len(trips)*100, 1) if trips else 0,
        'weekday_cnt': weekday_cnt, 'weekend_cnt': weekend_cnt,
        'hour_data': [hour_dist.get(h,0) for h in range(24)],
        'fare_data': [[str(k//100), v] for k,v in sorted(fare_dist.items())[:12]],
        'dur_data':  [[f'{k}-{k+9}min', v] for k,v in sorted(dur_dist.items())[:13]],
        'cluster_dist': cluster_dist,
    }

def pick_commuter_examples(trips, commuters, n=6):
    examples = []
    for card, info in list(commuters.items())[:n]:
        ts = trips[card]
        am = [t for t in ts if t[1] < 5 and 6 <= t[2] <= 9]
        avg = sum(t[2]+t[3]/60 for t in am)/max(len(am),1)
        h, m = int(avg), int((avg%1)*60)
        examples.append({
            'card_tail': card[-4:],
            'days': info['days'], 'total': info['total_trips'],
            'od': f"Stn {info['top_od'][0]} → Stn {info['top_od'][1]}",
            'od_ratio': info['od_ratio'], 'peak_ratio': info['peak_ratio'],
            'avg_time': f'{h:02d}:{m:02d}',
            'avg_dur': info['avg_duration'], 'avg_fare': info['avg_fare'],
        })
    return examples

# ========== 6. HTML ==========
HTML = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Beijing Metro · Card Behavior Analysis</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700&family=JetBrains+Mono:wght@400;500&display=swap');
:root{--bg:#0d1117;--surface:#161b22;--border:#30363d;--text:#e6edf3;--text2:#8b949e;
  --accent:#58a6ff;--green:#3fb950;--orange:#f78166;--purple:#bc8cff;--yellow:#e3b341;}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:'Noto Sans SC',system-ui,sans-serif;font-size:14px;line-height:1.6}
header{background:linear-gradient(135deg,#0d1f3c,#0d1117);border-bottom:1px solid var(--border);
  padding:48px 0 40px;text-align:center;position:relative;overflow:hidden;}
header::before{content:'';position:absolute;inset:0;
  background:radial-gradient(ellipse 80% 60% at 50% 0%,rgba(88,166,255,.12),transparent 70%);}
.hero-tag{display:inline-block;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--accent);
  border:1px solid rgba(88,166,255,.4);border-radius:20px;padding:3px 12px;margin-bottom:16px;letter-spacing:.08em;}
h1{font-size:2.2rem;font-weight:700;letter-spacing:-.5px;margin-bottom:8px;}
.subtitle{color:var(--text2);font-size:.95rem}
nav{background:var(--surface);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100;
  display:flex;justify-content:center;gap:4px;padding:0 20px;}
nav a{display:inline-block;padding:10px 14px;color:var(--text2);font-size:13px;
  border-bottom:2px solid transparent;transition:all .15s;text-decoration:none;}
nav a:hover,nav a.active{color:var(--text);border-bottom-color:var(--accent);}
main{max-width:1200px;margin:0 auto;padding:32px 20px;}
section{margin-bottom:56px;}
.sec-title{font-size:.7rem;font-weight:500;letter-spacing:.12em;text-transform:uppercase;
  color:var(--text2);margin-bottom:20px;padding-bottom:8px;border-bottom:1px solid var(--border);}
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:32px;}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:20px 22px;}
.kpi-val{font-family:'JetBrains Mono',monospace;font-size:2rem;font-weight:500;color:var(--accent);line-height:1;}
.kpi-label{color:var(--text2);font-size:.82rem;margin-top:6px;}
.kpi-sub{font-family:'JetBrains Mono',monospace;font-size:.78rem;color:var(--text2);margin-top:4px;}
.charts-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:20px;margin-bottom:24px;}
.chart-box{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:20px;}
.chart-title{font-size:.82rem;font-weight:500;color:var(--text2);margin-bottom:16px;}
.cluster-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;}
.cluster-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:18px;border-left:3px solid;}
.cluster-card .name{font-size:.95rem;font-weight:500;margin-bottom:6px;}
.cluster-card .pct{font-family:'JetBrains Mono',monospace;font-size:1.5rem;font-weight:500;line-height:1;}
.cluster-card .desc{color:var(--text2);font-size:.78rem;margin-top:8px;line-height:1.5;}
.tbl-wrap{background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden;margin-bottom:20px;}
table{width:100%;border-collapse:collapse;font-size:13px;}
th{background:#1c2128;padding:10px 14px;text-align:left;font-weight:500;color:var(--text2);
  font-size:.75rem;letter-spacing:.05em;text-transform:uppercase;border-bottom:1px solid var(--border);}
td{padding:9px 14px;border-bottom:1px solid rgba(48,54,61,.5);}
tr:last-child td{border-bottom:none;}
tr:hover td{background:rgba(255,255,255,.03);}
.mono{font-family:'JetBrains Mono',monospace;font-size:12px;}
.badge{display:inline-block;padding:2px 8px;border-radius:99px;font-size:11px;font-weight:500;}
.commute-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;}
.commute-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:18px;}
.commute-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px;}
.commute-card-num{font-family:'JetBrains Mono',monospace;font-size:.8rem;color:var(--text2);}
.commute-tag{background:rgba(63,185,80,.15);color:var(--green);border:1px solid rgba(63,185,80,.3);
  border-radius:99px;padding:2px 8px;font-size:.72rem;}
.commute-od{font-family:'JetBrains Mono',monospace;font-size:.85rem;color:var(--accent);margin-bottom:10px;}
.commute-meta{display:grid;grid-template-columns:1fr 1fr;gap:6px;}
.commute-meta div{font-size:.8rem;color:var(--text2);}
.commute-meta span{color:var(--text);font-weight:500;}
footer{text-align:center;color:var(--text2);font-size:.78rem;padding:24px 0 48px;
  border-top:1px solid var(--border);margin-top:48px;}
</style></head><body>
<header>
  <div class="hero-tag">Beijing Metro 2018.02 · AFC Card Data</div>
  <h1>Individual Card Behavior Analysis</h1>
  <p class="subtitle">Reconstructing travel profiles of %%CARDS_ALL%% passengers from %%TRIPS_ALL%% card swiping records<br>
  <span style="font-size:.85rem">%%CARDS_ACTIVE%% active passengers with >=3 trips entered deep analysis</span></p>
</header>
<nav id="nav">
  <a href="#overview" class="nav-link">Overview</a>
  <a href="#pattern"  class="nav-link">Patterns</a>
  <a href="#cluster"  class="nav-link">Clusters</a>
  <a href="#commuter" class="nav-link">Commuting</a>
  <a href="#heavy"    class="nav-link">Heavy Users</a>
  <a href="#anomaly"  class="nav-link">Anomalies</a>
</nav>
<main>

<section id="overview">
  <div class="sec-title">01 · Overview</div>
  <div class="kpi-grid">
    <div class="kpi"><div class="kpi-val">%%CARDS_ALL%%</div><div class="kpi-label">Total Unique Cards</div></div>
    <div class="kpi"><div class="kpi-val">%%TRIPS_ALL%%</div><div class="kpi-label">Raw Trip Records</div></div>
    <div class="kpi"><div class="kpi-val">%%COMMUTER_CNT%%</div><div class="kpi-label">Commuting Pattern Passengers</div>
      <div class="kpi-sub">%%COMMUTER_PCT%%% of active cards</div></div>
    <div class="kpi"><div class="kpi-val">%%WEEKDAY_CNT%%</div><div class="kpi-label">Weekday Trips</div>
      <div class="kpi-sub">Weekend %%WEEKEND_CNT%%</div></div>
  </div>
</section>

<section id="pattern">
  <div class="sec-title">02 · Travel Time & Fare Patterns</div>
  <div class="charts-row">
    <div class="chart-box"><div class="chart-title">Entry Time Distribution (24h)</div>
      <canvas id="hourChart" height="180"></canvas></div>
    <div class="chart-box"><div class="chart-title">Fare Distribution (CNY)</div>
      <canvas id="fareChart" height="180"></canvas></div>
  </div>
  <div class="charts-row">
    <div class="chart-box"><div class="chart-title">Ride Duration Distribution (min)</div>
      <canvas id="durChart" height="180"></canvas></div>
    <div class="chart-box"><div class="chart-title">Weekday vs Weekend Trips</div>
      <canvas id="weekChart" height="180"></canvas></div>
  </div>
</section>

<section id="cluster">
  <div class="sec-title">03 · Passenger Clustering (K-Means, k=5, Sampled 50k cards)</div>
  <div class="cluster-grid">%%CLUSTER_CARDS%%</div>
  <p style="color:var(--text2);font-size:.82rem;margin-top:16px;">
    Features: avg trips/day, entry time mean/std, weekday ratio, AM/PM peak ratio, avg duration, avg fare, OD concentration (9D).
  </p>
</section>

<section id="commuter">
  <div class="sec-title">04 · Commuter Detection</div>
  <p style="color:var(--text2);font-size:.85rem;margin-bottom:20px;">
    Criteria: >=4 travel days · Same OD ratio >=35% · Weekday peak (6-9AM or 5-8PM) ratio >=40%
  </p>
  <div class="commute-cards">%%COMMUTE_CARDS%%</div>
</section>

<section id="heavy">
  <div class="sec-title">05 · Heavy Users Top 20</div>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Card (last 4)</th><th>7-Day Total</th><th>Active Days</th><th>Avg/Day</th><th>Avg Fare</th><th>Avg Duration</th></tr></thead>
    <tbody>%%HEAVY_ROWS%%</tbody>
  </table></div>
</section>

<section id="anomaly">
  <div class="sec-title">06 · Anomalous Individuals</div>
  <p style="color:var(--text2);font-size:.85rem;margin-bottom:16px;">>=6 trips in a single day, or 7 consecutive days of travel</p>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Card (last 4)</th><th>Total</th><th>Max/Day</th><th>Active Days</th><th>Reason</th></tr></thead>
    <tbody>%%ANOMALY_ROWS%%</tbody>
  </table></div>
</section>

</main>
<footer>Beijing Metro AFC Card Data Analysis · 2018.02 · Data anonymized</footer>

<script>
const HD=%%HOUR_DATA%%, FD=%%FARE_DATA%%, DD=%%DUR_DATA%%;
const WD=%%WEEKDAY_CNT_RAW%%, WE=%%WEEKEND_CNT_RAW%%;
function mk(id,type,labels,data,color,extra={}){
  new Chart(document.getElementById(id).getContext('2d'),{type,
    data:{labels,datasets:[{data,backgroundColor:Array.isArray(color)?color:color+'bb',
      borderColor:Array.isArray(color)?color.map(c=>c+'cc'):color,borderWidth:1,borderRadius:type==='bar'?4:0,...(extra.ds||{})}]},
    options:{responsive:true,plugins:{legend:{display:!!extra.leg,...(extra.leg||{})},
      tooltip:{callbacks:{label:c=>' '+c.raw.toLocaleString()}}},
      scales:type!=='doughnut'?{x:{grid:{color:'rgba(255,255,255,.05)'},ticks:{color:'#8b949e',font:{size:10}}},
        y:{grid:{color:'rgba(255,255,255,.05)'},ticks:{color:'#8b949e',font:{size:10},callback:v=>v>=1000?Math.round(v/1000)+'k':v}}}:{},
      ...extra.chart}});
}
mk('hourChart','bar',Array.from({length:24},(_,i)=>i+'h'),HD,
   HD.map((_,i)=>i>=6&&i<=9||i>=17&&i<=20?'#f78166bb':'#58a6ffbb'));
mk('fareChart','bar',FD.map(d=>d[0]+'CNY'),FD.map(d=>d[1]),'#3fb950');
mk('durChart','bar',DD.map(d=>d[0]),DD.map(d=>d[1]),'#bc8cff');
mk('weekChart','doughnut',['Weekday','Weekend'],[WD,WE],['#58a6ff','#f78166'],
   {leg:{display:true,position:'right',labels:{color:'#8b949e',padding:16}}});
const secs=document.querySelectorAll('section[id]'),links=document.querySelectorAll('.nav-link');
new IntersectionObserver(es=>{es.forEach(e=>{if(e.isIntersecting){
  links.forEach(l=>l.classList.remove('active'));
  const a=document.querySelector('.nav-link[href="#'+e.target.id+'"]');if(a)a.classList.add('active');}});
},{rootMargin:'-30% 0px -60% 0px'}).observe&&secs.forEach(s=>new IntersectionObserver(es=>{es.forEach(e=>{if(e.isIntersecting){links.forEach(l=>l.classList.remove('active'));const a=document.querySelector('.nav-link[href="#'+e.target.id+'"]');if(a)a.classList.add('active');}});},{rootMargin:'-30% 0px -60% 0px'}).observe(s));
</script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
</body></html>"""

def num_fmt(n):
    return f'{n/10000:.0f}M' if n >= 10000 else f'{n:,}'

def gen_html(stats, examples, heavy, anomalies):
    h = HTML
    h = h.replace('%%TRIPS_ALL%%',   num_fmt(stats['total_trips_all']))
    h = h.replace('%%CARDS_ALL%%',   num_fmt(stats['total_cards_all']))
    h = h.replace('%%CARDS_ACTIVE%%',num_fmt(stats['total_cards']))
    h = h.replace('%%COMMUTER_CNT%%',num_fmt(stats['commuter_cnt']))
    h = h.replace('%%COMMUTER_PCT%%',str(stats['commuter_pct']))
    h = h.replace('%%WEEKDAY_CNT%%', num_fmt(stats['weekday_cnt']))
    h = h.replace('%%WEEKEND_CNT%%', num_fmt(stats['weekend_cnt']))
    h = h.replace('%%HOUR_DATA%%',   json.dumps(stats['hour_data']))
    h = h.replace('%%FARE_DATA%%',   json.dumps(stats['fare_data']))
    h = h.replace('%%DUR_DATA%%',    json.dumps(stats['dur_data']))
    h = h.replace('%%WEEKDAY_CNT_RAW%%', str(stats['weekday_cnt']))
    h = h.replace('%%WEEKEND_CNT_RAW%%', str(stats['weekend_cnt']))

    cc = ''
    total = stats['total_cards']
    for cd in stats['cluster_dist']:
        pct = round(cd['count']/total*100,1)
        desc = CLUSTER_LABELS[cd['type_id']][2]
        color = CLUSTER_LABELS[cd['type_id']][1]
        cc += f'<div class="cluster-card" style="border-left-color:{color}"><div class="pct" style="color:{color}">{pct}%</div><div class="name">{cd["label"]}</div><div class="desc">{desc}</div><div style="font-family:monospace;font-size:.75rem;color:var(--text2);margin-top:8px">{cd["count"]:,} people</div></div>'
    h = h.replace('%%CLUSTER_CARDS%%', cc or '<p style="color:var(--text2)">Clustering not run (scikit-learn not installed)</p>')

    cmh = ''
    for ex in examples:
        cmh += f'''<div class="commute-card">
<div class="commute-header"><span class="commute-card-num">Card ···{ex["card_tail"]}</span><span class="commute-tag">Commuter</span></div>
<div class="commute-od">{ex["od"]}</div>
<div class="commute-meta">
  <div>Active Days <span>{ex["days"]} </span></div><div>Total Trips <span>{ex["total"]} </span></div>
  <div>Main Route % <span>{int(ex["od_ratio"]*100)}%</span></div><div>Peak Hit % <span>{int(ex["peak_ratio"]*100)}%</span></div>
  <div>Avg Entry <span>{ex["avg_time"]}</span></div><div>Avg Duration <span>{ex["avg_dur"]}  min</span></div>
</div></div>'''
    h = h.replace('%%COMMUTE_CARDS%%', cmh or '<p style="color:var(--text2)">No commuters detected.</p>')

    colors = ['#f78166','#e3b341','#58a6ff']
    hr = ''
    for i,u in enumerate(heavy):
        c = colors[min(i,2)]
        hr += f'<tr><td><span class="mono" style="color:{c}">···{u["card"]}</span></td><td class="mono">{u["total"]}</td><td class="mono">{u["days"]}</td><td class="mono">{u["avg_per_day"]}</td><td class="mono">{u["avg_fare"]}</td><td class="mono">{u["avg_dur"]}</td></tr>'
    h = h.replace('%%HEAVY_ROWS%%', hr)

    ar = ''
    for a in anomalies:
        ar += f'<tr><td><span class="mono" style="color:var(--orange)">···{a["card"]}</span></td><td class="mono">{a["total"]}</td><td class="mono" style="color:var(--orange)">{a["max_per_day"]}</td><td class="mono">{a["active_days"]}</td><td><span class="badge" style="background:rgba(247,129,102,.15);color:var(--orange)">{a["reason"]}</span></td></tr>'
    h = h.replace('%%ANOMALY_ROWS%%', ar or '<tr><td colspan="5" style="color:var(--text2);text-align:center;padding:20px">未发现异常个体</td></tr>')
    return h

# ========== Main ==========
def main():
    print('='*50)
    print('Beijing Metro AFC Card Individual Behavior Analysis (Optimized)')
    print('='*50)

    trips, total_all, total_cards_all = load_data()

    print('⏳ Detecting commuter patterns…')
    commuters = detect_commuters(trips)
    print(f'   Detected {len(commuters):,} commuters')

    cluster_map = {}
    if HAS_ML:
        print('⏳ Feature extraction & clustering…')
        cards_l, X = build_features(trips)
        cluster_map = cluster_passengers(cards_l, X)
        print(f'   Clustering complete, {len(cluster_map):,} cards classified')

    print('⏳ Computing statistics…')
    stats = compute_stats(trips, total_all, total_cards_all, commuters, cluster_map)

    examples  = pick_commuter_examples(trips, commuters)
    heavy     = analyze_heavy_users(trips)
    anomalies = detect_anomalies(trips)

    print('⏳ Generating HTML report…')
    html = gen_html(stats, examples, heavy, anomalies)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'card_analysis_report.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'✅ Done! Report saved to: {out}')

if __name__ == '__main__':
    main()
