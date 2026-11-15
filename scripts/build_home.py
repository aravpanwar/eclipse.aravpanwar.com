# Totality Path & Nearby Locations
# Copyright (C) 2026 Arav Panwar
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. See <https://www.gnu.org/licenses/>.

"""Write the later eclipses' cards on the homepage from the build output.

    python scripts/build_home.py

The soonest eclipse still to come has the large block at the top, written by
hand. Every other computed eclipse gets a card here, between the cards
markers in docs/index.html: its date, the countries in totality west to
east, the longest totality and the number of places, linked to its map.
"""
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from eclipse import event

HOME = ROOT / 'docs' / 'index.html'
built = [e for e in event.available()
         if (ROOT / 'data' / 'out' / f'{e}-places.json').exists()
         and (ROOT / 'docs' / 'solar-eclipse' / e / 'index.html').exists()]
featured = min((e for e in built if event.day(e) >= date.today()), default=None)


def card(e):
    blob = json.loads((ROOT / 'data' / 'out' / f'{e}-places.json').read_text(encoding='utf-8'))
    places = blob['places']
    window = event.settings(e).get('lon_window')
    lons: dict[str, list[float]] = {}
    for p in places:
        lons.setdefault(p['country'], []).append(event.frame(p['longitude'], window))
    countries = sorted(lons, key=lambda c: sum(lons[c]) / len(lons[c]))
    peak = int(blob['event']['greatest_duration']['duration_seconds'])
    url = f'/solar-eclipse/{e}/'
    return f'''    <li class="card">
      <a href="{url}">
        <img src="/thumbs/{e}.webp" alt="" width="640" height="400" loading="lazy">
        <div class="b">
          <h3>{event.long_date(e)}</h3>
          <p class="where">{html.escape(", ".join(countries))}</p>
          <p class="d">{peak // 60}:{peak % 60:02d} longest, {len(places):,} places</p>
        </div>
      </a>
    </li>'''


cards = '\n'.join(card(e) for e in built if e != featured)
page = HOME.read_text(encoding='utf-8')
marked = re.compile(r'(<!-- cards: scripts/build_home.py -->\n).*?(    <!-- /cards -->)', re.S)
if not marked.search(page):
    sys.exit('expected the cards markers in docs/index.html')
HOME.write_text(marked.sub(lambda m: m[1] + cards + '\n' + m[2], page), encoding='utf-8')
print(f'featured          {featured}')
print(f'cards             {", ".join(e for e in built if e != featured)}')
print(f'wrote             {HOME.relative_to(ROOT)}')
