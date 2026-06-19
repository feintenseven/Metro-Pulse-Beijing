# -*- coding: utf-8 -*-
"""
Hypothesis 01: Commute Flow Directionality
===========================================
Check whether peak-hour flows between residential and work areas
show the expected directional pattern during Spring Festival return period.

Direction 3: Whether population flow direction during specific time periods matches real Beijing commute trends

Key assumptions:
  - Morning peak (7:00-10:00): residential areas -> work areas (net positive)
  - Evening peak (17:00-20:00): work areas -> residential areas (net positive)
  - Traffic hubs show inbound surge around ChuXi (Feb 22, 2018)
"""
import csv
import os
import sys
import math
from collections import defaultdict, Counter
from datetime import datetime, timedelta

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# ======================== CONFIG ========================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, 'od_flows.csv')
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'PingFang SC', 'Noto Sans CJK SC']
plt.rcParams['axes.unicode_minus'] = False

# Time period definitions (20-min window names)
TIME_PERIODS = {
    'early_morning':  ('0500', '0700'),   # 5:00-7:00
    'morning_peak':   ('0700', '1000'),   # 7:00-10:00
    'midday':         ('1000', '1700'),   # 10:00-17:00
    'evening_peak':   ('1700', '2000'),   # 17:00-20:00
    'night':          ('2000', '2359'),   # 20:00-00:00
    'late_night':     ('0000', '0500'),   # 0:00-5:00
}

# Commuting pairs: (residential, work_area)
COMMUTE_PAIRS = [
    # Huilongguan area -> tech hub
    ('回龙观', '西二旗'), ('回龙观', '上地'), ('回龙观', '中关村'),
    ('霍营', '西二旗'), ('霍营', '上地'),
    ('龙泽', '西二旗'),
    # Tiantongyuan area -> tech hub
    ('天通苑', '西二旗'), ('天通苑', '上地'), ('天通苑', '中关村'),
    ('天通苑北', '西二旗'), ('天通苑北', '上地'),
    ('天通苑南', '西二旗'),
    # Shahe area -> tech hub
    ('沙河', '西二旗'), ('沙河高教园', '西二旗'),
    # South residential -> CBD area
    ('宋家庄', '国贸'), ('宋家庄', '大望路'),
    ('刘家窑', '国贸'), ('刘家窑', '大望路'),
    # East residential -> CBD
    ('管庄', '国贸'), ('双桥', '国贸'),
    ('传媒大学', '国贸'), ('高碑店', '国贸'),
    ('通州北苑', '国贸'), ('果园', '国贸'),
    # West -> Financial street
    ('八角游乐园', '复兴门'), ('古城路', '复兴门'),
    ('八宝山', '复兴门'), ('玉泉路', '复兴门'),
    ('五棵松', '复兴门'),
]

# Traffic hubs
TRAFFIC_HUBS = ['北京站', '北京西站', '北京南站', '北京北站']


def load_od_data():
    """Load aggregated OD flow data."""
    data = []
    with open(DATA_FILE, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data


def time_to_minutes(time_str):
    """Convert time range string like '0740-0800' to start minute of day."""
    start = time_str.split('-')[0]
    h, m = int(start[:2]), int(start[2:])
    return h * 60 + m


def time_range_to_label(time_range):
    """Convert '0740-0800' to readable label."""
    return time_range


def get_period(time_range):
    """Assign a time range to a period name."""
    t = time_to_minutes(time_range)
    for period, (start_str, end_str) in TIME_PERIODS.items():
        s = int(start_str[:2]) * 60 + int(start_str[2:])
        e = int(end_str[:2]) * 60 + int(end_str[2:])
        if s <= t < e:
            return period
    return 'late_night'  # 0000-0500


def analyze_commute_pair(data, source, target):
    """Analyze flow for a single commute pair."""
    forward = []   # source -> target (e.g., residential -> work)
    backward = []  # target -> source (work -> residential)
    for row in data:
        if row['source'] == source and row['target'] == target:
            forward.append(row)
        elif row['source'] == target and row['target'] == source:
            backward.append(row)
    return forward, backward


def compute_period_flow(rows, date=None):
    """Compute total flow grouped by time period."""
    period_flow = defaultdict(int)
    for row in rows:
        if date and row['date'] != date:
            continue
        period = get_period(row['time_range'])
        period_flow[period] += int(row['flow'])
    return dict(period_flow)


def binomial_test(n_success, n_trials, p_null=0.5):
    """
    Two-sided binomial test (using normal approximation for large n).
    Tests if observed proportion deviates from null hypothesis proportion.
    """
    if n_trials == 0:
        return 1.0, 0.0
    p_obs = n_success / n_trials
    se = math.sqrt(p_null * (1 - p_null) / n_trials)
    if se == 0:
        return 1.0, p_obs
    z = (p_obs - p_null) / se
    # Two-sided p-value from normal distribution
    p_value = 2 * (1 - normal_cdf(abs(z)))
    return p_value, p_obs


def normal_cdf(x):
    """Standard normal CDF (Abramowitz and Stegun approximation)."""
    if x < 0:
        return 1 - normal_cdf(-x)
    b0 = 0.2316419
    b1 = 0.319381530
    b2 = -0.356563782
    b3 = 1.781477937
    b4 = -1.821255978
    b5 = 1.330274429
    t = 1 / (1 + b0 * x)
    pdf = math.exp(-x * x / 2) / math.sqrt(2 * math.pi)
    return 1 - pdf * (b1 * t + b2 * t**2 + b3 * t**3 + b4 * t**4 + b5 * t**5)


# ======================== VISUALIZATIONS ========================

def plot_commute_time_series(data, source, target, dates):
    """Plot hourly flow for a specific OD pair across all dates."""
    forward, backward = analyze_commute_pair(data, source, target)

    # Aggregate by time window
    fwd_by_window = defaultdict(lambda: defaultdict(int))
    bwd_by_window = defaultdict(lambda: defaultdict(int))
    for row in forward:
        fwd_by_window[row['date']][time_to_minutes(row['time_range'])] += int(row['flow'])
    for row in backward:
        bwd_by_window[row['date']][time_to_minutes(row['time_range'])] += int(row['flow'])

    fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    fig.suptitle(f'Commute Flow: {source} → {target}  vs  {target} → {source}', fontsize=14)

    # Prepare full time axis (every 20 min)
    full_time = list(range(0, 1440, 20))

    for idx, (direction, ax, color) in enumerate([
        (f'{source} -> {target}', axes[0], '#E74C3C'),
        (f'{target} -> {source}', axes[1], '#3498DB'),
    ]):
        by_window = fwd_by_window if idx == 0 else bwd_by_window
        for date in dates:
            flows = [by_window[date].get(t, 0) for t in full_time]
            ax.plot(full_time, flows, label=date, alpha=0.8, linewidth=1.2)

        ax.set_ylabel('Flow (passengers / 20 min)')
        ax.set_title(direction, fontsize=12)
        ax.legend(fontsize=8, ncol=4)
        ax.grid(True, alpha=0.3)

        # Mark peak hours
        for peak_start, peak_end, label, color_p in [
            (420, 600, 'Morning Peak', '#E74C3C'),
            (1020, 1200, 'Evening Peak', '#3498DB'),
        ]:
            ax.axvspan(peak_start, peak_end, alpha=0.08, color=color_p, label=label if idx == 0 else '')

    axes[1].set_xlabel('Time of Day (minutes from midnight)')
    # X-axis labels
    tick_positions = list(range(0, 1440, 120))
    tick_labels = [f'{h:02d}:00' for h in range(0, 24, 2)]
    axes[1].set_xticks(tick_positions)
    axes[1].set_xticklabels(tick_labels, rotation=45)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, f'ts_{source}_{target}.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  Saved: {path}')


def plot_commute_heatmap(data, source, target):
    """Heatmap: day x time-of-day flow matrix."""
    forward, backward = analyze_commute_pair(data, source, target)

    dates = sorted(set(row['date'] for row in forward))
    windows = sorted(set(row['time_range'] for row in forward))
    window_keys = sorted(set((time_to_minutes(r['time_range']), r['time_range']) for r in forward))
    window_keys.sort()

    # Build matrix: date rows x time window cols
    fwd_matrix = np.zeros((len(dates), len(window_keys)))
    bwd_matrix = np.zeros((len(dates), len(window_keys)))
    w_keys = [w[1] for w in window_keys]

    for di, date in enumerate(dates):
        for wi, w in enumerate(w_keys):
            for row in forward:
                if row['date'] == date and row['time_range'] == w:
                    fwd_matrix[di, wi] = int(row['flow'])
            for row in backward:
                if row['date'] == date and row['time_range'] == w:
                    bwd_matrix[di, wi] = int(row['flow'])

    fig, axes = plt.subplots(2, 1, figsize=(16, 8), sharex=True)
    fig.suptitle(f'Flow Heatmap: {source} ↔ {target}', fontsize=14)

    for idx, (matrix, direction, ax, cmap) in enumerate([
        (fwd_matrix, f'{source} → {target}', axes[0], 'Oranges'),
        (bwd_matrix, f'{target} → {source}', axes[1], 'Blues'),
    ]):
        im = ax.imshow(matrix, aspect='auto', cmap=cmap, interpolation='nearest')
        ax.set_yticks(range(len(dates)))
        ax.set_yticklabels([d[4:6] + '/' + d[6:8] for d in dates])
        ax.set_title(direction, fontsize=11)
        plt.colorbar(im, ax=ax, shrink=0.8)

    # X labels: show every 3rd window (hourly)
    tick_interval = 3  # every hour (3 x 20min)
    axes[1].set_xticks(range(len(w_keys))[::tick_interval])
    axes[1].set_xticklabels([w_keys[i] for i in range(0, len(w_keys), tick_interval)], rotation=45, fontsize=8)
    axes[1].set_xlabel('Time Window')

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, f'heatmap_{source}_{target}.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  Saved: {path}')


def plot_morning_peak_directionality(data, pairs, dates):
    """Bar chart comparing morning peak forward vs backward flow for each pair."""
    periods_to_check = ['morning_peak', 'evening_peak']
    results = {p: [] for p in periods_to_check}

    for source, target in pairs:
        forward, backward = analyze_commute_pair(data, source, target)
        for period_name in periods_to_check:
            fwd_sum = sum(int(r['flow']) for r in forward if get_period(r['time_range']) == period_name)
            bwd_sum = sum(int(r['flow']) for r in backward if get_period(r['time_range']) == period_name)
            results[period_name].append({
                'pair': f'{source}\n→\n{target}',
                'label': f'{source}→{target}',
                'forward': fwd_sum,
                'backward': bwd_sum,
                'ratio': fwd_sum / max(bwd_sum, 1),
            })

    # Filter out pairs with zero flow
    for period_name in periods_to_check:
        valid = [r for r in results[period_name] if r['forward'] + r['backward'] > 50]
        if not valid:
            continue

        fig, ax = plt.subplots(figsize=(max(10, len(valid) * 0.8), 6))
        labels = [r['pair'] for r in valid]
        x = np.arange(len(labels))
        width = 0.35

        fwd_vals = [r['forward'] for r in valid]
        bwd_vals = [r['backward'] for r in valid]

        bars1 = ax.bar(x - width/2, fwd_vals, width, label=f'{period_name}: residential→work', color='#E74C3C', alpha=0.85)
        bars2 = ax.bar(x + width/2, bwd_vals, width, label=f'{period_name}: work→residential', color='#3498DB', alpha=0.85)

        ax.set_ylabel('Total flow')
        period_label = 'Morning Peak (7:00-10:00)' if 'morning' in period_name else 'Evening Peak (17:00-20:00)'
        ax.set_title(f'{period_label} Commute Directionality (All Days)', fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=7, rotation=45, ha='center')
        ax.legend(fontsize=9)
        ax.grid(axis='y', alpha=0.3)

        # Add ratio annotations
        for i, r in enumerate(valid):
            ratio = r['forward'] / max(r['backward'], 1)
            ax.annotate(f'{ratio:.1f}x', (x[i], max(fwd_vals[i], bwd_vals[i])),
                       ha='center', va='bottom', fontsize=7, fontweight='bold',
                       color='#2C3E50')

        plt.tight_layout()
        path = os.path.join(OUTPUT_DIR, f'directionality_{period_name}.png')
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f'  Saved: {path}')


def plot_daily_ratio_trend(data, pairs, dates):
    """Plot forward/backward ratio trend across days for key pairs."""
    fig, ax = plt.subplots(figsize=(12, 6))

    # Pick top 5 pairs by total flow
    pair_totals = []
    for s, t in pairs:
        fwd, bwd = analyze_commute_pair(data, s, t)
        total = sum(int(r['flow']) for r in fwd) + sum(int(r['flow']) for r in bwd)
        pair_totals.append(((s, t), total))
    pair_totals.sort(key=lambda x: -x[1])

    colors = plt.cm.Set1(np.linspace(0, 1, 5))
    for idx, ((s, t), _) in enumerate(pair_totals[:5]):
        fwd, bwd = analyze_commute_pair(data, s, t)
        ratios = []
        for date in dates:
            fwd_peak = sum(int(r['flow']) for r in fwd
                          if r['date'] == date and get_period(r['time_range']) == 'morning_peak')
            bwd_peak = sum(int(r['flow']) for r in bwd
                          if r['date'] == date and get_period(r['time_range']) == 'morning_peak')
            ratio = fwd_peak / max(bwd_peak, 1)
            ratios.append(ratio)
        ax.plot(dates, ratios, marker='o', label=f'{s}→{t}', color=colors[idx], linewidth=2)

    ax.axhline(y=1.0, color='gray', linestyle='--', alpha=0.5, label='Equal (ratio=1)')
    ax.set_ylabel('Morning Peak Forward/Backward Ratio')
    ax.set_title('Daily Trend: Commute Directionality Ratio (Morning Peak)', fontsize=13)
    ax.set_xticks(dates)
    ax.set_xticklabels([d[4:6] + '/' + d[6:8] for d in dates])
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'daily_ratio_trend.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  Saved: {path}')


def plot_total_flow_by_date(data):
    """Plot overall daily flow to see traffic recovery trend."""
    date_flow = defaultdict(int)
    with open(DATA_FILE, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_flow[row['date']] += int(row['flow'])

    dates = sorted(date_flow.keys())
    flows = [date_flow[d] for d in dates]
    labels = [f'{d[4:6]}/{d[6:8]}' for d in dates]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(labels, flows, color=['#E74C3C', '#E67E22', '#F1C40F', '#2ECC71', '#1ABC9C', '#3498DB', '#9B59B6'],
                  alpha=0.85)
    ax.set_ylabel('Total Daily Flow (millions)')
    ax.set_title('Overall Daily Metro Flow (Feb 22-28, 2018)', fontsize=13)
    ax.grid(axis='y', alpha=0.3)

    # Add value labels
    for bar, v in zip(bars, flows):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(flows)*0.01,
                f'{v/1e6:.1f}M', ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'daily_total_flow.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  Saved: {path}')

    return date_flow


def plot_morning_peak_comparison(data, dates):
    """Compare top residential -> work flows in morning peak across days."""
    # Aggregate morning peak flow for all commute pairs
    pair_flows = defaultdict(lambda: defaultdict(int))
    for s, t in COMMUTE_PAIRS:
        for row in data:
            if row['source'] == s and row['target'] == t:
                period = get_period(row['time_range'])
                if period == 'morning_peak':
                    pair_flows[(s, t)][row['date']] += int(row['flow'])

    # Top 8 pairs
    totals = [(p, sum(d.values())) for p, d in pair_flows.items()]
    totals.sort(key=lambda x: -x[1])
    top_pairs = [p for p, _ in totals[:8]]

    fig, ax = plt.subplots(figsize=(12, 6))
    dates_sorted = sorted(dates)
    x = np.arange(len(dates_sorted))
    width = 0.1

    for idx, (s, t) in enumerate(top_pairs):
        vals = [pair_flows[(s, t)][d] for d in dates_sorted]
        bars = ax.bar(x + idx * width, vals, width, label=f'{s}→{t}')

    ax.set_xticks(x + width * (len(top_pairs) - 1) / 2)
    ax.set_xticklabels([d[4:6] + '/' + d[6:8] for d in dates_sorted])
    ax.set_ylabel('Morning Peak Flow (7:00-10:00)')
    ax.set_title('Top Commute Flows in Morning Peak by Day', fontsize=13)
    ax.legend(fontsize=8, ncol=2)
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'top_commute_morning_peak.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  Saved: {path}')


# ======================== STATISTICAL TESTS ========================

def run_binomial_tests(data, pairs, dates):
    """
    For each commute pair, test if morning peak forward flow > backward flow
    using a binomial test: H0: proportion_forward <= 0.5
    """
    print('\n' + '=' * 70)
    print('BINOMIAL TEST RESULTS: Morning Peak Directionality')
    print('H0: p(forward) <= 0.5  (residential->work is NOT dominant)')
    print('H1: p(forward) > 0.5   (residential->work IS dominant)')
    print('=' * 70)

    results = []
    for source, target in pairs:
        forward, backward = analyze_commute_pair(data, source, target)

        fwd_peak = sum(int(r['flow']) for r in forward
                      if get_period(r['time_range']) == 'morning_peak')
        bwd_peak = sum(int(r['flow']) for r in backward
                      if get_period(r['time_range']) == 'morning_peak')
        total_peak = fwd_peak + bwd_peak

        if total_peak < 10:
            continue  # skip pairs with too few observations

        p_value, p_obs = binomial_test(fwd_peak, total_peak, 0.5)
        reject = p_value < 0.05
        direction = 'DOMINANT' if reject and p_obs > 0.5 else 'not significant'
        if p_obs > 0.5 and p_value < 0.05:
            direction = f'Residential→Work dominant (p_forward={p_obs:.3f})'
        elif p_obs < 0.5 and p_value < 0.05:
            direction = f'Work→Residential dominant (p_forward={p_obs:.3f})'
        else:
            direction = f'No significant directionality (p_forward={p_obs:.3f})'

        results.append({
            'pair': f'{source} → {target}',
            'forward': fwd_peak,
            'backward': bwd_peak,
            'total': total_peak,
            'p_forward': p_obs,
            'p_value': p_value,
            'reject': reject,
            'direction': direction,
        })
        print(f'  {source:10s} → {target:10s}  '
              f'fwd={fwd_peak:>5d}  bwd={bwd_peak:>5d}  '
              f'p_forward={p_obs:.3f}  p={p_value:.4f}  {direction}')

    # Summary stats
    n_tested = len(results)
    n_reject = sum(1 for r in results if r['reject'] and r['p_forward'] > 0.5)
    print(f'\nSummary: {n_reject}/{n_tested} commute pairs show significant '
          f'residential→work dominance in morning peak')

    return results


def run_morning_evening_contrast(data, pairs, dates):
    """
    Contrast: morning peak should show net residential->work flow,
    evening peak should show net work->residential flow.
    """
    print('\n' + '=' * 70)
    print('MORNING vs EVENING PEAK CONTRAST')
    print('=' * 70)

    results = []
    for source, target in pairs:
        forward, backward = analyze_commute_pair(data, source, target)

        # Morning peak
        fwd_morning = sum(int(r['flow']) for r in forward
                         if get_period(r['time_range']) == 'morning_peak')
        bwd_morning = sum(int(r['flow']) for r in backward
                         if get_period(r['time_range']) == 'morning_peak')

        # Evening peak
        fwd_evening = sum(int(r['flow']) for r in forward
                         if get_period(r['time_range']) == 'evening_peak')
        bwd_evening = sum(int(r['flow']) for r in backward
                         if get_period(r['time_range']) == 'evening_peak')

        # Net flow (positive = net residential->work)
        net_morning = fwd_morning - bwd_morning
        net_evening = fwd_evening - bwd_evening  # positive means more residential->work even in evening

        if fwd_morning + bwd_morning + fwd_evening + bwd_evening < 20:
            continue

        ratio_morning = fwd_morning / max(bwd_morning, 1)
        ratio_evening = bwd_evening / max(fwd_evening, 1)  # work->residential ratio

        valid_contrast = (net_morning > 0 and net_evening < 0)  # expected pattern

        results.append({
            'pair': f'{source}→{target}',
            'net_morning': net_morning,
            'net_evening': net_evening,
            'ratio_morning': f'{ratio_morning:.1f}x',
            'ratio_evening': f'{ratio_evening:.1f}x',
            'valid_contrast': valid_contrast,
        })

        status = 'CORRECT' if valid_contrast else 'WRONG'
        print(f'  {source:10s} → {target:10s}  '
              f'morning_net={net_morning:+5d}  evening_net={net_evening:+5d}  '
              f'morning_ratio={ratio_morning:.1f}x  evening_reverse_ratio={ratio_evening:.1f}x  [{status}]')

    valid_count = sum(1 for r in results if r['valid_contrast'])
    print(f'\nSummary: {valid_count}/{len(results)} pairs show the expected '
          f'morning->evening flow reversal pattern')
    return results


def plot_evening_peak_directionality(data, pairs, dates):
    """Plot evening peak directionality separately."""
    results = []
    for source, target in pairs:
        forward, backward = analyze_commute_pair(data, source, target)

        fwd_eve = sum(int(r['flow']) for r in forward
                     if get_period(r['time_range']) == 'evening_peak')
        bwd_eve = sum(int(r['flow']) for r in backward
                     if get_period(r['time_range']) == 'evening_peak')

        if fwd_eve + bwd_eve < 50:
            continue

        results.append({
            'pair': f'{source}\n→\n{target}',
            'fwd_eve': fwd_eve,
            'bwd_eve': bwd_eve,
        })

    if not results:
        return

    fig, ax = plt.subplots(figsize=(max(10, len(results) * 0.8), 6))
    x = np.arange(len(results))
    width = 0.35

    fwd_vals = [r['fwd_eve'] for r in results]
    bwd_vals = [r['bwd_eve'] for r in results]
    labels = [r['pair'] for r in results]

    ax.bar(x - width/2, fwd_vals, width, label='work→residential', color='#E74C3C', alpha=0.85)
    ax.bar(x + width/2, bwd_vals, width, label='residential→work', color='#3498DB', alpha=0.85)

    ax.set_ylabel('Total flow')
    ax.set_title('Evening Peak (17:00-20:00) Flow Directionality (All Days)', fontsize=12)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7, rotation=45, ha='center')
    ax.legend(fontsize=9)
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'directionality_evening_peak.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  Saved: {path}')


# ======================== MAIN ========================

def main():
    print('Loading OD data...')
    data = load_od_data()
    dates = sorted(set(r['date'] for r in data))
    print(f'Loaded {len(data)} records across {len(dates)} days: {dates}')

    # 1. Overall daily flow
    print('\n--- Overall Daily Flow ---')
    date_flow = plot_total_flow_by_date(data)

    # 2. Key commute pair time series
    print('\n--- Commute Time Series ---')
    key_pairs = [
        ('回龙观', '西二旗'),
        ('天通苑', '西二旗'),
        ('沙河', '西二旗'),
        ('宋家庄', '国贸'),
        ('管庄', '国贸'),
        ('五棵松', '复兴门'),
    ]
    for s, t in key_pairs:
        plot_commute_time_series(data, s, t, dates)
        plot_commute_heatmap(data, s, t)

    # 3. Morning peak directionality bar chart
    plot_morning_peak_directionality(data, COMMUTE_PAIRS, dates)
    plot_evening_peak_directionality(data, COMMUTE_PAIRS, dates)

    # 4. Daily trend
    plot_daily_ratio_trend(data, key_pairs, dates)

    # 5. Top commute comparison
    plot_morning_peak_comparison(data, dates)

    # 6. Statistical tests
    binom_results = run_binomial_tests(data, COMMUTE_PAIRS, dates)
    contrast_results = run_morning_evening_contrast(data, COMMUTE_PAIRS, dates)

    # 7. Print conclusion
    print('\n' + '=' * 70)
    print('CONCLUSION')
    print('=' * 70)
    n_sig = sum(1 for r in binom_results if r['reject'] and r['p_forward'] > 0.5)
    n_valid_contrast = sum(1 for r in contrast_results if r['valid_contrast'])
    n_total = len(binom_results)

    print(f'\nHypothesis: During Spring Festival return period (Feb 22-28),')
    print(f'  morning peak flow from residential to work areas should be')
    print(f'  significantly greater than the reverse direction.')
    print(f'\nResults:')
    print(f'  - Binomial test: {n_sig}/{n_total} pairs show significant dominance')
    print(f'  - Morning-evening contrast: {n_valid_contrast}/{len(contrast_results)} pairs show expected reversal')
    print(f'\nOverall: ', end='')

    if n_sig / max(n_total, 1) > 0.7 and n_valid_contrast / max(len(contrast_results), 1) > 0.5:
        print('  STRONG EVIDENCE: Commute flow directionality pattern is confirmed.')
        print('  The data is consistent with real Beijing commute patterns.')
    elif n_sig / max(n_total, 1) > 0.4:
        print('  MODERATE EVIDENCE: Some directional patterns observed,')
        print('  but not uniformly across all commute pairs.')
    else:
        print('  WEAK EVIDENCE: Commute flow directionality not clearly observed.')
        print('  Data may have issues, or the Spring Festival period affects patterns.')

    print(f'\nAll figures saved to: {OUTPUT_DIR}')


if __name__ == '__main__':
    main()
