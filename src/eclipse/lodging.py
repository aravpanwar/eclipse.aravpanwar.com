# Totality Path & Nearby Locations
# Copyright (C) 2026 Arav Panwar
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. See <https://www.gnu.org/licenses/>.

"""Lodging supply from OpenStreetMap extracts.

Supply, never price. Counting rooms is not the same as knowing what they cost,
and this project does not publish prices: a count of beds within reach of a
place is sourceable from open data and stays true indefinitely, whereas a price
is a scrape with a shelf life.

The argument the counts support: supply thins toward the centreline. Scarcity is
what produces a markup, so a town with six guest houses and a town with six
hundred hotel rooms are different propositions at the same duration, and that
difference is visible without quoting a single rate.

Read from Geofabrik country extracts at build time. Overpass is deliberately not
used: the brief forbids depending on volunteer-run infrastructure, and a
corridor-sized Overpass query returned 504 in testing.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import osmium

# tourism=* values that mean "somewhere to sleep".
LODGING_VALUES = {
    'hotel', 'guest_house', 'hostel', 'motel', 'apartment',
    'chalet', 'resort', 'alpine_hut', 'wilderness_hut',
}

# Campsites and caravan sites are counted separately: for an eclipse they are
# genuinely useful (you can pitch a tent in a desert) but they are not
# equivalent to a room, and lumping them in would overstate supply.
CAMPING_VALUES = {'camp_site', 'caravan_site', 'camp_pitch'}


@dataclass
class Lodging:
    """One place to sleep, reduced to what we need."""

    latitude: float
    longitude: float
    kind: str
    name: str = ''
    rooms: int | None = None
    beds: int | None = None
    stars: str = ''

    @property
    def is_camping(self) -> bool:
        return self.kind in CAMPING_VALUES


def _int_or_none(value: str | None) -> int | None:
    """OSM tag values are free text. Accept a plain integer, reject the rest."""
    if not value:
        return None
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return n if 0 < n < 100000 else None


def extract(pbf_path: str | Path) -> list[Lodging]:
    """Pull every lodging feature out of one country extract.

    Counts nodes and closed ways. A hotel mapped as a building polygon is one
    hotel, the same as a hotel mapped as a point, so both are kept and the
    polygon is reduced to the mean of its node positions. We only need to know
    which town a hotel is near, not its footprint.

    Filtering is done on the 'tourism' key and the value is checked here rather
    than in a TagFilter: a TagFilter holding several (key, value) pairs did not
    behave as key-value matching, letting non-lodging tourism features through
    while under-counting hotels. Counting nodes alone, which is what a naive
    geometry try/except degrades to, lost about 15% of Libyan lodging.
    """
    out: list[Lodging] = []
    wanted = LODGING_VALUES | CAMPING_VALUES

    # with_locations() is required, not optional: without it a way's node
    # coordinates are all invalid and every polygon-mapped hotel is silently
    # dropped. That cost about 15% of Libyan lodging, and 74 of 319 hotels.
    for obj in osmium.FileProcessor(str(pbf_path))            .with_locations()            .with_filter(osmium.filter.KeyFilter('tourism')):
        tags = dict(obj.tags)
        kind = tags.get('tourism', '')
        if kind not in wanted:
            continue

        if obj.is_node():
            loc = obj.location
            if not loc.valid():
                continue
            lat, lon = loc.lat, loc.lon
        elif obj.is_way():
            pts = [n.location for n in obj.nodes if n.location.valid()]
            if not pts:
                continue
            lat = sum(pt.lat for pt in pts) / len(pts)
            lon = sum(pt.lon for pt in pts) / len(pts)
        else:
            # Relations: rare for lodging, and their member ways are already
            # counted. Skipping them avoids double counting.
            continue

        out.append(Lodging(
            latitude=lat,
            longitude=lon,
            kind=kind,
            name=tags.get('name', ''),
            rooms=_int_or_none(tags.get('rooms')),
            beds=_int_or_none(tags.get('beds')),
            stars=tags.get('stars', ''),
        ))
    return out


# GeoNames country code -> Geofabrik extract basename. Saudi Arabia has no
# standalone extract; it is inside the GCC states region. Gibraltar is inside
# the Spain extract.
EXTRACTS = {
    'EG': 'egypt', 'LY': 'libya', 'TN': 'tunisia', 'DZ': 'algeria',
    'MA': 'morocco', 'SO': 'somalia', 'YE': 'yemen', 'ES': 'spain',
    'SA': 'gcc-states', 'GI': 'spain',
}


@dataclass
class Supply:
    """Lodging within reach of one place."""

    radius_km: float
    rooms_listed: int = 0        # sum of rooms=* where tagged
    lodging_count: int = 0       # anything you can book a room in
    camping_count: int = 0       # tent and caravan sites, counted apart
    by_kind: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            'radius_km': self.radius_km,
            'lodging_count': self.lodging_count,
            'camping_count': self.camping_count,
            'rooms_listed': self.rooms_listed or None,
            'by_kind': self.by_kind or None,
        }


def _grid_key(lat: float, lon: float, cell: float = 0.5) -> tuple[int, int]:
    return (int(lat // cell), int(lon // cell))


def index_by_cell(items: list[Lodging], cell: float = 0.5):
    """Bucket lodging into a coarse lat/lon grid.

    Turns the supply query from a scan of every hotel per place into a look at
    a handful of neighbouring cells. Cells are degrees, so they are not equal
    area, but they only ever over-select candidates; the real filter is the
    great-circle distance test that follows.
    """
    idx: dict[tuple[int, int], list[Lodging]] = {}
    for it in items:
        idx.setdefault(_grid_key(it.latitude, it.longitude, cell), []).append(it)
    return idx


def supply_within(lat: float, lon: float, radius_km: float,
                  index: dict, cell: float = 0.5,
                  distance_fn=None) -> Supply:
    """Count lodging within radius_km of a point.

    Membership is by great-circle distance, never point-in-polygon against a
    drawn circle: a polygon approximation makes places on the edge flicker in
    and out depending on how finely the circle was tessellated.
    """
    if distance_fn is None:
        from .places import haversine_km as distance_fn

    # Degrees of latitude per km is ~1/111; longitude shrinks with cos(lat).
    import math
    span_lat = radius_km / 111.0
    coslat = max(0.01, math.cos(math.radians(lat)))
    span_lon = radius_km / (111.0 * coslat)

    lo_la, hi_la = lat - span_lat, lat + span_lat
    lo_lo, hi_lo = lon - span_lon, lon + span_lon

    out = Supply(radius_km=radius_km)
    seen_cells = set()
    la = lo_la
    while la <= hi_la + cell:
        lo = lo_lo
        while lo <= hi_lo + cell:
            key = _grid_key(la, lo, cell)
            if key not in seen_cells:
                seen_cells.add(key)
                for it in index.get(key, ()):
                    if distance_fn(lat, lon, it.latitude, it.longitude) <= radius_km:
                        if it.is_camping:
                            out.camping_count += 1
                        else:
                            out.lodging_count += 1
                            if it.rooms:
                                out.rooms_listed += it.rooms
                        out.by_kind[it.kind] = out.by_kind.get(it.kind, 0) + 1
            lo += cell
        la += cell
    return out


def load_cache(cache_dir: str | Path, country_codes: list[str]) -> dict:
    """Load the extracted lodging cache and index it per country.

    Saudi Arabia shares the GCC states extract with its neighbours, so several
    country codes can map to one file. The index is built per extract and the
    distance test does the rest; a hotel across a border is still a hotel you
    could sleep in, and the circle query is geographic rather than political.
    """
    cache_dir = Path(cache_dir)
    loaded: dict[str, list[Lodging]] = {}
    for cc in country_codes:
        basename = EXTRACTS.get(cc)
        if not basename or basename in loaded:
            continue
        path = cache_dir / f'{basename}.json'
        if not path.exists():
            continue
        raw = json.loads(path.read_text(encoding='utf-8'))
        loaded[basename] = [
            Lodging(latitude=r['lat'], longitude=r['lon'], kind=r['kind'],
                    rooms=r.get('rooms'))
            for r in raw
        ]
    return loaded


def combined_index(loaded: dict, cell: float = 0.5) -> dict:
    """One grid index across every extract, so border areas are not truncated."""
    everything: list[Lodging] = []
    for items in loaded.values():
        everything.extend(items)
    return index_by_cell(everything, cell)
