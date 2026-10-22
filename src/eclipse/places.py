# Totality Path & Nearby Locations
# Copyright (C) 2026 Arav Panwar
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. See <https://www.gnu.org/licenses/>.

"""Load GeoNames populated places and intersect them with an eclipse path.

GeoNames is CC-BY 4.0. Attribution is carried through to the output.

Coverage is uneven by country and this matters for how results are read: the
cities1000 extract holds thousands of records for Spain and low hundreds for
Libya and Somalia. Absence of a town from the output means absence from
GeoNames, not absence of a town.
"""

from __future__ import annotations

import csv
import io
import math
import zipfile
from dataclasses import dataclass
from pathlib import Path

GEONAMES_FIELDS = [
    'geonameid', 'name', 'asciiname', 'alternatenames', 'latitude', 'longitude',
    'feature_class', 'feature_code', 'country_code', 'cc2',
    'admin1', 'admin2', 'admin3', 'admin4',
    'population', 'elevation', 'dem', 'timezone', 'modified',
]

# Feature codes worth keeping: populated places and administrative seats.
# Excludes abandoned (PPLQ), destroyed (PPLW) and historical (PPLH) places,
# and sections of a town (PPLX), which list one town twice: Principe is a
# district of Ceuta, not a second town beside it.
KEEP_FEATURE_CODES = {
    'PPL', 'PPLA', 'PPLA2', 'PPLA3', 'PPLA4', 'PPLA5',
    'PPLC', 'PPLG', 'PPLS', 'PPLL', 'PPLF', 'PPLR',
}

# Every country with a town in or near a path needs a name here. The list of
# countries is not kept by hand: it comes from the towns the eclipse
# calculation finds, so a country is never missed (Gibraltar once was).
COUNTRY_NAMES = {
    'ES': 'Spain', 'MA': 'Morocco', 'DZ': 'Algeria', 'TN': 'Tunisia',
    'LY': 'Libya', 'EG': 'Egypt', 'SA': 'Saudi Arabia', 'YE': 'Yemen',
    'SO': 'Somalia', 'SD': 'Sudan', 'GI': 'Gibraltar', 'PT': 'Portugal',
    'MT': 'Malta', 'IT': 'Italy',
}


@dataclass
class Place:
    geonameid: int
    name: str
    country_code: str
    latitude: float
    longitude: float
    elevation_m: float
    population: int
    timezone: str
    feature_code: str

    @property
    def country(self) -> str:
        return COUNTRY_NAMES.get(self.country_code, self.country_code)


def load(zip_path: str | Path, countries: list[str] | None = None,
         min_population: int = 0,
         box: tuple[float, float, float, float] | None = None) -> list[Place]:
    """Read the GeoNames cities archive, filtered to countries or to a box.

    box is (west, south, east, north) in degrees.
    """
    wanted = set(countries) if countries else None
    out: list[Place] = []

    with zipfile.ZipFile(zip_path) as z:
        member = next(n for n in z.namelist() if n.endswith('.txt'))
        text = z.read(member).decode('utf-8')

    reader = csv.reader(io.StringIO(text), delimiter='\t', quoting=csv.QUOTE_NONE)
    for row in reader:
        if len(row) < len(GEONAMES_FIELDS):
            continue
        r = dict(zip(GEONAMES_FIELDS, row))
        if wanted and r['country_code'] not in wanted:
            continue
        if r['feature_code'] not in KEEP_FEATURE_CODES:
            continue
        try:
            pop = int(r['population'] or 0)
        except ValueError:
            pop = 0
        if pop < min_population:
            continue
        lat, lon = float(r['latitude']), float(r['longitude'])
        if box and not (box[0] <= lon <= box[2] and box[1] <= lat <= box[3]):
            continue

        # 'elevation' is usually blank; 'dem' is the SRTM/GTOPO30 fallback and
        # is populated far more often. Either is fine for eclipse work, where
        # a few tens of metres changes duration by milliseconds.
        elev = r['elevation'] or r['dem'] or '0'
        try:
            elev_m = float(elev)
        except ValueError:
            elev_m = 0.0
        if elev_m < -500:      # GeoNames uses -9999 for unknown
            elev_m = 0.0

        out.append(Place(
            geonameid=int(r['geonameid']),
            name=r['name'],
            country_code=r['country_code'],
            latitude=lat,
            longitude=lon,
            elevation_m=elev_m,
            population=pop,
            timezone=r['timezone'],
            feature_code=r['feature_code'],
        ))
    return out


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance. Geodesic only, never Web Mercator."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))
