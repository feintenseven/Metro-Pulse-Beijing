"""
Transport Hub Heatmap Generation Script
=========================================
For each hub station (Beijing Station, Beijing West, Beijing South, T2 Terminal, T3 Terminal),
generate two heatmaps:
  1. Outflow heatmap — flow distribution from the hub to various destinations
  2. Inflow heatmap — flow distribution from various stations arriving at the hub

Data source: _hub_destinations.json (outflow), _hub_flow_data.json (inflow)
Output: two .html files per station, 10 total
"""

import json
import os
import folium
from folium.plugins import HeatMap
from branca.colormap import linear

# ── Path configuration ───────────────────────────────────────────
BASE_DIR = r"C:\Users\YF\Desktop\dataset\data"
OUTPUT_DIR = os.path.join(BASE_DIR, "heatmaps")

DEST_FILE = os.path.join(BASE_DIR, "_hub_destinations.json")
FLOW_FILE = os.path.join(BASE_DIR, "_hub_flow_data.json")
COORDS_FILE = os.path.join(BASE_DIR, "_dest_stations_coords.json")

# Hub stations and their coordinates (for map centering)
HUBS = {
    "北京站": {"lng": 116.427, "lat": 39.903, "label": "北京站"},
    "北京西站": {"lng": 116.322, "lat": 39.895, "label": "北京西站"},
    "北京南站": {"lng": 116.378, "lat": 39.865, "label": "北京南站"},
    "T2航站楼": {"lng": 116.538, "lat": 40.005, "label": "T2航站楼"},
    "T3航站楼": {"lng": 116.62, "lat": 40.049, "label": "T3航站楼"},
}

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Load data ────────────────────────────────────────────────────
with open(DEST_FILE, "r", encoding="utf-8") as f:
    outflow_data = json.load(f)  # hub -> [{dest, flow, lng, lat}, ...]

with open(FLOW_FILE, "r", encoding="utf-8") as f:
    inflow_data = json.load(f)  # hub -> {dest: flow, ...}

with open(COORDS_FILE, "r", encoding="utf-8") as f:
    coords_data = json.load(f)  # station -> {lng, lat, display, lines}


def make_heatmap(center, points, title, filename, color_scheme="YlOrRd"):
    """
    Generate a heatmap HTML file.

    Parameters
    - center: (lat, lng) map center
    - points: [(lat, lng, weight), ...] heatmap points
    - title: chart title
    - filename: output file path
    """
    # Find weight range for color scale
    weights = [p[2] for p in points]
    w_min, w_max = min(weights), max(weights)

    # Create map — using OpenStreetMap tiles
    m = folium.Map(
        location=center,
        zoom_start=11,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    # Add heatmap layer
    # radius / blur control heat spread radius, tuned for city scale
    HeatMap(
        points,
        radius=20,
        blur=15,
        max_zoom=12,
        min_opacity=0.3,
        max_opacity=0.85,
        gradient={
            0.4: "blue",
            0.6: "lime",
            0.8: "orange",
            1.0: "red",
        },
    ).add_to(m)

    # Add color legend (bottom right)
    colormap = linear.YlOrRd_09.scale(w_min, w_max)
    colormap.caption = "Flow (passengers / 7 days)"
    colormap.add_to(m)

    # Add title HTML overlay
    title_html = f'''
    <div style="
        position: fixed; top: 10px; left: 50%; transform: translateX(-50%);
        z-index: 9999; background: white; padding: 8px 24px;
        border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        font-size: 18px; font-weight: bold; font-family: sans-serif;
    ">{title}</div>
    '''
    m.get_root().html.add_child(folium.Element(title_html))

    m.save(filename)
    return m


def make_heatmap_with_base_marker(center_base, points, title, filename,
                                   base_label="Hub Station"):
    """Place a marker at the hub station coordinate and generate a heatmap"""
    weights = [p[2] for p in points]
    if not weights:
        print(f"  [WARN] No data, skipping: {os.path.basename(filename)}")
        return None
    w_min, w_max = min(weights), max(weights)

    m = folium.Map(
        location=center_base,
        zoom_start=11,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    HeatMap(
        points,
        radius=20,
        blur=15,
        max_zoom=12,
        min_opacity=0.3,
        max_opacity=0.85,
        gradient={
            0.4: "blue",
            0.6: "lime",
            0.8: "orange",
            1.0: "red",
        },
    ).add_to(m)

    # Add marker at hub location
    folium.Marker(
        location=(center_base[0], center_base[1]),
        popup=base_label,
        tooltip=base_label,
        icon=folium.Icon(color="red", icon="info-sign"),
    ).add_to(m)

    colormap = linear.YlOrRd_09.scale(w_min, w_max)
    colormap.caption = "Flow (passengers / 7 days)"
    colormap.add_to(m)

    title_html = f'''
    <div style="
        position: fixed; top: 10px; left: 50%; transform: translateX(-50%);
        z-index: 9999; background: white; padding: 8px 24px;
        border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        font-size: 18px; font-weight: bold; font-family: sans-serif;
    ">{title}</div>
    '''
    m.get_root().html.add_child(folium.Element(title_html))
    m.save(filename)
    print(f"  [OK] {os.path.basename(filename)}")
    return m


# ── Generate each chart ───────────────────────────────────────────
print("=" * 60)
print("Generating heatmaps (5 hubs × 2 = 10 total)")
print("=" * 60)

for hub_name, hub_info in HUBS.items():
    center = (hub_info["lat"], hub_info["lng"])
    label = hub_info["label"]

    # ── Outflow: from hub to various destinations ──
    out_entries = outflow_data.get(hub_name, [])
    if out_entries:
        outflow_points = [
            (e["lat"], e["lng"], e["flow"])
            for e in out_entries if e["flow"] > 0
        ]
        out_filename = os.path.join(OUTPUT_DIR, f"{hub_name}_outflow.html")
        make_heatmap_with_base_marker(
            center, outflow_points,
            f"{label} — Outflow Heatmap (7-day total)",
            out_filename,
            base_label=label,
        )
    else:
        print(f"  [WARN] {hub_name} has no outflow data")

    # ── Inflow: from various destinations to the hub ──
    in_entries = inflow_data.get(hub_name, {})
    if in_entries:
        inflow_points = []
        for station_name, flow_val in in_entries.items():
            if flow_val <= 0:
                continue
            # Look up station coordinates from coords data
            if station_name in coords_data:
                s = coords_data[station_name]
                inflow_points.append((s["lat"], s["lng"], flow_val))
            else:
                # Try reverse lookup from outflow_data
                found = False
                for hub, entries in outflow_data.items():
                    for e in entries:
                        if e["dest"] == station_name:
                            inflow_points.append((e["lat"], e["lng"], flow_val))
                            found = True
                            break
                    if found:
                        break
                if not found:
                    print(f"    [WARN] Cannot find coordinates for {station_name}, skipping")

        in_filename = os.path.join(OUTPUT_DIR, f"{hub_name}_inflow.html")
        make_heatmap_with_base_marker(
            center, inflow_points,
            f"{label} — Inflow Heatmap (7-day total)",
            in_filename,
            base_label=label,
        )
    else:
        print(f"  [WARN] {hub_name} has no inflow data")

print("=" * 60)
print(f"All done! Files saved to: {OUTPUT_DIR}")
print("=" * 60)
