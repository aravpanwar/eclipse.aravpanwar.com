# Totality Path & Nearby Locations
# Copyright (C) 2026 Arav Panwar
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. See <https://www.gnu.org/licenses/>.

"""Draw the eclipse's link-preview card, its homepage thumbnails and the site icons.

    python scripts/build_images.py <event>

The card is drawn from the same outlines, path and places as the site, not
screenshotted from the map, so it carries no basemap tiles and needs no tile
credit. Requires Pillow. Fonts and outlines are downloaded into data/cache on
first run.
"""
import json
import math
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


# ---------- the map ----------

def fitted_map(ring, centre, dots, tw, th, z):
    """Land, the band of totality, the centre line and the towns, fitted to one path.

    Drawn at z times tw by th, to be scaled down for smooth edges.
    """
    # Paths that cross 180 degrees run on past it in this site's data, so
    # their land is drawn a second time, 360 degrees east.
    wrap = max(x for x, _ in centre) > 180
    fix = (lambda x: x + 360 if x < 0 else x) if wrap else (lambda x: x)
    ring = [(fix(x), y) for x, y in ring]
    centre = [(fix(x), y) for x, y in centre]

    xs = [x for x, _ in ring]
    ys = [y for _, y in ring]
    lat_c = (min(ys) + max(ys)) / 2
    kx = math.cos(math.radians(lat_c))
    # Fit the band with a margin, then widen the short side to the frame.
    w = (max(xs) - min(xs)) * kx * 1.25 + 6
    h = (max(ys) - min(ys)) * 1.25 + 6
    if w / h > tw / th:
        h = w * th / tw
    else:
        w = h * tw / th
    cx, cy = (min(xs) + max(xs)) / 2, lat_c
    k = tw * z / w

    def project(lon, lat):
        return ((lon - cx) * kx * k + tw * z / 2, (cy - lat) * k + th * z / 2)

    land = json.loads(cached(NE_URL).read_text(encoding='utf-8'))
    img = Image.new('RGBA', (tw * z, th * z), SEA)
    d = ImageDraw.Draw(img)
    for f in land['features']:
        for poly in polygons(f['geometry']):
            for shift in ((0, 360) if wrap else (0,)):
                pts = [project(x + shift, y) for x, y in poly[0]]
                px = [p[0] for p in pts]
                py = [p[1] for p in pts]
                if max(px) < 0 or min(px) > tw * z or max(py) < 0 or min(py) > th * z:
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
    return Image.alpha_composite(img, over)


S = 3                      # drawn at 3x and scaled down, for smooth edges
path = json.loads((DATA / f'{EVENT}-path.geojson').read_text(encoding='utf-8'))
places = json.loads((DATA / f'{EVENT}-places.json').read_text(encoding='utf-8'))
feats = {f['properties']['kind']: f['geometry']['coordinates'] for f in path['features']}
SHAPE = ([tuple(p) for p in feats['umbra'][0]], [tuple(p) for p in feats['centerline']],
         [(p['x'], p['y'], p['p']) for p in places['places']])


# ---------- link-preview card ----------

W, H = 1200, 630
MAP_W = 700                # the map on the left, the text on the right


def card():
    img = Image.new('RGBA', (W * S, H * S), PAPER)
    img.paste(fitted_map(*SHAPE, MAP_W, H, S), (0, 0))
    d = ImageDraw.Draw(img)
    d.line((MAP_W * S, 0, MAP_W * S, H * S), fill=LINE, width=S)
    d.rectangle((MAP_W * S, 0, W * S, 6 * S), fill=ACCENT)

    n = len(places['places'])
    countries = len({p['c'] for p in places['places']})
    peak = int(places['event']['peak'])
    x = (MAP_W + 44) * S
    d.text((x, 70 * S), 'Total solar eclipse', font=font('regular', 22 * S), fill=DIM)
    d.text((x, 104 * S), event.long_date(EVENT), font=font('bold', 50 * S), fill=INK)
    d.text((x, 196 * S), f'Up to {peak // 60} min {peak % 60} s of totality',
           font=font('serif', 27 * S), fill='#45423d')
    d.text((x, 240 * S), f'{n:,} places in {countries} '
           f'{"country" if countries == 1 else "countries"}',
           font=font('serif', 27 * S), fill='#45423d')
    d.text((x, 470 * S), 'Totality Path & Nearby Locations',
           font=font('bold', 22 * S), fill=INK)
    d.text((x, 506 * S), 'eclipse.aravpanwar.com',
           font=font('bold', 22 * S), fill=ACCENT)
    d.text((W * S - 30 * S, H * S - 22 * S), 'Places: GeoNames',
           font=font('regular', 12 * S), fill='#75716a', anchor='rs')

    dest = DOCS / 'og' / f'{EVENT}.png'
    dest.parent.mkdir(exist_ok=True)
    img.resize((W, H), Image.LANCZOS).convert('RGB').save(dest, optimize=True)
    print(f'wrote             {dest.relative_to(ROOT)} '
          f'({dest.stat().st_size // 1024} KB)')


# ---------- homepage thumbnails ----------

TW, TH = 640, 400          # 16:10, shown at about half that on the homepage


def thumbs():
    out = DOCS / 'thumbs'
    out.mkdir(exist_ok=True)
    # The featured eclipse is shown about 560 px wide, so each also gets a 2x copy.
    for scale, name in ((1, f'{EVENT}.webp'), (2, f'{EVENT}@2x.webp')):
        img = fitted_map(*SHAPE, TW, TH, S * scale)
        dest = out / name
        img.resize((TW * scale, TH * scale), Image.LANCZOS).convert('RGB').save(
            dest, quality=82, method=6)
        print(f'wrote             {dest.relative_to(ROOT)} ({dest.stat().st_size // 1024} KB)')


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
