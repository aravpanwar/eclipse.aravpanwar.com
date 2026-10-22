# Totality Path & Nearby Locations
# Copyright (C) 2026 Arav Panwar
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. See <https://www.gnu.org/licenses/>.

"""Trim the dataset for the browser.

Short keys and rounded numbers: the full CSV stays the download, this is what
the page loads on every visit.

Local clock times of totality, and of the peak at towns outside the path,
are worked out here, not in the browser, so
every visitor sees the same times whatever their browser's time-zone data.
That needs a current tz database: install tzdata 2026.3 or later.
"""
import importlib.metadata
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[1]
EVENT = '2027-08-02'

src = json.loads((ROOT / 'data' / 'out' / f'{EVENT}-places.json')
                 .read_text(encoding='utf-8'))
OUT = ROOT / 'docs' / 'data'
OUT.mkdir(parents=True, exist_ok=True)

# Morocco moved to permanent UTC+0 on 2026-09-20 (tz 2026c). Older tz data
# puts it on UTC+1 and every Moroccan time an hour late, so refuse to build.
DAY = datetime.fromisoformat(f'{EVENT}T00:00:00+00:00')
if (DAY + timedelta(hours=9)).astimezone(ZoneInfo('Africa/Casablanca')).utcoffset():
    sys.exit('expected tz data from 2026c or later (Morocco on UTC+0): pip install "tzdata>=2026.3"')
try:
    TZ_VERSION = importlib.metadata.version('tzdata')
except importlib.metadata.PackageNotFoundError:
    TZ_VERSION = 'system'


def local_times(p):
    """Start and end of totality as local HH:MM, truncated, and the UTC offset in minutes."""
    mid = DAY + timedelta(hours=p['max_eclipse_ut_hours'])
    half = timedelta(seconds=p['duration_seconds'] / 2)
    start = (mid - half).replace(microsecond=0).astimezone(ZoneInfo(p['timezone']))
    end = (mid + half).astimezone(ZoneInfo(p['timezone']))
    return start.strftime('%H:%M'), end.strftime('%H:%M'), int(start.utcoffset().total_seconds() // 60)

places = []
for p in src['places']:
    t0, t1, offset = local_times(p)
    places.append({
        'i': p['geonameid'],
        'n': p['name'],
        'c': p['country_code'],
        'y': round(p['latitude'], 4),
        'x': round(p['longitude'], 4),
        'p': p['population'],
        'd': round(p['duration_seconds'], 1),
        's': round(p['seconds_sacrificed'], 1),
        'a': round(p['sun_altitude_deg'], 1),
        'u': round(p['max_eclipse_ut_hours'], 4),
        'k': p['distance_from_centerline_km'],
        'w': p['mean_cloud_percent'],
        'q': p['clear_sky_probability'],
        'l': p['lodging_within_25km'],
        'L': p['lodging_within_80km'],
        'z': p['timezone'],
        't0': t0,
        't1': t1,
        'o': offset,
    })

adv = {}
for cc, a in src['advisories']['by_country'].items():
    adv[cc] = {
        'country': a['country'],
        'worst': a['worst'],
        'label': a['labels'][0] if a['labels'] else None,
        'regions': a['regions'],
        'reviewed': (a['reviewed_at'] or '')[:10],
        'url': a['url'],
    }

payload = {
    'event': {
        'id': src['event']['id'],
        'label': src['event']['label'],
        'delta_t': src['event']['delta_t_seconds'],
        'peak': src['event']['greatest_duration']['duration_seconds'],
        'peak_lat': src['event']['greatest_duration']['latitude_deg'],
        'peak_lon': src['event']['greatest_duration']['longitude_deg'],
        'tz_version': TZ_VERSION,
    },
    'caveats': src['event']['caveats'],
    'sources': src['sources'],
    'advisories': adv,
    'issuer': src['advisories']['issuer'],
    'places': places,
}

dest = OUT / f'{EVENT}-places.json'
dest.write_text(json.dumps(payload, separators=(',', ':'), ensure_ascii=False),
                encoding='utf-8')
print(f'places  {len(places)}')
print(f'wrote   {dest.relative_to(ROOT)} ({dest.stat().st_size // 1024} KB)')

outside_src = json.loads((ROOT / 'data' / 'out' / f'{EVENT}-outside.json')
                         .read_text(encoding='utf-8'))
outside = []
for p in outside_src['places']:
    mid = (DAY + timedelta(hours=p['max_eclipse_ut_hours'])).astimezone(ZoneInfo(p['timezone']))
    outside.append({
        'i': p['geonameid'],
        'n': p['name'],
        'c': p['country_code'],
        'y': round(p['latitude'], 4),
        'x': round(p['longitude'], 4),
        'p': p['population'],
        'v': round(p['obscuration_percent'], 1),
        'm': mid.strftime('%H:%M'),
        'o': int(mid.utcoffset().total_seconds() // 60),
        'a': round(p['sun_altitude_deg'], 1),
        'e': round(p['km_to_edge_of_totality'], 1),
        'k': round(p['km_to_centre_line'], 1),
    })
outside.sort(key=lambda r: r['e'])

dest = OUT / f'{EVENT}-outside.json'
dest.write_text(json.dumps({
    'range_km': outside_src['range_km'],
    'countries': outside_src['countries'],
    'places': outside,
}, separators=(',', ':'), ensure_ascii=False), encoding='utf-8')
print(f'outside {len(outside)}')
print(f'wrote   {dest.relative_to(ROOT)} ({dest.stat().st_size // 1024} KB)')
