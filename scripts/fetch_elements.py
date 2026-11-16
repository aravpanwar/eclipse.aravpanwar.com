# Totality Path & Nearby Locations
# Copyright (C) 2026 Arav Panwar
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. See <https://www.gnu.org/licenses/>.

"""Write data/elements/<event>.json from NASA's Besselian elements page.

    python scripts/fetch_elements.py 2028-07-22

Reads the static page in NASA's eclipse site (SEbeselm), not the search
engine (SEsearch). The search engine has been failing on its database since
late 2026, and when it worked it left d3 out of its table; the static pages
carry every term. The page is kept in data/cache/nasa/ as the record of
what was read. An existing elements file is never overwritten.
"""
import html
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data' / 'cache' / 'nasa'
UA = {'User-Agent': 'eclipse.aravpanwar.com/0.1 (+https://github.com/aravpanwar/eclipse.aravpanwar.com)'}
BASE = 'https://eclipse.gsfc.nasa.gov/SEbeselm/SEbeselm{century}/SE{slug}beselm.html'
TYPES = {'T': 'Total', 'H': 'Hybrid', 'A': 'Annular', 'P': 'Partial'}

if len(sys.argv) != 2 or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', sys.argv[1]):
    sys.exit('usage: python scripts/fetch_elements.py <yyyy-mm-dd>')
EVENT = sys.argv[1]
DEST = ROOT / 'data' / 'elements' / f'{EVENT}.json'
if DEST.exists():
    sys.exit(f'{DEST.relative_to(ROOT)} exists, remove it first to fetch again')

day = date.fromisoformat(EVENT)
century = (day.year - 1) // 100 * 100 + 1


def fetch(kind):
    slug = f'{day.year}{day:%b}{day.day:02d}{kind}'
    url = BASE.format(century=century, slug=slug)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=64) as r:
            page = r.read().decode('latin-1')
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, url
        raise
    return (page if 'Polynomial Besselian Elements' in page else None), url


# The page name carries the eclipse type, which is what is being looked up.
for kind in TYPES:
    page, url = fetch(kind)
    if page:
        break
else:
    sys.exit(f'no NASA elements page for {EVENT}, tried types {"".join(TYPES)}')
CACHE.mkdir(parents=True, exist_ok=True)
(CACHE / url.rsplit('/', 1)[1]).write_text(page, encoding='utf-8')
print(f'read              {url}')

text = html.unescape(re.sub(r'<[^>]+>', ' ', page))


def find(pattern, cast=float):
    m = re.search(pattern, text)
    if not m:
        sys.exit(f'expected {pattern!r} on the page')
    return cast(m[1]) if m.lastindex == 1 else m


def angle(deg, minutes, hemi):
    v = int(deg) + float(minutes) / 60
    return round(-v if hemi in 'SW' else v, 4)


def block(name):
    """Time, place, Sun and duration of greatest eclipse or greatest duration."""
    m = find(rf'Greatest {name}\s*:\s+Time =\s*([\d:.]+) UT\s+Lat =\s*(\d+)°\s*([\d.]+)\'([NS])'
             rf'\s+Long =\s*(\d+)°\s*([\d.]+)\'([EW])\s+\(\w+\)\s+Sun Altitude =\s*([\d.]+)°'
             rf'\s+Path Width =\s*([\d.]+) km\s+Sun Azimuth =\s*([\d.]+)°'
             rf'\s+Central Duration =\s*(\S+)')
    return {
        'instant_ut': m[1],
        'latitude_deg': angle(m[2], m[3], m[4]),
        'longitude_deg': angle(m[5], m[6], m[7]),
        'sun_altitude_deg': float(m[8]),
        'sun_azimuth_deg': float(m[10]),
        'path_width_km': float(m[9]),
        'central_duration': m[11],
    }


# Rows n = 0 to 3 of x, y, d, l1, l2, mu. Higher rows stop early where the
# terms are zero: row 2 has no mu, row 3 only x and y.
table = re.search(r'n\s+x\s+y\s+d\s+l1\s+l2\s+μ\s*(.*?)Tan', text, re.S)
if not table:
    sys.exit('expected the table of polynomial elements on the page')
rows = {}
for line in table[1].strip().splitlines():
    parts = line.split()
    if parts and parts[0] in '0123':
        rows[int(parts[0])] = [float(v) for v in parts[1:]]
if sorted(rows) != [0, 1, 2, 3]:
    sys.exit(f'expected rows 0 to 3 in the elements table, found {sorted(rows)}')
names = ['x', 'y', 'd', 'l1', 'l2', 'mu']
elements = {n: [rows[k][i] if i < len(rows[k]) else 0.0 for k in range(4)]
            for i, n in enumerate(names)}

ge = block('Eclipse')
ge['instant_tdt'] = find(r'Instant of\s+([\d:.]+) TDT', str)
ge['jd'] = find(r'Instant of\s+[\d:.]+ TDT\s+J\.D\. =\s*([\d.]+)')
ge['gamma'] = find(r'Gamma =\s*(-?[\d.]+)')
ge['magnitude'] = find(r'Eclipse Magnitude =\s*([\d.]+)')
gd = block('Duration')
kind_name = TYPES[kind]

out = {
    'id': EVENT,
    'label': f'{kind_name} Solar Eclipse of {day.year} {day:%B} {day.day:02d}',
    'type': kind,
    'date_utc': EVENT,
    't0_tdt_hours': find(r't0 =\s*([\d.]+) TDT'),
    'delta_t_seconds': find(r'ΔT =\s*([\d.]+) s'),
    'greatest_eclipse': {k: ge[k] for k in (
        'instant_tdt', 'instant_ut', 'jd', 'latitude_deg', 'longitude_deg',
        'sun_altitude_deg', 'sun_azimuth_deg', 'path_width_km',
        'central_duration', 'gamma', 'magnitude')},
    'greatest_duration': gd,
    'lunar_radius_constants': {
        'k1_penumbra': find(r'k1 =\s*([\d.]+)'),
        'k2_umbra': find(r'k2 =\s*([\d.]+)'),
    },
    'elements': elements,
    'tan_f1': find(r'Tan ƒ1 =\s*([\d.]+)'),
    'tan_f2': find(r'Tan ƒ2 =\s*([\d.]+)'),
    'valid_tdt_hours': [find(r'valid over the period\s+(-?[\d.]+)'),
                        find(r'valid over the period\s+-?[\d.]+ \S+ t0 \S+\s+(-?[\d.]+)')],
    'ephemerides': find(r'Ephemerides =\s*(\S+)', str),
    'saros': find(r'Saros Series =\s*(\d+)', int),
    'lunation': find(r'Lunation No\. =\s*(\d+)', int),
    'provenance': {
        'source': 'NASA GSFC eclipse web site, Besselian elements page',
        'url': url,
        'retrieved': date.today().isoformat(),
        'attribution': "Eclipse Predictions by Fred Espenak, NASA's GSFC",
        'publication': 'Five Millennium Canon of Solar Eclipses: -1999 to +3000',
        'delta_t_basis': 'the value NASA gives on the elements page',
        'path_edge_accuracy_km': '1-2 (limited by lunar limb profile)',
    },
}
DEST.write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(f'eclipse           {out["label"]}')
print(f'delta T           {out["delta_t_seconds"]} s')
print(f'greatest eclipse  {ge["latitude_deg"]}, {ge["longitude_deg"]}  '
      f'{ge["central_duration"]}  sun {ge["sun_altitude_deg"]}°')
print(f'wrote             {DEST.relative_to(ROOT)}')
