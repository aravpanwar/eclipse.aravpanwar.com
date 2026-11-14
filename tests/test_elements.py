"""Every elements file against NASA's own figures for greatest eclipse.

Runs for each file in data/elements/, so a new event is checked the moment
it is added. The event-specific checks for 2027 are in test_validation.py.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import eclipse.local_circumstances as L
from eclipse import event
from eclipse.path import axis_point, lon_window
from eclipse.places import haversine_km

FILES = sorted((ROOT / 'data' / 'elements').glob('*.json'))


def load(path):
    meta = json.loads(path.read_text(encoding='utf-8'))
    ge = meta['greatest_eclipse']
    return L.Elements.from_json(path), meta, ge, (ge['latitude_deg'], ge['longitude_deg'])


def seconds(text):
    """'06m23s' or '05m09.7s' as seconds."""
    m = re.fullmatch(r'(\d+)m(\d+(?:\.\d+)?)s', text)
    return int(m[1]) * 60 + float(m[2])


@pytest.mark.parametrize('path', FILES, ids=[p.stem for p in FILES])
def test_greatest_eclipse_is_on_the_axis(path):
    """NASA rounds its coordinates, to 0.1 degree on some pages, so within about 13 km."""
    E, _, _, point = load(path)
    c = L.compute(*point, 0.0, E)
    assert c.in_totality
    assert c.distance_from_axis_radii < 2e-3, c.distance_from_axis_radii


@pytest.mark.parametrize('path', FILES, ids=[p.stem for p in FILES])
def test_greatest_eclipse_sun_altitude(path):
    E, _, ge, point = load(path)
    c = L.compute(*point, 0.0, E)
    assert abs(c.sun_altitude_deg - ge['sun_altitude_deg']) <= 0.3, c.sun_altitude_deg


@pytest.mark.parametrize('path', FILES, ids=[p.stem for p in FILES])
def test_greatest_eclipse_duration(path):
    E, _, ge, point = load(path)
    c = L.compute(*point, 0.0, E)
    assert abs(c.duration_seconds - seconds(ge['central_duration'])) <= 2.0, c.duration_seconds


@pytest.mark.parametrize('path', FILES, ids=[p.stem for p in FILES])
def test_axis_at_greatest_eclipse_instant(path):
    """Stepping the axis in time lands on NASA's point at NASA's instant."""
    E, meta, ge, point = load(path)
    h, m, s = (float(v) for v in ge['instant_tdt'].split(':'))
    p = axis_point(E, h + m / 60 + s / 3600 - meta['t0_tdt_hours'])
    assert p is not None
    assert haversine_km(*p, *point) < 15.0, p


@pytest.mark.parametrize('path', FILES, ids=[p.stem for p in FILES])
def test_path_window_holds_greatest_eclipse(path):
    """A path that crosses 180 degrees needs its window set by hand."""
    E, _, _, (_, lon) = load(path)
    lo, hi = lon_window(E, event.settings(path.stem).get('lon_window'))
    assert lo < lon < hi
