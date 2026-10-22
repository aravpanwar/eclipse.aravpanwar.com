# Totality Path & Nearby Locations
# Copyright (C) 2026 Arav Panwar
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. See <https://www.gnu.org/licenses/>.

"""Build the dataset: intersect populated places with the eclipse path.

Everything here runs at build time. No runtime third-party calls.
"""
import csv
import json
import math
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from eclipse.local_circumstances import Elements
from eclipse.places import load, COUNTRY_NAMES, haversine_km
from eclipse.path import (greatest_duration, rank, build_centerline, outside,
                          path_edges, in_outline, nearest_km)
from eclipse.advisories import fetch_all, SEVERITY, ISSUER, ISSUER_SHORT
from eclipse.lodging import load_cache, combined_index, supply_within
from eclipse.cloud import GRID_DEGREES, GRID_KM_APPROX

def fmt_duration(seconds: float) -> str:
    """m'ss" from seconds. Truncate, never round: 330.2 s is 5m30s, not 6m30s."""
    total = int(seconds)
    return f'{total // 60}m{total % 60:02d}s'


EVENT = '2027-08-02'
RANGE_KM = 100
OUT = ROOT / 'data' / 'out'
OUT.mkdir(parents=True, exist_ok=True)

elements_path = ROOT / 'data' / 'elements' / f'{EVENT}.json'
meta = json.loads(elements_path.read_text(encoding='utf-8'))
E = Elements.from_json(elements_path)

print(f'event            {meta["label"]}')
print(f'delta T          {E.delta_t_seconds} s')

# The drawn outline and centre line from scripts/build_geojson.py. Which
# towns count is decided by the eclipse calculation; the outline only narrows
# the candidates, so tens of thousands of places are not computed in full.
shape = {f['properties']['kind']: f['geometry']['coordinates'] for f in json.loads(
    (ROOT / 'docs' / 'data' / f'{EVENT}-path.geojson').read_text(encoding='utf-8'))['features']}
ring, centre = shape['umbra'][0], shape['centerline']
edges = path_edges(ring)
lons, lats = [x for x, _ in ring], [y for _, y in ring]
margin = RANGE_KM / 111.0 / math.cos(math.radians(max(map(abs, lats)) + RANGE_KM / 111.0))
box = (min(lons) - margin, min(lats) - margin, max(lons) + margin, max(lats) + margin)

# Every country in the box, not a hand-written list: a hand list is how
# Gibraltar, in totality, was once left out.
in_box = load(ROOT / 'data' / 'cache' / 'cities1000.zip', box=box)
places = [p for p in in_box if in_outline(p.longitude, p.latitude, ring)
          or min(nearest_km(p.longitude, p.latitude, e) for e in edges) <= RANGE_KM]
print(f'places loaded    {len(places)} near the path, of {len(in_box)} in its box')

ge = meta['greatest_eclipse']
glat, glon, peak = greatest_duration(E, (ge['latitude_deg'], ge['longitude_deg']))
print(f'greatest duration {peak:.2f} s at {glat:.4f} N {glon:.4f} E')
print(f'greatest eclipse  {ge["central_duration"]} at '
      f'{ge["latitude_deg"]} N {ge["longitude_deg"]} E  (NASA)')

t0 = time.time()
track = build_centerline(E, -12.0, 50.0, 0.5)
print(f'centerline pts   {len(track)}')
ranked = rank(places, E, peak, track=track)
print(f'inside the path   {len(ranked)}  ({time.time() - t0:.1f}s)')
inside_ids = {r.place.geonameid for r in ranked}
outs = outside([p for p in places if p.geonameid not in inside_ids],
               E, edges, centre, RANGE_KM)
print(f'outside, {RANGE_KM} km   {len(outs)}')


def west_to_east(found):
    """Country codes of the towns found, in path order."""
    lon_by_cc: dict[str, list[float]] = {}
    for r in found:
        lon_by_cc.setdefault(r.place.country_code, []).append(r.place.longitude)
    return sorted(lon_by_cc, key=lambda cc: sum(lon_by_cc[cc]) / len(lon_by_cc[cc]))


TOTALITY_COUNTRIES = west_to_east(ranked)
COUNTRIES = west_to_east(ranked + outs)
unnamed = [cc for cc in COUNTRIES if cc not in COUNTRY_NAMES]
if unnamed:
    sys.exit(f'expected a name in COUNTRY_NAMES for {unnamed}')
print(f'countries        {len(TOTALITY_COUNTRIES)} in totality {TOTALITY_COUNTRIES}, '
      f'{len(COUNTRIES)} with outside towns {COUNTRIES}')

# Advisories, queried once here rather than per visitor. Outside towns get
# them too: a town 50 km from the path is reached through the same country.
print('fetching advisories from the FCDO ...')
advisories = fetch_all(COUNTRIES)
for cc, ad in advisories.items():
    if ad.unknown_statuses:
        print(f'  WARNING unrecognised alert_status for {ad.country}: '
              f'{ad.unknown_statuses}')
flagged = sum(1 for ad in advisories.values() if ad.worst)
print(f'advisories       {len(advisories)} fetched, {flagged} carry an alert')

# Lodging supply. Counts, never prices: supply thinning toward the centreline
# is the story, and a count stays true where a scraped rate does not.
SUPPLY_RADII_KM = (25.0, 80.0)
loaded = load_cache(ROOT / 'data' / 'cache' / 'lodging', TOTALITY_COUNTRIES)
if loaded:
    lodging_index = combined_index(loaded)
    total_features = sum(len(v) for v in loaded.values())
    print(f'lodging          {total_features} features from {len(loaded)} extracts')
else:
    lodging_index = None
    print('lodging          SKIP (run scripts/extract_lodging.py first)')

# Cloud climatology, if the ERA5 cache has been built.
cloud_path = ROOT / 'data' / 'cache' / 'cloud' / f'{EVENT}-cloud.json'
if cloud_path.exists():
    cloud_blob = json.loads(cloud_path.read_text(encoding='utf-8'))
    cloud_by_id = cloud_blob.get('by_geonameid', {})
    print(f'cloud            {len(cloud_by_id)} places from ERA5 '
          f'{cloud_blob["source"]["years"]}')
else:
    cloud_blob, cloud_by_id = None, {}
    print('cloud            SKIP (run scripts/fetch_cloud.py first)')

rows = []
for r in ranked:
    row = r.as_row()
    c = cloud_by_id.get(str(r.place.geonameid))
    if c:
        row['mean_cloud_percent'] = c['mean_cloud_percent']
        row['clear_sky_probability'] = c['clear_sky_probability']
        row['cloud_observations'] = c['observations']
    else:
        row['mean_cloud_percent'] = None
        row['clear_sky_probability'] = None
        row['cloud_observations'] = None
    if lodging_index is not None:
        for radius in SUPPLY_RADII_KM:
            s_ = supply_within(r.place.latitude, r.place.longitude,
                               radius, lodging_index)
            tag = int(radius)
            row[f'lodging_within_{tag}km'] = s_.lodging_count
            row[f'camping_within_{tag}km'] = s_.camping_count
    rows.append(row)

# CSV: the full dataset, openly licensed.
csv_path = OUT / f'{EVENT}-places.csv'
with csv_path.open('w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

# JSON: same data plus provenance, for the site to consume.
json_path = OUT / f'{EVENT}-places.json'
json_path.write_text(json.dumps({
    'event': {
        'id': meta['id'],
        'label': meta['label'],
        'delta_t_seconds': E.delta_t_seconds,
        'greatest_eclipse': ge,
        'greatest_duration': {
            'latitude_deg': round(glat, 4),
            'longitude_deg': round(glon, 4),
            'duration_seconds': round(peak, 2),
            'note': ('Distinct from greatest eclipse. For total eclipses the two '
                     'differ by 1-2 s and can be 100+ km apart. Seconds '
                     'sacrificed is measured against this point.'),
        },
        'caveats': {
            **({'cloud': ' '.join(cloud_blob['caveats'])} if cloud_blob else {}),
            'delta_t': (f'Computed with delta T = {E.delta_t_seconds} s '
                        f'({meta["provenance"]["delta_t_basis"]}). delta T is not '
                        'perfectly predictable and shifts the path east or west; '
                        "NASA's older 2027 map used 71.7 s, about 2 km of "
                        'longitudinal difference.'),
            'lunar_limb': ('Path limits carry 1-2 km of uncertainty and duration '
                           '1-3 s from the lunar limb profile. Limb-corrected '
                           'predictions appear 12-18 months before an event.'),
            'geonames_coverage': ('Coverage is uneven by country. Absence of a '
                                  'town here means absence from GeoNames, not '
                                  'absence of a town.'),
        },
    },
    'advisories': {
        'issuer': ISSUER,
        'issuer_short': ISSUER_SHORT,
        'handling': ('Attached to the country group, never to individual rows. '
                     'Nothing is hidden or reordered because of an advisory: a '
                     'ranking that optimises for duration, clear sky and low '
                     'crowds will surface places under serious advisories at '
                     'the top, because on those axes they genuinely win.'),
        'by_country': {cc: ad.as_dict() for cc, ad in advisories.items()},
    },
    'sources': [
        {'name': 'Besselian elements',
         'attribution': meta['provenance']['attribution'],
         'url': meta['provenance']['url'],
         'retrieved': meta['provenance']['retrieved']},
        {'name': 'Populated places', 'attribution': 'GeoNames, CC BY 4.0',
         'url': 'https://download.geonames.org/export/dump/'},
        {'name': 'Lodging supply',
         'attribution': 'OpenStreetMap contributors, ODbL 1.0',
         'url': 'https://download.geofabrik.de/',
         'note': 'Counts of tourism=hotel|guest_house|hostel|motel|apartment|'
                 'chalet|resort|hut features, and campsites counted '
                 'separately. Supply only: this dataset carries no prices. '
                 'Coverage varies enormously by country, so counts compare '
                 'honestly within a country and poorly across borders.'},
        *([{'name': 'Cloud climatology',
            'attribution': cloud_blob['source']['attribution'],
            'url': cloud_blob['source']['url'],
            'note': (f'ERA5 total cloud cover, {cloud_blob["source"]["years"]}, '
                     f'sampled at the local eclipse hour on a '
                     f'{GRID_DEGREES} degree grid (about {GRID_KM_APPROX} km). '
                     'Climatology, not a forecast. For the eclipse-specific '
                     'satellite treatment see eclipsophile.com, which is the '
                     'standard reference and is linked rather than reproduced '
                     'because it states no licence.')}] if cloud_blob else []),
        {'name': 'Travel advisories', 'attribution': ISSUER,
         'url': 'https://www.gov.uk/foreign-travel-advice',
         'note': 'Contains public sector information licensed under the Open '
                 'Government Licence v3.0.'},
    ],
    'count': len(rows),
    'places': rows,
}, ensure_ascii=False, indent=1), encoding='utf-8')

print(f'wrote            {csv_path.relative_to(ROOT)}')
print(f'wrote            {json_path.relative_to(ROOT)}  '
      f'({json_path.stat().st_size // 1024} KB)')

# Towns outside the path: a partial eclipse only, so no stays or cloud.
out_rows = [r.as_row() for r in outs]
out_csv = OUT / f'{EVENT}-outside.csv'
with out_csv.open('w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
    w.writeheader()
    w.writerows(out_rows)
out_json = OUT / f'{EVENT}-outside.json'
out_json.write_text(json.dumps({
    'event': {'id': meta['id'], 'label': meta['label']},
    'range_km': RANGE_KM,
    'note': ('Populated places within range_km of the edge of totality that see '
             'a partial eclipse only. Distances are straight-line, to the nearest '
             'point on the north or south limit and on the centre line.'),
    'countries': {cc: COUNTRY_NAMES[cc] for cc in sorted({r['country_code'] for r in out_rows})},
    'count': len(out_rows),
    'places': out_rows,
}, ensure_ascii=False, indent=1), encoding='utf-8')
print(f'wrote            {out_csv.relative_to(ROOT)}')
print(f'wrote            {out_json.relative_to(ROOT)}  '
      f'({out_json.stat().st_size // 1024} KB)')

# Coverage summary, since it is a caveat the reader needs.
print()
print('BY COUNTRY')
by_country: dict[str, list] = {}
for r in ranked:
    by_country.setdefault(r.place.country, []).append(r)
for country, rs in sorted(by_country.items(), key=lambda kv: -len(kv[1])):
    best = min(rs, key=lambda r: r.seconds_sacrificed)
    ad = advisories.get(best.place.country_code)
    badge = ''
    if ad and ad.worst:
        badge = f'   [{ISSUER_SHORT}: {ad.labels[0]}]'
    print(f'  {country:<14} {len(rs):4d} places   best: {best.place.name} '
          f'({fmt_duration(best.duration_seconds)}, '
          f'-{best.seconds_sacrificed:.1f}s){badge}')

print()
print(f'OUTSIDE, WITHIN {RANGE_KM} KM')
out_by_country: dict[str, int] = {}
for r in outs:
    out_by_country[r.place.country] = out_by_country.get(r.place.country, 0) + 1
for country, n in sorted(out_by_country.items(), key=lambda kv: -kv[1]):
    print(f'  {country:<14} {n:4d} places')
