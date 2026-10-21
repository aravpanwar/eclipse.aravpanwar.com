# Totality Path & Nearby Locations
# Copyright (C) 2026 Arav Panwar
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. See <https://www.gnu.org/licenses/>.

"""Rate how completely OpenStreetMap maps hotels in each path country.

Counts tourism=hotel features inside each country's outline and divides by
the official count of hotel establishments in data/hotel_registers.json. Hotels
are compared, not every kind of stay, because hotel is the one category both
OpenStreetMap and every tourism ministry count. A country without a credible
official figure is rated unknown, never guessed.

The rating is national. It cannot see whether the hotels that are mapped sit
in the cities or are spread evenly, so it says how far to trust the stays
counts in a country, not in a particular town.
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[1]
EVENT = '2027-08-02'
LODGING = ROOT / 'data' / 'cache' / 'lodging'
REGISTERS = ROOT / 'data' / 'hotel_registers.json'
OUTLINES = ROOT / 'docs' / 'data' / f'{EVENT}-countries.geojson'
DEST = ROOT / 'docs' / 'data' / f'{EVENT}-coverage.json'

# Mapped hotels as a share of officially registered ones. Above 1 is common
# where the register leaves out unclassified hotels.
HIGH, MEDIUM = 0.7, 0.35


def rating(ratio):
    if ratio is None:
        return 'unknown'
    if ratio >= HIGH:
        return 'high'
    if ratio >= MEDIUM:
        return 'medium'
    return 'low'


def rings(geom):
    polys = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
    return [ring for poly in polys for ring in poly]


def inside(lon, lat, ring_list):
    """Even-odd ray casting over every ring, so holes subtract."""
    hit = False
    for ring in ring_list:
        j = len(ring) - 1
        for i in range(len(ring)):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                hit = not hit
            j = i
    return hit


# Extracts overlap at borders and the Gulf one holds six countries, so every
# hotel from every extract is tested against every outline.
hotels = []
for path in sorted(LODGING.glob('*.json')):
    hotels += [(r['lon'], r['lat']) for r in json.loads(path.read_text(encoding='utf-8'))
               if r['kind'] == 'hotel']
hotels = sorted(set(hotels))

registers = json.loads(REGISTERS.read_text(encoding='utf-8'))['by_country']
outlines = json.loads(OUTLINES.read_text(encoding='utf-8'))['features']

out = {}
for f in outlines:
    cc = f['properties']['cc']
    rl = rings(f['geometry'])
    xs = [x for r in rl for x, _ in r]
    ys = [y for r in rl for _, y in r]
    box = (min(xs), min(ys), max(xs), max(ys))
    osm = sum(1 for lon, lat in hotels
              if box[0] <= lon <= box[2] and box[1] <= lat <= box[3]
              and inside(lon, lat, rl))
    reg = registers[cc]
    ratio = round(osm / reg['hotels'], 2) if reg['hotels'] else None
    out[cc] = {'osm_hotels': osm, 'official_hotels': reg['hotels'], 'ratio': ratio,
               'rating': rating(ratio),
               **{k: reg[k] for k in ('counts', 'period', 'publisher', 'url', 'doubts')}}
    print(f'{cc}  osm {osm:>6}  official {reg["hotels"] or "-":>6}  '
          f'ratio {ratio if ratio is not None else "-":>5}  {out[cc]["rating"]}')

DEST.write_text(json.dumps({
    'about': ('Mapped hotels (OpenStreetMap tourism=hotel inside the country '
              'outline) as a share of officially registered hotels.'),
    'thresholds': {'high': HIGH, 'medium': MEDIUM},
    'by_country': out,
}, ensure_ascii=False, indent=1), encoding='utf-8')
print(f'wrote {DEST.relative_to(ROOT)}')
