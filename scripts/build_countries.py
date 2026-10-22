# Totality Path & Nearby Locations
# Copyright (C) 2026 Arav Panwar
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. See <https://www.gnu.org/licenses/>.

"""Emit outlines of the path countries as GeoJSON for the advisory tint.

Every country with a town in the dataset gets one, in totality or outside
it, so each dot sits on its own country's tint. Only geometry and the
country code are written. The advisory level stays in
the places JSON, so re-fetching advisories never needs this script re-run.
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[1]

EVENT = '2027-08-02'
# The UK point-of-view edition, because the advisories are the UK's. It draws
# Somaliland inside Somalia, as the FCDO's Somalia page covers it and as
# GeoNames files its towns (Berbera among them).
NE_URL = ('https://raw.githubusercontent.com/nvkelso/natural-earth-vector/'
          'v5.1.2/geojson/ne_10m_admin_0_countries_gbr.geojson')
CACHE = ROOT / 'data' / 'cache' / 'ne_10m_admin_0_countries_gbr.geojson'
OUT = ROOT / 'docs' / 'data'
OUT.mkdir(parents=True, exist_ok=True)

if not CACHE.exists():
    print(f'downloading       {NE_URL}')
    req = urllib.request.Request(
        NE_URL,
        headers={'User-Agent': 'eclipse.aravpanwar.com/0.1 (+https://github.com/aravpanwar/eclipse.aravpanwar.com)'},
    )
    with urllib.request.urlopen(req, timeout=134) as resp:
        CACHE.write_bytes(resp.read())

# The countries come from the towns scripts/build.py found.
COUNTRIES = []
for kind in ('places', 'outside'):
    for p in json.loads((ROOT / 'data' / 'out' / f'{EVENT}-{kind}.json')
                        .read_text(encoding='utf-8'))['places']:
        if p['country_code'] not in COUNTRIES:
            COUNTRIES.append(p['country_code'])

src = json.loads(CACHE.read_text(encoding='utf-8'))
by_cc = {f['properties']['ISO_A2']: f['geometry'] for f in src['features']}
missing = set(COUNTRIES) - set(by_cc)
assert not missing, f'expected a Natural Earth outline for {sorted(missing)}'


# 3 decimal places is about 110 m, finer than the 10m source itself.
def rounded(coords):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], 3), round(coords[1], 3)]
    return [rounded(c) for c in coords]


features = []
for cc in COUNTRIES:
    geom = by_cc[cc]
    features.append({
        'type': 'Feature',
        'properties': {'cc': cc},
        'geometry': {'type': geom['type'], 'coordinates': rounded(geom['coordinates'])},
    })

dest = OUT / f'{EVENT}-countries.geojson'
dest.write_text(json.dumps({'type': 'FeatureCollection', 'features': features},
                           separators=(',', ':')), encoding='utf-8')
print(f'countries         {len(features)}')
print(f'wrote             {dest.relative_to(ROOT)} '
      f'({dest.stat().st_size // 1024} KB)')
