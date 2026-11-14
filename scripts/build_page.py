# Totality Path & Nearby Locations
# Copyright (C) 2026 Arav Panwar
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. See <https://www.gnu.org/licenses/>.

"""Write docs/solar-eclipse/<event>/index.html from templates/event.html.

The page itself is the same for every eclipse; what differs is the date,
the counts and the countries in its text and link previews, filled in here
from the build output. Everything else app.js reads from the data files.
"""
import html
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from eclipse import event

EVENT = event.from_argv()
KINDS = {'T': 'Total', 'H': 'Hybrid', 'A': 'Annular', 'P': 'Partial'}

meta = json.loads((ROOT / 'data' / 'elements' / f'{EVENT}.json').read_text(encoding='utf-8'))
places = json.loads((ROOT / 'data' / 'out' / f'{EVENT}-places.json')
                    .read_text(encoding='utf-8'))['places']
outside = json.loads((ROOT / 'data' / 'out' / f'{EVENT}-outside.json').read_text(encoding='utf-8'))
settings = event.settings(EVENT)

# The countries of the westernmost and easternmost towns in totality.
west = min(places, key=lambda p: p['longitude'])['country']
east = max(places, key=lambda p: p['longitude'])['country']

kind = KINDS[meta['type']]
date = event.long_date(EVENT)
has_cloud = any(p['mean_cloud_percent'] is not None for p in places)
told = ['how long totality lasts there', 'local times',
        *(['cloud'] if has_cloud else []), 'places to stay']
description = (f'Every populated place inside the path of the {date} {kind.lower()} '
               f'solar eclipse, with {", ".join(told[:-1])} and {told[-1]}.')
view = settings.get('map')
map_attrs = (f' data-center="{view["center"][0]},{view["center"][1]}" data-zoom="{view["zoom"]}"'
             if view else '')

values = {
    'event': EVENT,
    'map': map_attrs,
    'date': date,
    'kind': kind,
    'month': event.month_name(EVENT),
    'description': description,
    'first': west,
    'last': east,
    'count': f'{len(places):,}',
    'range_km': outside['range_km'],
}
page = (ROOT / 'templates' / 'event.html').read_text(encoding='utf-8')


def fill(m):
    v = values[m[1]]
    # The map attributes are markup already; everything else is text.
    return v if m[1] == 'map' else html.escape(str(v), quote=True)


page = re.sub(r'\{\{(\w+)\}\}', fill, page)
dest = ROOT / 'docs' / 'solar-eclipse' / EVENT / 'index.html'
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(page, encoding='utf-8')
print(f'places            {values["count"]} from {values["first"]} to {values["last"]}')
print(f'cloud             {"yes" if has_cloud else "none yet, the page says so"}')
print(f'wrote             {dest.relative_to(ROOT)}')
