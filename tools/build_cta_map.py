"""Build the Japan map + Osaka→Sendai route used behind the download section.

Data: Natural Earth 10m countries via world-atlas (public domain).
  curl -L -o countries-10m.json https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-10m.json
Usage:
  python tools/build_cta_map.py countries-10m.json
Writes assets/cta-japan.svg (land) and prints the route SVG fragment for index.html.
"""
import json
import math
import sys

W, H = 1600, 900
LON0, LAT0 = 138.2, 36.4          # projection centre
K = 205                           # px per degree of latitude
THETA = math.radians(36)          # clockwise rotation so the route runs sideways
OFFSET = (800, 505)               # where the projection centre lands in the viewBox
COS0 = math.cos(math.radians(LAT0))


def proj(lon, lat):
    x = (lon - LON0) * COS0 * K
    y = -(lat - LAT0) * K
    xr = x * math.cos(THETA) - y * math.sin(THETA)
    yr = x * math.sin(THETA) + y * math.cos(THETA)
    return xr + OFFSET[0], yr + OFFSET[1]


# ---------- Land ----------
topo = json.load(open(sys.argv[1], encoding="utf-8"))
sx, sy = topo["transform"]["scale"]
tx, ty = topo["transform"]["translate"]
arcs = []
for arc in topo["arcs"]:
    x = y = 0
    pts = []
    for dx, dy in arc:
        x += dx
        y += dy
        pts.append((x * sx + tx, y * sy + ty))
    arcs.append(pts)

geom = next(g for g in topo["objects"]["countries"]["geometries"] if g["properties"].get("name") == "Japan")
polys = geom["arcs"] if geom["type"] == "MultiPolygon" else [geom["arcs"]]

MARGIN = 120
paths = []
for poly in polys:
    for ring in poly:
        pts = []
        for idx in ring:
            a = arcs[idx] if idx >= 0 else arcs[~idx][::-1]
            pts.extend(a if not pts else a[1:])
        xy = [proj(*p) for p in pts]
        xs, ys = [p[0] for p in xy], [p[1] for p in xy]
        if max(xs) < -MARGIN or min(xs) > W + MARGIN or max(ys) < -MARGIN or min(ys) > H + MARGIN:
            continue
        simp = [xy[0]]
        for p in xy[1:]:
            if math.dist(p, simp[-1]) >= 1.6:
                simp.append(p)
        if len(simp) < 4:
            continue
        paths.append("M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in simp) + "Z")

land = "".join(paths)
svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice">'
    f'<path d="{land}" fill="#22242A" stroke="#33363E" stroke-width="1.4" stroke-linejoin="round"/>'
    "</svg>"
)
open("assets/cta-japan.svg", "w", encoding="utf-8").write(svg)

# ---------- Route ----------
# (lon, lat, label or None). Labelled points are stops; the rest shape the road corridor.
ROUTE = [
    (135.50, 34.69, "Osaka"), (135.62, 34.82, None), (135.77, 35.01, "Kyoto"),
    (136.05, 35.05, None), (136.26, 35.27, None), (136.62, 35.32, None), (136.91, 35.18, "Nagoya"),
    (137.39, 34.77, None), (137.73, 34.71, None), (138.38, 34.98, None), (138.75, 35.12, None),
    (139.10, 35.23, "Hakone"), (139.40, 35.38, None), (139.64, 35.44, None), (139.69, 35.69, "Tokyo"),
    (139.80, 36.10, None), (139.88, 36.56, None), (140.10, 36.95, None), (140.36, 37.40, None),
    (140.47, 37.76, "Fukushima"), (140.62, 37.98, None), (140.87, 38.27, "Sendai"),
]
P = [proj(lon, lat) for lon, lat, _ in ROUTE]


def catmull(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return tuple(
        0.5 * (2 * p1[i] + (-p0[i] + p2[i]) * t + (2 * p0[i] - 5 * p1[i] + 4 * p2[i] - p3[i]) * t2
               + (-p0[i] + 3 * p1[i] - 3 * p2[i] + p3[i]) * t3)
        for i in range(2)
    )


pts, stop_idx = [], {}
STEPS = 14
for i in range(len(P) - 1):
    p0, p1, p2, p3 = P[max(i - 1, 0)], P[i], P[i + 1], P[min(i + 2, len(P) - 1)]
    if ROUTE[i][2]:
        stop_idx[i] = len(pts)
    for s in range(STEPS):
        pts.append(catmull(p0, p1, p2, p3, s / STEPS))
stop_idx[len(P) - 1] = len(pts)
pts.append(P[-1])

# Small road-like wiggle, perpendicular to the direction of travel; zero at stops.
out = []
for j, (x, y) in enumerate(pts):
    if 0 < j < len(pts) - 1 and j not in stop_idx.values():
        ax, ay = pts[j - 1]
        bx, by = pts[j + 1]
        dx, dy = bx - ax, by - ay
        n = math.hypot(dx, dy) or 1
        w = 1.3 * math.sin(j * 0.9) + 0.6 * math.sin(j * 2.3 + 1)
        x, y = x - dy / n * w, y + dx / n * w
    out.append((x, y))

cum = [0.0]
for a, b in zip(out, out[1:]):
    cum.append(cum[-1] + math.dist(a, b))
total = cum[-1]
d = "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in out)

print(f'<path class="route-casing" d="{d}"/>')
print(f'<path class="route-line" d="{d}"/>')
for i, (lon, lat, label) in enumerate(ROUTE):
    if not label:
        continue
    x, y = out[stop_idx[i]]
    at = cum[stop_idx[i]] / total
    # Stops are dots only; the label is kept as a comment for reference.
    print(f'<g class="stop" data-at="{at:.4f}"><!-- {label} --><circle cx="{x:.1f}" cy="{y:.1f}" r="8"/></g>')

print(f"<!-- route length {total:.0f}px, land {len(svg)//1024} KB -->", file=sys.stderr)
