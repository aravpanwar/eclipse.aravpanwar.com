# eclipse.aravpanwar.com

Computes local circumstances of a solar eclipse from NASA's Besselian elements
for every populated place in GeoNames near the path, and publishes the results
as CSV, JSON and a static map site.

For each place inside the path the dataset gives the duration of totality, the
time of maximum eclipse, the Sun's altitude, the distance from the centre line,
historical cloud cover for the date and hour, and counts of lodging and camping
sites nearby. For each place within 100 km outside the path it gives the
fraction of the Sun covered at maximum and the distances to the path edge and
centre line.

Computed events: 2 August 2027 (total).

## Repository layout

| Path | Contents |
|---|---|
| `data/elements/` | Besselian elements, one JSON file per event |
| `data/events.json` | Choices made by hand for each event: map view, link card framing |
| `src/eclipse/` | Computation: local circumstances, path, places, cloud, lodging, advisories |
| `scripts/` | Build steps, listed below |
| `data/cache/` | Downloaded inputs and extracted caches |
| `data/out/` | Full build output (CSV and JSON) |
| `docs/` | The site, served by GitHub Pages; `docs/data/` holds the site's data files |
| `templates/` | The event page, filled in by `build_page.py` |
| `tests/` | Validation tests |

Each script takes the event as its one argument, the name of a file in
`data/elements/`.

## Requirements

Python 3.11. Packages: `osmium`, `xarray`, `netCDF4` or another xarray netCDF
engine, `cdsapi`, `Pillow`, `tzdata` 2026.3 or later, `pytest`. Pinned
versions are in `requirements.txt`:

```
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```

Download these separately:

- `data/cache/cities1000.zip` from GeoNames.
- Geofabrik country extracts in `data/cache/osm/`, for `extract_lodging.py`
  only.
- A Copernicus Climate Data Store account in `~/.cdsapirc`, for
  `fetch_cloud.py` only.

The scripts download Natural Earth outlines, NASA path tables and fonts
themselves.

## Build

```
python scripts/extract_lodging.py           # once per OSM refresh; writes data/cache/lodging/
python scripts/build_geojson.py <event>     # docs/data/<event>-path.geojson, <event>-centre-profile.json
python scripts/build.py <event>             # data/out/<event>-places.{csv,json}, <event>-outside.{csv,json}
python scripts/fetch_cloud.py <event>       # optional, then build.py again; writes data/cache/cloud/
python scripts/build_site_data.py <event>   # docs/data/<event>-places.json, <event>-outside.json
python scripts/build_countries.py <event>   # docs/data/<event>-countries.geojson
python scripts/build_coverage.py <event>    # docs/data/<event>-coverage.json
python scripts/build_images.py <event>      # docs/og.png, homepage thumbnails, site icons
python scripts/build_page.py <event>        # docs/solar-eclipse/<event>/index.html
python -m pytest tests/ -q
```

Then copy `data/out/<event>-places.csv` and `data/out/<event>-outside.csv`
into `docs/data/`.

`build.py` fetches UK travel advice at run time and takes about 8 minutes, most
of it the centre line solve. It runs without the lodging or cloud caches and
leaves those columns empty. Without cloud the event page says no cloud data
is available yet and leaves cloud out of the list.

## Adding an event

1. `python scripts/fetch_elements.py <yyyy-mm-dd>` writes
   `data/elements/<event>.json` from NASA's Besselian elements page, and keeps
   the page in `data/cache/nasa/`. It reads the static pages, not the search
   engine, which has been failing since late 2026 and left out `d3` when it
   worked. `tests/test_elements.py` then checks the file against NASA's
   greatest eclipse figures.
2. Add the event to `data/events.json` if it needs a hand-chosen setting. A
   path that crosses 180 degrees needs a `lon_window` that stops at 180.
   Without a `map` view the map frames the whole path; without `og` no link
   card is drawn.
3. Download Geofabrik extracts for the path countries and add any new country
   to `EXTRACTS` in `src/eclipse/lodging.py` and `COUNTRY_NAMES` in
   `src/eclipse/places.py`. `build.py` stops on a missing name and warns on a
   missing extract.
4. Add official hotel counts for the new countries to
   `data/hotel_registers.json`, or they are rated unknown.
5. Run the build above, then move the event's card on `docs/index.html` from
   the upcoming list.

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
| `lodging_within_25km`, `lodging_within_80km` | OSM `tourism=*` lodging features |
| `camping_within_25km`, `camping_within_80km` | OSM camp and caravan sites |

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
- Lodging: OpenStreetMap contributors, ODbL 1.0, via Geofabrik extracts.
- Travel advice: UK Foreign, Commonwealth & Development Office, Open Government
  Licence v3.0.
- Country outlines: Natural Earth 1:10m, UK point of view, v5.1.2, public
  domain.
- Hotel registers, used for the stays coverage rating: INE (Spain), HCP
  (Morocco), ONTT (Tunisia), GASTAT (Saudi Arabia), UN Tourism Statistics
  Database (Algeria, Egypt), Statistics Office (Gibraltar). Figures, periods
  and links are in `data/hotel_registers.json`.

## Licence

Code: AGPL 3.0 (`LICENSE`).

Fonts in `docs/fonts/`: Schibsted Grotesk and Source Serif 4, SIL Open Font
License 1.1.

Data in `data/out/` and `docs/data/`: ODbL 1.0 (`LICENSE-DATA.md`). The lodging
columns come from OpenStreetMap, which is share-alike. Required attributions
are listed in `LICENSE-DATA.md`.
