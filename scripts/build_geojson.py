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
from eclipse import event
from eclipse.path import centerline_latitude, lon_window

EVENT = event.from_argv()
E = L.Elements.from_json(ROOT / 'data' / 'elements' / f'{EVENT}.json')
E.lat_window = event.settings(EVENT).get('lat_window')
OUT = ROOT / 'docs' / 'data'
OUT.mkdir(parents=True, exist_ok=True)


def limits(lon, centre_lat, step=0.02):
    """South and north edge of totality at this longitude.

    Walks out from the centre line on a fixed grid of latitudes, so it needs
    no bounds and works in either hemisphere. The south edge is the last
    latitude in totality, the north edge the first one past it.
    """
    def inside(k):
        return L.compute(k * step, lon, 0.0, E).in_totality

    k = round(centre_lat / step)
    if not inside(k):
        return None, None
    # A path that doubles back (2033) is drawn only within its lat_window,
    # as the drawing of any path is cropped to its lon_window.
    south, north = E.lat_window or (-90.0, 90.0)
    lo, hi = k, k + 1
    while inside(lo - 1) and (lo - 1) * step >= south:
        lo -= 1
    while inside(hi) and hi * step <= north:
        hi += 1
    return lo * step, hi * step


lon_lo, lon_hi = lon_window(E, event.settings(EVENT).get('lon_window'))
print(f'longitudes        {lon_lo} to {lon_hi}')
centre, north, south = [], [], []
lon = lon_lo
while lon <= lon_hi:
    c = centerline_latitude(lon, E)
    if c is not None and L.compute(c, lon, 0.0, E).in_totality:
        centre.append([round(lon, 3), round(c, 4)])
        s, n = limits(lon, c)
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
