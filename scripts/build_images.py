# Totality Path & Nearby Locations
# Copyright (C) 2026 Arav Panwar
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. See <https://www.gnu.org/licenses/>.

"""Draw the link-preview card, the homepage thumbnails and the site icons.

The card is drawn from the same outlines, path and places as the site, not
screenshotted from the map, so it carries no basemap tiles and needs no tile
credit. Requires Pillow. Fonts and outlines are downloaded into data/cache on
first run.
"""
import json
import math
import re
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from eclipse import event  # noqa: E402

EVENT = event.from_argv()
DOCS = ROOT / 'docs'
DATA = DOCS / 'data'
CACHE = ROOT / 'data' / 'cache'
UA = {'User-Agent': 'eclipse.aravpanwar.com/0.1 (+https://github.com/aravpanwar/eclipse.aravpanwar.com)'}

NE_URL = ('https://raw.githubusercontent.com/nvkelso/natural-earth-vector/'
          'v5.1.2/geojson/ne_10m_admin_0_countries_gbr.geojson')
# The site's faces, as variable TTFs from Google Fonts: Pillow cannot read
# the woff2 files the site serves.
GFONTS = 'https://raw.githubusercontent.com/google/fonts/main/ofl'
SANS = f'{GFONTS}/schibstedgrotesk/SchibstedGrotesk%5Bwght%5D.ttf'
SERIF = f'{GFONTS}/sourceserif4/SourceSerif4%5Bopsz,wght%5D.ttf'
FONTS = {
    'bold': (SANS, 750),
    'semibold': (SANS, 600),
    'regular': (SANS, 400),
    'serif': (SERIF, 400),
}

# The site's palette (docs/style.css).
GROUND = '#faf8f2'
PAPER = '#fffdf8'
INK = '#141414'
DIM = '#6b6862'
LINE = '#e2dccf'
ACCENT = '#1e6a45'
RAIL = '#1e4a33'
RAIL_INK = '#f6f1e4'
OCHRE = '#d9a441'
SEA = '#dde6e1'
EDGE = '#86ad97'
DOT = '#3d382f'


def cached(url):
    dest = CACHE / url.rsplit('/', 1)[1].replace('%5B', '[').replace('%5D', ']')
    if not dest.exists():
        print(f'downloading       {url}')
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                    timeout=134) as resp:
            dest.write_bytes(resp.read())
    return dest


def font(kind, px):
    url, weight = FONTS[kind]
    f = ImageFont.truetype(str(cached(url)), px)
    # Optical size follows the pixel size where the face has that axis.
    axes = [weight if a['name'] in (b'Weight', 'Weight') else
            min(max(px / S, a['minimum']), a['maximum'])
            for a in f.get_variation_axes()]
    f.set_variation_by_axes(axes)
    return f


def rgba(hex_colour, alpha):
    h = hex_colour.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (round(alpha * 255),)


def polygons(geom):
    if geom['type'] == 'Polygon':
        return [geom['coordinates']]
    if geom['type'] == 'MultiPolygon':
        return geom['coordinates']
    return []


# ---------- link-preview card ----------

W, H = 1200, 630
S = 3                      # drawn at 3x and scaled down, for smooth edges
# The card's framing is chosen by hand for each event, in data/events.json:
# the top latitude, the latitude whose scale it keeps, the left longitude and
# how many degrees of latitude fit its height.
OG = event.settings(EVENT).get('og')


def project(lon, lat):
    k = H / OG['lat_span']
    x = (lon - OG['lon_left']) * math.cos(math.radians(OG['lat0'])) * k
    y = (OG['lat_top'] - lat) * k
    return x * S, y * S


def card():
    if not OG:
        print('og card           SKIP (no og framing in data/events.json)')
        return
    land = json.loads(cached(NE_URL).read_text(encoding='utf-8'))
    path = json.loads((DATA / f'{EVENT}-path.geojson').read_text(encoding='utf-8'))
    places = json.loads((DATA / f'{EVENT}-places.json').read_text(encoding='utf-8'))

    img = Image.new('RGBA', (W * S, H * S), SEA)
    d = ImageDraw.Draw(img)
    for f in land['features']:
        for poly in polygons(f['geometry']):
            ring = [project(*c) for c in poly[0]]
            xs = [p[0] for p in ring]
            ys = [p[1] for p in ring]
            if max(xs) < 0 or min(xs) > W * S or max(ys) < 0 or min(ys) > H * S:
                continue
            d.polygon(ring, fill=GROUND, outline=LINE, width=S)

    over = Image.new('RGBA', img.size, (0, 0, 0, 0))
    o = ImageDraw.Draw(over)
    for f in path['features']:
        if f['properties']['kind'] == 'umbra':
            ring = [project(*c) for c in f['geometry']['coordinates'][0]]
            o.polygon(ring, fill=rgba(ACCENT, 0.16))
            o.line(ring, fill=rgba(EDGE, 1), width=round(1.4 * S))
    for f in path['features']:
        if f['properties']['kind'] == 'centerline':
            o.line([project(*c) for c in f['geometry']['coordinates']],
                   fill=rgba(ACCENT, 1), width=round(2.2 * S), joint='curve')
    for p in places['places']:
        x, y = project(p['x'], p['y'])
        r = (1.1 + 2.1 * min(1.0, math.log10(max(p['p'], 1000) / 1000) / 3.3)) * S
        o.ellipse((x - r, y - r, x + r, y + r), fill=rgba(DOT, 0.8))
    img = Image.alpha_composite(img, over)

    # Text panel over the empty Sahara, clear of the path.
    d = ImageDraw.Draw(img)
    px, py, pw, ph = 36 * S, 352 * S, 660 * S, 242 * S
    d.rectangle((px, py, px + pw, py + ph), fill=PAPER, outline=LINE, width=S)
    d.rectangle((px, py, px + pw, py + 4 * S), fill=ACCENT)
    x = px + 30 * S
    d.text((x, py + 26 * S), 'Totality Path & Nearby Locations',
           font=font('bold', 36 * S), fill=INK)
    d.text((x, py + 82 * S), f'Total solar eclipse, {event.long_date(EVENT)}',
           font=font('serif', 28 * S), fill='#45423d')
    n = len(places['places'])
    # Advisories also cover countries with towns outside the path only.
    countries = len({p['c'] for p in places['places']})
    d.text((x, py + 136 * S),
           f'{n} places in {countries} countries, ranked by seconds of totality lost',
           font=font('regular', 16 * S), fill=DIM)
    d.text((x, py + 184 * S), 'eclipse.aravpanwar.com',
           font=font('bold', 21 * S), fill=ACCENT)
    d.text((px + pw - 30 * S, py + ph - 20 * S), 'Places: GeoNames',
           font=font('regular', 12 * S), fill='#75716a', anchor='rs')

    out = img.resize((W, H), Image.LANCZOS).convert('RGB')
    dest = DOCS / 'og.png'
    out.save(dest, optimize=True)
    print(f'wrote             {dest.relative_to(ROOT)} '
          f'({dest.stat().st_size // 1024} KB)')


# ---------- homepage thumbnails ----------

TW, TH = 640, 400          # 16:10, shown at about half that on the homepage

# Eclipses on the homepage not yet computed here. Their paths are drawn from
# NASA's published path tables (Fred Espenak, NASA GSFC), so the thumbnail
# shows where totality falls before this site has computed anything.
NASA_PATHS = {
    '2028-07-22': 'SE2028Jul22T', '2030-11-25': 'SE2030Nov25T',
    '2033-03-30': 'SE2033Mar30T', '2034-03-20': 'SE2034Mar20T',
    '2035-09-02': 'SE2035Sep02T',
}
NASA_URL = 'https://eclipse.gsfc.nasa.gov/SEpath/SEpath2001/{}path.html'
_PAIR = re.compile(r'(\d{2}) (\d{2}\.\d)([NS])\s+(\d{3}) (\d{2}\.\d)([EW])')


def _lonlat(text):
    m = _PAIR.search(text)
    if not m:
        return None
    lat = int(m[1]) + float(m[2]) / 60
    lon = int(m[4]) + float(m[5]) / 60
    return (-lon if m[6] == 'W' else lon, -lat if m[3] == 'S' else lat)


def nasa_path(slug):
    """North limit, south limit and centre line from a NASA path table.

    Rows are fixed-width. Where the shadow edge runs off the Earth's limb a
    limit is blank, so each line keeps only the points it has.
    """
    page = cached(NASA_URL.format(slug)).read_text(encoding='latin-1')
    rows = [r for r in re.sub(r'<[^>]+>', '', page).splitlines()
            if re.match(r'^\s*(Limits|\d{2}:\d{2})\s', r)]
    north = [p for p in (_lonlat(r[9:27]) for r in rows) if p]
    south = [p for p in (_lonlat(r[29:47]) for r in rows) if p]
    centre = [p for p in (_lonlat(r[49:67]) for r in rows) if p]
    return north + south[::-1], centre


def thumb(ring, centre, dots, dest, scale=1):
    """A map fitted to one path: land, the band of totality, the centre line.

    scale 2 draws the same picture at twice the size, lines and dots included,
    for high-density screens.
    """
    tw, th, z = TW * scale, TH * scale, S * scale
    # Paths that cross 180 degrees are drawn in 0..360 longitude.
    wrap = max(x for x, _ in centre) - min(x for x, _ in centre) > 180
    fix = (lambda x: x + 360 if x < 0 else x) if wrap else (lambda x: x)
    ring = [(fix(x), y) for x, y in ring]
    centre = [(fix(x), y) for x, y in centre]

    xs = [x for x, _ in ring]
    ys = [y for _, y in ring]
    lat_c = (min(ys) + max(ys)) / 2
    kx = math.cos(math.radians(lat_c))
    # Fit the band with a margin, then widen the short side to 16:10.
    w = (max(xs) - min(xs)) * kx * 1.25 + 6
    h = (max(ys) - min(ys)) * 1.25 + 6
    if w / h > TW / TH:
        h = w * TH / TW
    else:
        w = h * TW / TH
    cx, cy = (min(xs) + max(xs)) / 2, lat_c
    k = tw * S / w

    def project(lon, lat):
        return ((lon - cx) * kx * k + tw * S / 2, (cy - lat) * k + th * S / 2)

    land = json.loads(cached(NE_URL).read_text(encoding='utf-8'))
    img = Image.new('RGBA', (tw * S, th * S), SEA)
    d = ImageDraw.Draw(img)
    for f in land['features']:
        for poly in polygons(f['geometry']):
            for shift in ((0, 360) if wrap else (0,)):
                pts = [project(x + shift, y) for x, y in poly[0]]
                px = [p[0] for p in pts]
                py = [p[1] for p in pts]
                if max(px) < 0 or min(px) > tw * S or max(py) < 0 or min(py) > th * S:
                    continue
                d.polygon(pts, fill=GROUND, outline=LINE, width=z)

    over = Image.new('RGBA', img.size, (0, 0, 0, 0))
    o = ImageDraw.Draw(over)
    band = [project(*p) for p in ring]
    o.polygon(band, fill=rgba(ACCENT, 0.2))
    o.line(band + band[:1], fill=rgba(EDGE, 1), width=round(1.2 * z))
    o.line([project(*p) for p in centre], fill=rgba(ACCENT, 1),
           width=round(2 * z), joint='curve')
    for x, y, pop in dots:
        px, py = project(fix(x), y)
        r = (1.0 + 1.6 * min(1.0, math.log10(max(pop, 1000) / 1000) / 3.3)) * z
        o.ellipse((px - r, py - r, px + r, py + r), fill=rgba(DOT, 0.8))
    img = Image.alpha_composite(img, over)
    img.resize((tw, th), Image.LANCZOS).convert('RGB').save(dest, quality=82, method=6)
    print(f'wrote             {dest.relative_to(ROOT)} ({dest.stat().st_size // 1024} KB)')


def thumbs():
    out = DOCS / 'thumbs'
    out.mkdir(exist_ok=True)
    # The computed eclipse is drawn from this site's own path and places.
    path = json.loads((DATA / f'{EVENT}-path.geojson').read_text(encoding='utf-8'))
    places = json.loads((DATA / f'{EVENT}-places.json').read_text(encoding='utf-8'))
    feats = {f['properties']['kind']: f['geometry']['coordinates'] for f in path['features']}
    args = ([tuple(p) for p in feats['umbra'][0]], [tuple(p) for p in feats['centerline']],
            [(p['x'], p['y'], p['p']) for p in places['places']])
    thumb(*args, out / f'{EVENT}.webp')
    # The homepage shows this one about 560 px wide, so it also gets a 2x copy.
    thumb(*args, out / f'{EVENT}@2x.webp', scale=2)
    # An eclipse computed here is drawn by its own run, from its own data.
    for other, slug in NASA_PATHS.items():
        if other == EVENT or (DATA / f'{other}-path.geojson').exists():
            continue
        ring, centre = nasa_path(slug)
        thumb(ring, centre, [], out / f'{other}.webp')


# ---------- icons ----------

# An eclipse on the forest square of the AP mark on www.aravpanwar.com: the
# Moon's dark disc inside a cream corona, and the ochre bead of the diamond
# ring where the last of the Sun shows. Square, like the AP mark; iOS rounds
# the touch icon itself.
MOON = '#123222'
BEAD = (16 + 10.6 * math.cos(math.radians(45)), 16 - 10.6 * math.sin(math.radians(45)))
ICON_SVG = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<rect width="32" height="32" fill="{RAIL}"/>
<circle cx="16" cy="16" r="10.6" fill="none" stroke="{RAIL_INK}" stroke-width="2.2"/>
<circle cx="16" cy="16" r="8.6" fill="{MOON}"/>
<circle cx="{BEAD[0]:.2f}" cy="{BEAD[1]:.2f}" r="3" fill="{OCHRE}"/>
</svg>
'''


def icon(px):
    """The same drawing as ICON_SVG, rasterised at px by px."""
    s = px * 8 / 32
    img = Image.new('RGBA', (px * 8, px * 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, px * 8 - 1, px * 8 - 1), fill=RAIL)
    r_out, r_in = (10.6 + 1.1) * s, (10.6 - 1.1) * s
    c = 16 * s
    d.ellipse((c - r_out, c - r_out, c + r_out, c + r_out), fill=RAIL_INK)
    d.ellipse((c - r_in, c - r_in, c + r_in, c + r_in), fill=RAIL)
    d.ellipse((c - 8.6 * s, c - 8.6 * s, c + 8.6 * s, c + 8.6 * s), fill=MOON)
    bx, by, br = BEAD[0] * s, BEAD[1] * s, 3 * s
    d.ellipse((bx - br, by - br, bx + br, by + br), fill=OCHRE)
    return img.resize((px, px), Image.LANCZOS)


def icons():
    (DOCS / 'favicon.svg').write_text(ICON_SVG, encoding='utf-8')
    icon(48).save(DOCS / 'favicon.ico', sizes=[(16, 16), (32, 32), (48, 48)])
    # iOS draws its own rounded corners and ignores transparency.
    touch = Image.new('RGB', (180, 180), RAIL)
    touch.paste(icon(180), (0, 0), icon(180))
    touch.save(DOCS / 'apple-touch-icon.png', optimize=True)
    for name in ('favicon.svg', 'favicon.ico', 'apple-touch-icon.png'):
        print(f'wrote             docs/{name}')


card()
thumbs()
icons()
