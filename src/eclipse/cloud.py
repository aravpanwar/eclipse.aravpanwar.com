# Totality Path & Nearby Locations
# Copyright (C) 2026 Arav Panwar
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. See <https://www.gnu.org/licenses/>.

"""Cloud cover climatology from ERA5 reanalysis.

What this answers: on the calendar date of the eclipse, at the hour the eclipse
happens there, how often has this place historically been cloudy?

Method: ERA5 total cloud cover, hourly, sampled for a window of years on the
eclipse date and the surrounding days, at the UT hour of local maximum eclipse.
The mean over years is the climatological probability; nothing here is a
forecast, and it cannot be. A forecast for 2 August 2027 will exist about a
week before the event and will be far more useful than any of this.

Why ERA5 rather than the satellite record: Jay Anderson's eclipsophile.com is
the domain standard and states no licence, so its tables cannot be
redistributed under an open licence. ERA5 is free, documented and citable.
Link to Anderson, never copy him.

Known limitations, all of which belong on the page next to the number:

- 0.25 degree grid, about 28 km. That is coarser than the terrain in much of
  this path. One ERA5 cell can span the Nile valley and the desert plateau
  beside it, which have genuinely different cloud behaviour. Treat the number
  as regional, not local.
- Reanalysis is a model constrained by observations, not an observation. Its
  cloud fields are among its weaker variables.
- A climatological mean over a window of years hides the spread. Two places at
  20% can differ in whether that is one year in five totally overcast or five
  years all hazy.
- Averaging days around the date trades date-specificity for sample size. That
  is the right trade for a 40-year window, but it is a trade.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

DATASET = 'reanalysis-era5-single-levels'
VARIABLE = 'total_cloud_cover'

# ERA5 native grid. Stated so the caveat on the page can cite it.
GRID_DEGREES = 0.25
GRID_KM_APPROX = 28


@dataclass
class CloudClimatology:
    """Historical cloudiness for one place at its eclipse hour.

    Samples are place-days, not years: sampling three days across forty years
    gives 120 observations, and the field names say so. Calling them years
    would overstate the evidence, because 1 and 2 August of the same year are
    correlated in a way two different years are not.
    """

    mean_cloud_fraction: float      # 0..1, mean over sampled observations
    observations: int               # years x days actually sampled
    hour_ut: int
    clear_observations: int         # observations under 20% cloud
    overcast_observations: int      # observations over 80% cloud
    grid_lat: float                 # the ERA5 cell actually used
    grid_lon: float

    @property
    def clear_sky_probability(self) -> float:
        """Fraction of sampled observations that were substantially clear."""
        return (self.clear_observations / self.observations
                if self.observations else 0.0)

    def as_dict(self) -> dict:
        d = asdict(self)
        d['mean_cloud_percent'] = round(self.mean_cloud_fraction * 100, 1)
        d['clear_sky_probability'] = round(self.clear_sky_probability, 3)
        return d


def build_request(year_from: int, year_to: int, month: int, days: list[int],
                  hours_ut: list[int], area: tuple[float, float, float, float]):
    """A single CDS request covering the whole path and the whole year window.

    One request rather than one per place: the API is a queue, and hundreds of
    requests would be both slow and inconsiderate. Area is (north, west, south, east) in
    degrees, which is the order the API expects and an easy one to get wrong.
    """
    north, west, south, east = area
    return {
        'product_type': ['reanalysis'],
        'variable': [VARIABLE],
        'year': [str(y) for y in range(year_from, year_to + 1)],
        'month': [f'{month:02d}'],
        'day': [f'{d:02d}' for d in days],
        'time': [f'{h:02d}:00' for h in hours_ut],
        'area': [north, west, south, east],
        'data_format': 'netcdf',
        'download_format': 'unarchived',
    }


def path_area(places, pad_degrees: float = 1.0):
    """Bounding box around every place, padded, as (north, west, south, east)."""
    lats = [p['latitude'] if isinstance(p, dict) else p.latitude for p in places]
    lons = [p['longitude'] if isinstance(p, dict) else p.longitude for p in places]
    return (
        min(90.0, max(lats) + pad_degrees),
        max(-180.0, min(lons) - pad_degrees),
        max(-90.0, min(lats) - pad_degrees),
        min(180.0, max(lons) + pad_degrees),
    )


def nearest_grid_index(value: float, axis) -> int:
    """Index of the closest coordinate on an ERA5 axis.

    Nearest neighbour, deliberately, rather than interpolating between cells.
    Interpolation would invent a smoothness the 0.25 degree field does not have
    and would blur the one distinction that matters here, valley against
    plateau, into an average of both.
    """
    best_i, best_d = 0, float('inf')
    for i, a in enumerate(axis):
        d = abs(float(a) - value)
        if d < best_d:
            best_d, best_i = d, i
    return best_i


def sample(dataset, lat: float, lon: float, hour_ut: int,
           lat_name: str, lon_name: str, time_name: str,
           var_name: str) -> CloudClimatology | None:
    """Extract one place's climatology from an opened netCDF dataset.

    `dataset` is anything with numpy-like indexing on the cloud variable and
    coordinate arrays, so xarray or netCDF4 both work; the caller opens it.
    """
    import numpy as np

    lats = np.asarray(dataset[lat_name][:])
    lons = np.asarray(dataset[lon_name][:])
    iy = nearest_grid_index(lat, lats)
    ix = nearest_grid_index(lon, lons)

    times = np.asarray(dataset[time_name][:])
    values = dataset[var_name]

    # Select the timesteps whose UT hour matches this place's eclipse hour.
    hours = _hours_of(dataset, time_name, times)
    picked = [i for i, h in enumerate(hours) if h == hour_ut]
    if not picked:
        return None

    series = []
    for i in picked:
        v = float(np.asarray(values[i, iy, ix]))
        if v != v:            # NaN
            continue
        # ERA5 total cloud cover is a 0..1 fraction.
        series.append(max(0.0, min(1.0, v)))
    if not series:
        return None

    return CloudClimatology(
        mean_cloud_fraction=sum(series) / len(series),
        observations=len(series),
        hour_ut=hour_ut,
        clear_observations=sum(1 for v in series if v < 0.20),
        overcast_observations=sum(1 for v in series if v > 0.80),
        grid_lat=round(float(lats[iy]), 4),
        grid_lon=round(float(lons[ix]), 4),
    )


def _hours_of(dataset, time_name, times):
    """UT hour for each timestep, tolerating the several shapes ERA5 uses."""
    import numpy as np

    # xarray hands back datetime64; netCDF4 hands back numbers plus a units
    # attribute. Both appear depending on how the file was opened.
    if np.issubdtype(np.asarray(times).dtype, np.datetime64):
        return [int(np.datetime64(t, 'h').astype(int) % 24) for t in times]

    units = ''
    try:
        units = getattr(dataset[time_name], 'units', '') or ''
    except Exception:
        pass
    try:
        import cftime
        parsed = cftime.num2date(times, units)
        return [int(p.hour) for p in parsed]
    except Exception:
        # Last resort: assume hours since an epoch on the hour.
        return [int(float(t)) % 24 for t in times]
