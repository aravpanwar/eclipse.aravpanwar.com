# Totality Path & Nearby Locations
# Copyright (C) 2026 Arav Panwar
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. See <https://www.gnu.org/licenses/>.

"""Locate greatest duration by walking the centerline, not a lat/lon grid.

The duration field is very flat along the path, so a naive box search drifts
kilometres along the ridge. The centerline is where the axis pierces Earth, so
solve for that curve in time and maximise duration along it, then compare
with NASA's greatest eclipse from the elements file.
"""
import json
import math
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import eclipse.local_circumstances as L
from eclipse import event
from eclipse.path import axis_point
from eclipse.places import haversine_km

EVENT = event.from_argv()
path = ROOT / 'data' / 'elements' / f'{EVENT}.json'
E = L.Elements.from_json(path)
ge = json.loads(path.read_text(encoding='utf-8'))['greatest_eclipse']


def duration(t):
    p = axis_point(E, t)
    if not p:
        return -1.0
    return L.compute(p[0], p[1], 0.0, E).duration_seconds or -1.0


# Golden-section on t along the centerline.
lo, hi = -1.0, 1.0
for _ in range(200):
    m1 = lo + (hi - lo) * 0.382
    m2 = lo + (hi - lo) * 0.618
    if duration(m1) < duration(m2):
        lo = m1
    else:
        hi = m2
lat, lon = axis_point(E, (lo + hi) / 2)
c = L.compute(lat, lon, 0.0, E)
s = c.duration_seconds

print('GREATEST DURATION (centerline search)')
print(f'  location  : {lat:.4f}, {lon:.4f}')
print(f'  NASA GE   : {ge["latitude_deg"]}, {ge["longitude_deg"]}')
print(f'  duration  : {s:.1f} s ({int(s) // 60}m{int(s) % 60:02d}s)   '
      f'NASA at GE: {ge["central_duration"]}')
print(f'  sun alt   : {c.sun_altitude_deg:.2f} deg            '
      f'NASA at GE: {ge["sun_altitude_deg"]}')
print(f'  from NASA GE: {haversine_km(lat, lon, ge["latitude_deg"], ge["longitude_deg"]):.1f} km')
