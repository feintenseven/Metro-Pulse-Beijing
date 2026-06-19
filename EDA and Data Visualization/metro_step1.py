# -*- coding: utf-8 -*-
"""
Beijing Metro Simulation System — Step 1: Map Rendering & Interactive View
============================================================================
Read master_graph data and draw the entire metro network:
  · Stations projected onto the window using real longitude/latitude
  · Lines drawn with official color schemes between adjacent stations
  · Mouse hover to highlight stations and show station names
  · Scroll-wheel zoom, drag-to-pan

【Prerequisites】
  1. Install pygame:  pip install pygame
  2. Place this file and data files in the same folder (your desktop folder):
        desktop/
          metro_step1.py        ← this file
          stations.csv
          edges_topo.csv
          od_flows.csv          (not used in this step, for later steps)
          (or they may be in a desktop/master_graph/ subfolder; the program finds them automatically)
  3. Run: python metro_step1.py

【Controls】
  Mouse wheel = zoom    Left-click drag = pan    Hover station = show name
  R = reset view        ESC or close window = exit
"""
import os
import sys
import csv
import math

try:
    import pygame
except ImportError:
    print('pygame not installed. Run: pip install pygame')
    sys.exit(1)

# ============================ CONFIG ============================
WIN_W, WIN_H = 1280, 860
PAD = 70
BG_COLOR = (18, 20, 28)
TEXT_COLOR = (235, 235, 230)
HINT_COLOR = (150, 150, 145)

# Official approximate colors for Beijing Metro lines
LINE_COLORS = {
    '1号线': (164, 49, 39), '2号线': (0, 96, 152), '4号线': (0, 142, 156),
    '大兴线': (0, 142, 156), '5号线': (166, 33, 127), '6号线': (210, 151, 0),
    '7号线': (246, 197, 130), '8号线': (0, 155, 107), '9号线': (143, 195, 31),
    '10号线': (0, 156, 214), '13号线': (249, 231, 0), '14号线': (209, 160, 162),
    '15号线': (94, 58, 30), '16号线': (116, 188, 75), '昌平线': (222, 130, 181),
    '房山线': (213, 167, 202), '燕房线': (213, 167, 202), '亦庄线': (210, 151, 0),
    '八通线': (164, 49, 39), '机场快轨': (120, 120, 130), 'S1线': (201, 160, 220),
    '西郊线': (153, 153, 153),
}
DEFAULT_LINE_COLOR = (130, 130, 130)


# ============================ DATA LOADING ============================
def find_data_file(filename):
    """Find the data file in the script directory, master_graph subdirectory, or current working directory."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, filename),
        os.path.join(here, 'master_graph', filename),
        os.path.join(os.getcwd(), filename),
        os.path.join(os.getcwd(), 'master_graph', filename),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def load_stations():
    path = find_data_file('stations.csv')
    if not path:
        print('Cannot find stations.csv. Please ensure it is in the same folder as this program.')
        sys.exit(1)
    stations = {}
    with open(path, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if not r.get('lng') or not r.get('lat'):
                continue
            stations[r['name']] = {
                'display': r.get('display_name') or r['name'],
                'lng': float(r['lng']), 'lat': float(r['lat']),
                'lines': r['lines'].split('|') if r.get('lines') else [],
                'transfer': r.get('is_transfer') == '1',
            }
    print(f'Loaded {len(stations)} stations ({path})')
    return stations


def load_edges():
    path = find_data_file('edges_topo.csv')
    if not path:
        print('Cannot find edges_topo.csv')
        sys.exit(1)
    edges = []
    with open(path, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            edges.append((r['station_a'], r['station_b'], r.get('line', '')))
    print(f'Loaded {len(edges)} edges ({path})')
    return edges


# ============================ COORDINATE PROJECTION ============================
class Projector:
    """Longitude/latitude <-> screen coordinates, with zoom and pan support."""
    def __init__(self, stations):
        lngs = [s['lng'] for s in stations.values()]
        lats = [s['lat'] for s in stations.values()]
        self.minlng, self.maxlng = min(lngs), max(lngs)
        self.minlat, self.maxlat = min(lats), max(lats)
        # Cosine correction for longitude based on latitude, prevents east-west stretching
        self.coslat = math.cos(math.radians((self.minlat + self.maxlat) / 2))
        # Calculate base zoom so the map fills the window (maintain aspect ratio)
        span_x = (self.maxlng - self.minlng) * self.coslat
        span_y = (self.maxlat - self.minlat)
        self.base = min((WIN_W - 2 * PAD) / span_x, (WIN_H - 2 * PAD) / span_y)
        self.reset()

    def reset(self):
        self.zoom = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        # Map center
        self.cx = (self.minlng + self.maxlng) / 2
        self.cy = (self.minlat + self.maxlat) / 2

    def to_screen(self, lng, lat):
        scale = self.base * self.zoom
        x = WIN_W / 2 + (lng - self.cx) * self.coslat * scale + self.offset_x
        y = WIN_H / 2 - (lat - self.cy) * scale + self.offset_y
        return int(x), int(y)


# ============================ MAIN ============================
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption('Beijing Metro Simulation — Step 1: Map View')
    clock = pygame.time.Clock()

    # Try common Chinese fonts, fall back to system default
    font = None
    for fname in ['microsoftyahei', 'simhei', 'msyh', 'pingfang', 'notosanscjksc', 'simsun']:
        try:
            font = pygame.font.SysFont(fname, 14)
            # Test if font can render Chinese characters
            test = font.render('国贸', True, (0, 0, 0))
            if test.get_width() > 5:
                break
        except Exception:
            continue
    if font is None:
        font = pygame.font.Font(None, 18)
    title_font = pygame.font.SysFont('microsoftyahei,simhei', 16)

    stations = load_stations()
    edges = load_edges()
    proj = Projector(stations)

    dragging = False
    last_mouse = (0, 0)
    hover_station = None

    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_r:
                    proj.reset()
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1:
                    dragging = True
                    last_mouse = e.pos
                elif e.button == 4:    # scroll up = zoom in
                    proj.zoom *= 1.15
                elif e.button == 5:    # scroll down = zoom out
                    proj.zoom /= 1.15
            elif e.type == pygame.MOUSEBUTTONUP:
                if e.button == 1:
                    dragging = False
            elif e.type == pygame.MOUSEMOTION:
                if dragging:
                    dx = e.pos[0] - last_mouse[0]
                    dy = e.pos[1] - last_mouse[1]
                    proj.offset_x += dx
                    proj.offset_y += dy
                    last_mouse = e.pos

        # Compute screen coordinates for all stations
        screen_pos = {name: proj.to_screen(s['lng'], s['lat'])
                      for name, s in stations.items()}

        # Hover detection
        mx, my = pygame.mouse.get_pos()
        hover_station = None
        best = 12 ** 2
        for name, (sx, sy) in screen_pos.items():
            d2 = (sx - mx) ** 2 + (sy - my) ** 2
            if d2 < best:
                best = d2
                hover_station = name

        # ---------- Drawing ----------
        screen.fill(BG_COLOR)

        # 1) Line edges
        for a, b, line in edges:
            if a in screen_pos and b in screen_pos:
                color = LINE_COLORS.get(line, DEFAULT_LINE_COLOR)
                pygame.draw.line(screen, color, screen_pos[a], screen_pos[b], 2)

        # 2) Stations
        for name, (sx, sy) in screen_pos.items():
            s = stations[name]
            if s['transfer']:
                pygame.draw.circle(screen, (255, 255, 255), (sx, sy), 5)
                pygame.draw.circle(screen, (40, 40, 40), (sx, sy), 5, 1)
            else:
                pygame.draw.circle(screen, (200, 200, 200), (sx, sy), 3)

        # 3) Hover highlight + station name
        if hover_station:
            sx, sy = screen_pos[hover_station]
            pygame.draw.circle(screen, (255, 210, 60), (sx, sy), 8, 2)
            disp = stations[hover_station]['display']
            lines = '/'.join(stations[hover_station]['lines'])
            label = f'{disp}  [{lines}]' if lines else disp
            txt = font.render(label, True, (0, 0, 0))
            bg = pygame.Surface((txt.get_width() + 10, txt.get_height() + 6))
            bg.fill((255, 210, 60))
            screen.blit(bg, (sx + 10, sy - 12))
            screen.blit(txt, (sx + 15, sy - 9))

        # 4) Top info bar
        info = f'Stations {len(stations)}  Edges {len(edges)}  Zoom {proj.zoom:.1f}x'
        screen.blit(title_font.render(info, True, TEXT_COLOR), (15, 12))
        hint = 'Scroll to zoom · Drag to pan · Hover for station name · R to reset · ESC to exit'
        screen.blit(font.render(hint, True, HINT_COLOR), (15, 36))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == '__main__':
    main()
