"""Validation gate. If these fail, nothing downstream matters.

Targets come from the project brief plus independently published values.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import eclipse.local_circumstances as L

E = L.Elements.from_json(
    Path(__file__).resolve().parents[1] / 'data' / 'elements' / '2027-08-02.json')

LUXOR = (25.6872, 32.6396, 76.0)
NASA_GREATEST_ECLIPSE = (25.5, 33.2)


def approx(a, b, tol):
    return abs(a - b) <= tol


def test_greatest_eclipse_point_is_on_the_axis():
    """NASA's greatest-eclipse coordinates must sit on the shadow axis."""
    c = L.compute(*NASA_GREATEST_ECLIPSE, 0.0, E)
    assert c.in_totality
    assert c.distance_from_axis_radii < 1e-4, c.distance_from_axis_radii


def test_greatest_eclipse_sun_altitude():
    """NASA publishes 81.7 degrees."""
    c = L.compute(*NASA_GREATEST_ECLIPSE, 0.0, E)
    assert approx(c.sun_altitude_deg, 81.7, 0.1), c.sun_altitude_deg


def test_greatest_eclipse_duration():
    """NASA publishes central duration 06m23s at greatest eclipse."""
    c = L.compute(*NASA_GREATEST_ECLIPSE, 0.0, E)
    assert approx(c.duration_seconds, 383.0, 1.0), c.duration_seconds


def test_luxor_duration():
    """Brief says ~6m23s; eclipsewhere publishes 6m20s. Accept the 6m19-6m23 band."""
    c = L.compute(*LUXOR, E)
    assert c.in_totality
    assert 379.0 <= c.duration_seconds <= 384.0, c.duration_seconds


def test_luxor_sacrifices_only_a_few_seconds():
    """The core thesis: Luxor gives up almost nothing versus the path maximum."""
    lux = L.compute(*LUXOR, E)
    peak = _greatest_duration()
    sacrificed = peak - lux.duration_seconds
    assert 0.0 <= sacrificed <= 6.0, sacrificed


def test_greatest_duration_exceeds_greatest_eclipse_slightly():
    """Espenak: for total eclipses these differ by 1-2 s and 100+ km.

    See eclipsewise.com/solar/SEhelp/SEgreatest.html. This is a real property of
    total eclipses, not an error: greatest eclipse is where the shadow axis
    passes closest to Earth's centre, greatest duration is where totality lasts
    longest, and they are different points.
    """
    ge = L.compute(*NASA_GREATEST_ECLIPSE, 0.0, E).duration_seconds
    gd = _greatest_duration()
    assert gd >= ge
    assert gd - ge < 3.0, (gd, ge)


def test_path_crosses_expected_countries():
    """Sampled points that must be inside the path, one per brief country."""
    inside = {
        'Spain (Cadiz)':        (36.53, -6.29),
        'Morocco (Tangier)':    (35.78, -5.81),
        'Algeria (centerline)': (35.55,  2.00),
        'Tunisia (Tozeur)':     (33.92,  8.13),
        'Libya (Benghazi)':     (32.12, 20.07),
        'Egypt (Luxor)':        (25.69, 32.64),
        'Saudi Arabia (Jeddah)':(21.49, 39.19),
    }
    failures = []
    for name, (lat, lon) in inside.items():
        c = L.compute(lat, lon, 0.0, E)
        if not c.in_totality:
            failures.append((name, c.magnitude))
    assert not failures, failures


def test_outside_path_is_not_total():
    """Cairo and Aden are NOT in the path.

    Aden and Berbera circulate widely as 2027 "totality destinations" and are
    partial-only. Credit to eclipsewhere.com for documenting this first.
    """
    for name, (lat, lon) in {'Cairo': (30.04, 31.24),
                             'Aden': (12.79, 45.02),
                             'Berbera': (10.44, 45.01)}.items():
        c = L.compute(lat, lon, 0.0, E)
        assert not c.in_totality, (name, c.magnitude)


def test_path_does_not_cross_sudan():
    """Some sources list Sudan as a tenth country. The centerline runs well
    north of it: at longitude 31-34 E the centre is near 25-27 N, and Sudan's
    northern border is at 22 N. Kept as a regression test because the brief's
    nine-country list depends on it.
    """
    for lat, lon in ((21.0, 31.5), (20.0, 33.0), (19.5, 34.0)):
        c = L.compute(lat, lon, 0.0, E)
        assert not c.in_totality, (lat, lon, c.magnitude)


def test_delta_t_is_recorded():
    """The brief requires the assumed delta T to be stored and displayable."""
    assert E.delta_t_seconds == 76.0


def _greatest_duration():
    """Hill-climb from the greatest-eclipse point to the duration maximum."""
    lat, lon = NASA_GREATEST_ECLIPSE
    step = 0.5
    best = L.compute(lat, lon, 0.0, E).duration_seconds
    for _ in range(400):
        moved = False
        for dla, dlo in ((step, 0), (-step, 0), (0, step), (0, -step),
                         (step, step), (step, -step), (-step, step), (-step, -step)):
            c = L.compute(lat + dla, lon + dlo, 0.0, E)
            if c.duration_seconds and c.duration_seconds > best + 1e-9:
                best, lat, lon, moved = c.duration_seconds, lat + dla, lon + dlo, True
                break
        if not moved:
            step /= 2.0
            if step < 1e-6:
                break
    return best


def test_cloud_cache_is_physically_plausible():
    """ERA5 cloud should reproduce the known August climate of the path.

    Not a test of the eclipse maths, a test that the right variable was read
    from the right grid cells: the Western Desert is famously cloudless in
    August and the Yemeni highlands are in monsoon. If these invert, the
    latitude axis is flipped or the variable is wrong.
    """
    import json
    cache = (Path(__file__).resolve().parents[1] / 'data' / 'cache' / 'cloud'
             / '2027-08-02-cloud.json')
    if not cache.exists():
        return                      # cloud is optional; the build works without it

    blob = json.loads(cache.read_text(encoding='utf-8'))
    by_id = blob['by_geonameid']
    assert by_id, 'expected a non-empty cloud cache'

    for rec in by_id.values():
        assert 0.0 <= rec['mean_cloud_fraction'] <= 1.0
        assert rec['observations'] > 0
        assert rec['clear_observations'] <= rec['observations']
        assert rec['overcast_observations'] <= rec['observations']

    import csv
    places = list(csv.DictReader(
        (Path(__file__).resolve().parents[1] / 'data' / 'out'
         / '2027-08-02-places.csv').open(encoding='utf-8')))
    cloud_by_name = {
        p['name']: by_id[p['geonameid']]['mean_cloud_percent']
        for p in places if p['geonameid'] in by_id
    }

    # Upper Egypt in August is among the driest places on Earth.
    assert cloud_by_name.get('Girga', 100) < 10.0, cloud_by_name.get('Girga')
    # Sanaa sits in the Yemeni highlands during the summer monsoon.
    assert cloud_by_name.get('Sanaa', 0) > 40.0, cloud_by_name.get('Sanaa')
    # And the ordering must hold.
    assert cloud_by_name.get('Girga', 100) < cloud_by_name.get('Sanaa', 0)
