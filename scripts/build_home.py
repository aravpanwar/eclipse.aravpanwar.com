# Totality Path & Nearby Locations
# Copyright (C) 2026 Arav Panwar
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. See <https://www.gnu.org/licenses/>.

"""Write the homepage's eclipses from the build output, by today's date.

    python scripts/build_home.py

The soonest eclipse still to come gets the large block at the top, the
others still to come get cards below it, soonest first, and the ones that
have passed go in a section at the bottom, latest first. An eclipse counts
as to come until the end of its own day, so the page changes the day after.
Each part is written between its markers in docs/index.html, the link
preview of it and of the method page points at the featured eclipse, and
docs/sitemap.xml lists every page. A scheduled
GitHub Action runs this every day, so the page moves on by itself.
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
TODAY = date.today()
built = [e for e in event.available()
         if (ROOT / 'data' / 'out' / f'{e}-places.json').exists()
         and (ROOT / 'docs' / 'solar-eclipse' / e / 'index.html').exists()]
coming = [e for e in built if event.day(e) >= TODAY]
past = sorted((e for e in built if event.day(e) < TODAY), reverse=True)
featured = coming[0] if coming else None
later = coming[1:]


def facts(e):
    """The places, the countries in totality west to east, and the longest totality."""
    blob = json.loads((ROOT / 'data' / 'out' / f'{e}-places.json').read_text(encoding='utf-8'))
    places = blob['places']
    window = event.settings(e).get('lon_window')
    lons: dict[str, list[float]] = {}
    names = {}
    for p in places:
        lons.setdefault(p['country_code'], []).append(event.frame(p['longitude'], window))
        names[p['country_code']] = p['country']
    order = sorted(lons, key=lambda c: sum(lons[c]) / len(lons[c]))
    peak = int(blob['event']['greatest_duration']['duration_seconds'])
    return places, [(c, names[c]) for c in order], peak


def card(e):
    places, countries, peak = facts(e)
    where = html.escape(', '.join(name for _, name in countries))
    return f'''    <li class="card">
      <a href="/solar-eclipse/{e}/">
        <img src="/thumbs/{e}.webp" alt="" width="640" height="400" loading="lazy">
        <div class="b">
          <h3>{event.long_date(e)}</h3>
          <p class="where">{where}</p>
          <p class="d">{peak // 60}:{peak % 60:02d} longest, {len(places):,} places</p>
        </div>
      </a>
    </li>'''


def feature(e):
    places, countries, peak = facts(e)
    url = f'/solar-eclipse/{e}/'
    has_cloud = any(p['mean_cloud_percent'] is not None for p in places)
    told = ('local times and cloud cover.' if has_cloud else
            'local times. Cloud cover is added closer to the date.')
    chips = '\n'.join(f'        <li><a href="{url}?c={c}">{html.escape(name)}</a></li>'
                      for c, name in countries)
    return f'''  <article class="feature">
    <a class="pic" href="{url}" tabindex="-1" aria-hidden="true"><img
      src="/thumbs/{e}.webp" srcset="/thumbs/{e}.webp 1x, /thumbs/{e}@2x.webp 2x"
      alt="" width="640" height="400"></a>
    <div class="body">
      <h3><a href="{url}">{event.long_date(e)}</a></h3>
      <p class="when" id="countdown" data-date="{e}" hidden></p>
      <p class="dur">Up to <b>{peak // 60} min {peak % 60} s</b> of totality, {len(places):,} places mapped</p>
      <p class="what"><b>Totality Path &amp; Nearby Locations</b>: every populated
      place inside the path, ranked by how long totality lasts there, with
      {told}</p>
      <p class="chiplabel" id="chipsLabel">Go straight to a country</p>
      <ul class="chips" aria-labelledby="chipsLabel">
{chips}
      </ul>
      <span class="gap"></span>
      <a class="go" href="{url}">Open the map</a>
    </div>
  </article>'''


def put(page, name, body):
    """Replace what sits between <!-- name: scripts/build_home.py --> and <!-- /name -->."""
    marked = re.compile(rf'(<!-- {name}: scripts/build_home.py -->).*?(\n *<!-- /{name} -->)', re.S)
    if not marked.search(page):
        sys.exit(f'expected the {name} markers in docs/index.html')
    return marked.sub(lambda m: m[1] + ('\n' + body if body else '') + m[2], page)


def section(page, name, shown):
    """Show or hide a section, marked by data-section on its element."""
    return re.sub(rf'(<section class="eclipses" data-section="{name}")( hidden)?',
                  lambda m: m[1] + ('' if shown else ' hidden'), page)


def preview(page, e):
    """Point a page's link-preview card at an eclipse's own card."""
    places, _, _ = facts(e)
    # The countries of the westernmost and easternmost towns, as on the
    # eclipse's own page.
    window = event.settings(e).get('lon_window')
    west = min(places, key=lambda p: event.frame(p['longitude'], window))['country']
    east = max(places, key=lambda p: event.frame(p['longitude'], window))['country']
    alt = (f'Map of the path of totality of {event.long_date(e)}, '
           f'{event.where(west, east)}, with the {len(places):,} places inside it marked.')
    page = re.sub(r'(<meta property="og:image" content=")[^"]*(">)',
                  lambda m: f'{m[1]}https://eclipse.aravpanwar.com/og/{e}.png{m[2]}', page)
    return re.sub(r'(<meta property="og:image:alt" content=")[^"]*(">)',
                  lambda m: m[1] + html.escape(alt) + m[2], page)


# The method page has no eclipse of its own, so it shares the homepage's card.
shown = featured or (past[0] if past else None)
METHOD = ROOT / 'docs' / 'method.html'
if shown:
    METHOD.write_text(preview(METHOD.read_text(encoding='utf-8'), shown),
                      encoding='utf-8', newline='\n')

page = HOME.read_text(encoding='utf-8')
if shown:
    page = preview(page, shown)
page = put(page, 'feature', feature(featured) if featured else '')
page = put(page, 'cards', '\n'.join(card(e) for e in later))
page = put(page, 'past', '\n'.join(card(e) for e in past))
page = section(page, 'later', bool(later))
page = section(page, 'past', bool(past))
HOME.write_text(page, encoding='utf-8', newline='\n')

# The sitemap lists the same pages, so it is written from the same list.
SITE = 'https://eclipse.aravpanwar.com'
urls = [f'{SITE}/', f'{SITE}/method.html', *(f'{SITE}/solar-eclipse/{e}/' for e in built)]
SITEMAP = ROOT / 'docs' / 'sitemap.xml'
SITEMAP.write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                   '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                   + ''.join(f'  <url><loc>{u}</loc></url>\n' for u in urls)
                   + '</urlset>\n', encoding='utf-8', newline='\n')
print(f'today             {TODAY}')
print(f'featured          {featured}')
print(f'later             {", ".join(later) or "none"}')
print(f'past              {", ".join(past) or "none"}')
print(f'wrote             {HOME.relative_to(ROOT)}, {SITEMAP.relative_to(ROOT)}')
