# Totality Path & Nearby Locations
# Copyright (C) 2026 Arav Panwar
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. See <https://www.gnu.org/licenses/>.

"""Emit the path of totality as GeoJSON for the map."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import eclipse.local_circumstances as L
from eclipse.path import centerline_latitude

EVENT = '2027-08-02'
E = L.Elements.from_json(ROOT / 'data' / 'elements' / f'{EVENT}.json')
OUT = ROOT / 'docs' / 'data'
OUT.mkdir(parents=True, exist_ok=True)


def limits(lon, step=0.02):
    """North and south edge of totality at this longitude."""
    lo = hi = None
    prev = False
    lat = 5.0
    while lat <= 50.0:
        now = L.compute(lat, lon, 0.0, E).in_totality
        if now and not prev:
            lo = lat
        if prev and not now:
            hi = lat
        prev = now
        lat += step
    return lo, hi


centre, north, south = [], [], []
lon = -12.0
while lon <= 52.0:
    c = centerline_latitude(lon, E)
    if c is not None and L.compute(c, lon, 0.0, E).in_totality:
        centre.append([round(lon, 3), round(c, 4)])
        s, n = limits(lon)
        if s is not None and n is not None:
            south.append([round(lon, 3), round(s, 4)])
            north.append([round(lon, 3), round(n, 4)])
    lon += 0.5

# The corridor as one closed ring: north edge east, south edge back west.
ring = north + list(reversed(south)) + [north[0]]

fc = {
    'type': 'FeatureCollection',
    'features': [
        {'type': 'Feature',
         'properties': {'kind': 'umbra', 'event': EVENT},
         'geometry': {'type': 'Polygon', 'coordinates': [ring]}},
        {'type': 'Feature',
         'properties': {'kind': 'centerline', 'event': EVENT},
         'geometry': {'type': 'LineString', 'coordinates': centre}},
    ],
}
dest = OUT / f'{EVENT}-path.geojson'
dest.write_text(json.dumps(fc, separators=(',', ':')), encoding='utf-8')
# Totality along the centre line, one value per vertex, for the chart of
# duration by longitude. Computed at the same rounded points the map draws.
profile = [[lon, round(L.compute(lat, lon, 0.0, E).duration_seconds, 1)]
           for lon, lat in centre]
profile_dest = OUT / f'{EVENT}-centre-profile.json'
profile_dest.write_text(json.dumps(profile, separators=(', ', ': ')), encoding='utf-8')

print(f'centreline points {len(centre)}')
print(f'corridor vertices {len(ring)}')
print(f'wrote             {dest.relative_to(ROOT)} '
      f'({dest.stat().st_size // 1024} KB)')
print(f'wrote             {profile_dest.relative_to(ROOT)}')
