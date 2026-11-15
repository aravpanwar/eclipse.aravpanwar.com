# eclipse.aravpanwar.com

Computes local circumstances of a solar eclipse from NASA's Besselian elements
for every populated place in GeoNames near the path, and publishes the results
as CSV, JSON and a static map site.

For each place inside the path the dataset gives the duration of totality, the
time of maximum eclipse, the Sun's altitude, the distance from the centre line,
and historical cloud cover for the date and hour. For each place within 100 km outside the path it gives the
fraction of the Sun covered at maximum and the distances to the path edge and
centre line.

Computed events, all total: 2 August 2027, 22 July 2028, 25 November 2030,
30 March 2033, 20 March 2034 and 2 September 2035, and five that have passed,
21 August 2017, 2 July 2019, 14 December 2020, 8 April 2024 and 12 August
2026. Cloud cover is computed for 2027 only so far; the other pages to come
say it is not available yet. Past eclipses carry no cloud and no travel
advice, and their pages say they have passed.

## Repository layout

| Path | Contents |
|---|---|
| `data/elements/` | Besselian elements, one JSON file per event |
| `data/events.json` | Choices made by hand for each event: map view, link card framing |
| `src/eclipse/` | Computation: local circumstances, path, places, cloud, advisories |
| `scripts/` | Build steps, listed below |
| `data/cache/` | Downloaded inputs and extracted caches |
| `data/out/` | Full build output (CSV and JSON) |
| `docs/` | The site, served by GitHub Pages; `docs/data/` holds the site's data files |
| `templates/` | The event page, filled in by `build_page.py` |
| `tests/` | Validation tests |

Each script takes the event as its one argument, the name of a file in
`data/elements/`.

## Requirements

Python 3.11. Packages: `xarray`, `netCDF4` or another xarray netCDF
engine, `cdsapi`, `Pillow`, `tzdata` 2026.3 or later, `pytest`. Pinned
versions are in `requirements.txt`:

```
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```

Download these separately:

- `data/cache/cities1000.zip` from GeoNames.
- A Copernicus Climate Data Store account in `~/.cdsapirc`, for
  `fetch_cloud.py` only.

The scripts download Natural Earth outlines, NASA path tables and fonts
themselves.

## Build

```
python scripts/build_geojson.py <event>     # docs/data/<event>-path.geojson, <event>-centre-profile.json
python scripts/build.py <event>             # data/out/<event>-places.{csv,json}, <event>-outside.{csv,json}
python scripts/fetch_cloud.py <event>       # optional, then build.py again; writes data/cache/cloud/
python scripts/build_site_data.py <event>   # docs/data/<event>-places.json, <event>-outside.json
python scripts/build_countries.py <event>   # docs/data/<event>-countries.geojson
python scripts/build_images.py <event>      # docs/og.png, homepage thumbnails, site icons
python scripts/build_page.py <event>        # docs/solar-eclipse/<event>/index.html
python scripts/build_home.py                # the homepage: next eclipse, later ones, past ones
python -m pytest tests/ -q
```

Then copy `data/out/<event>-places.csv` and `data/out/<event>-outside.csv`
into `docs/data/`.

`build.py` fetches UK travel advice at run time, for eclipses still to come,
and takes about 8 minutes, most of it the centre line solve. It runs without the cloud cache and leaves those
columns empty. Without cloud the event page says no cloud data
is available yet and leaves cloud out of the list.

## Adding an event

1. `python scripts/fetch_elements.py <yyyy-mm-dd>` writes
   `data/elements/<event>.json` from NASA's Besselian elements page, and keeps
   the page in `data/cache/nasa/`. It reads the static pages, not the search
   engine, which has been failing since late 2026 and left out `d3` when it
   worked. `tests/test_elements.py` then checks the file against NASA's
   greatest eclipse figures.
2. Add the event to `data/events.json` if it needs a hand-chosen setting. A
   path that crosses 180 degrees needs a `lon_window` that either stops at
   180 (2028, 2035) or runs on past it (2033: 179 to 205), in which case
   towns west of Greenwich are carried past 180 while computing and written
   back to -180..180 in the output. A path that doubles back needs a
   `lat_window` to say which pass to draw (2033 turns back in the Arctic;
   2026 runs south past Iceland, so it is drawn from Iceland to Spain).
   Without a `map` view the map frames the whole path; without `og` no link
   card is drawn.
3. Add any new country to `COUNTRY_NAMES` in `src/eclipse/places.py` and
   `SLUGS` in `src/eclipse/advisories.py`. `build.py` stops on a missing one.
   A past eclipse needs no slug, since it fetches no advice.
4. Run the build above, ending with `build_home.py`, which puts the event on
   the homepage. The soonest eclipse still to come gets the large block at
   the top, the others still to come get cards, and past ones go in a
   section at the bottom. `.github/workflows/home.yml` runs `build_home.py`
   every day and pushes when the page changes, so the day after an eclipse
   the homepage moves on to the next one by itself.

## Output

`<event>-places.csv`, one row per place inside the path:

| Column | Meaning |
|---|---|
| `geonameid` | GeoNames ID |
| `name`, `country_code`, `country` | From GeoNames |
| `latitude`, `longitude`, `elevation_m`, `population`, `timezone` | From GeoNames |
| `duration_seconds` | Duration of totality |
| `seconds_sacrificed` | Greatest duration on the path minus this place's duration |
| `sun_altitude_deg` | Sun altitude at maximum eclipse |
| `max_eclipse_ut_hours` | Time of maximum eclipse, decimal hours UT |
| `distance_from_centerline_km` | Straight-line distance to the centre line |
| `mean_cloud_percent` | Mean total cloud cover, ERA5, 1985 to 2024, eclipse date and a day either side, nearest hour |
| `clear_sky_probability` | Share of those hours under 20% cloud cover |
| `cloud_observations` | Number of hours sampled |

`<event>-outside.csv`, one row per place within 100 km outside the path:
GeoNames columns as above, then `obscuration_percent`, `magnitude`,
`max_eclipse_ut_hours`, `sun_altitude_deg`, `km_to_edge_of_totality` and
`km_to_centre_line`.

Place counts follow GeoNames coverage, which varies by country. A place missing
from GeoNames is missing here.

## Validation

`tests/test_validation.py` checks the 2027 computation against published
values:

| Check | Reference | Computed |
|---|---|---|
| Distance of NASA's greatest eclipse point from the shadow axis | 0 | 1.0e-5 Earth radii |
| Sun altitude at greatest eclipse | 81.7 deg (NASA) | 81.69 deg |
| Duration at greatest eclipse | 6m23s (NASA) | 382.5 s |
| Duration at Luxor | 6m19s to 6m23s | 380.0 s |
| Greatest duration minus duration at greatest eclipse | 0 to 3 s | passes |
| Countries crossed | 9 plus Gibraltar, not Sudan | passes |
| Cairo, Aden, Berbera | outside totality | passes |
| ERA5 August cloud, Girga and Sanaa | under 10%, over 40% | 1.8%, 79.8% |

ERA5 cells are 0.25 degrees, so cloud figures are regional. Against Jay
Anderson's satellite figures (eclipsophile.com): Tarifa 23.8% against 26%,
Luxor 3.1% against 0.7%, Melilla 25.3% against 39%. The last two differ
because one cell mixes the Nile valley with desert, and Melilla with sea and
mountains.

## Method notes

`mu` is tabulated against TDT but is a Greenwich hour angle, which is a UT
quantity, so the code subtracts delta T from it. Leaving it out shifts
longitudes by delta T x 15 / 3600 degrees. The 2027 build uses delta T =
76.0 s.

Greatest eclipse and greatest duration are different points. For 2027 they are
about 215 km and 0.6 s apart. `seconds_sacrificed` is measured from greatest
duration.

The lunar radius is k1 = 0.272488 for penumbral contacts and k2 = 0.272281 for
umbral contacts. Durations and path limits use k2.

The lunar limb profile is not modelled. It moves path limits by 1 to 2 km and
durations by 1 to 3 s.

## Data sources

- Besselian elements: NASA GSFC, *Eclipse Predictions by Fred Espenak, NASA's
  GSFC*.
- Places: GeoNames, CC BY 4.0.
- Cloud: ERA5 hourly data on single levels, Copernicus Climate Change Service.
  Contains modified Copernicus Climate Change Service information.
- Travel advice: UK Foreign, Commonwealth & Development Office, Open Government
  Licence v3.0.
- Country outlines: Natural Earth 1:10m, UK point of view, v5.1.2, public
  domain.

## Licence

Code: AGPL 3.0 (`LICENSE`).

Fonts in `docs/fonts/`: Schibsted Grotesk and Source Serif 4, SIL Open Font
License 1.1.

Data in `data/out/` and `docs/data/`: CC BY 4.0 (`LICENSE-DATA.md`). Required
attributions are listed in `LICENSE-DATA.md`. Versions before November 2026
were ODbL 1.0, and copies of those stay ODbL.

There are no places to stay in the dataset. Versions before November 2026 had
counts of OpenStreetMap lodging and camping features (`lodging_within_*`,
`camping_within_*`); they were dropped because a count of what is mapped says
little about what can be booked. The site links each town to a map search
instead.
