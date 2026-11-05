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
| `src/eclipse/` | Computation: local circumstances, path, places, cloud, lodging, advisories |
| `scripts/` | Build steps, listed below |
| `data/cache/` | Downloaded inputs and extracted caches |
| `data/out/` | Full build output (CSV and JSON) |
| `docs/` | The site, served by GitHub Pages; `docs/data/` holds the site's data files |
| `tests/` | Validation tests |

Each script sets `EVENT = '2027-08-02'` at the top. To build another event,
change that value in each script and add the event's file to `data/elements/`.

## Requirements

Python 3.11. Packages: `osmium`, `xarray`, `netCDF4` or another xarray netCDF
engine, `cdsapi`, `Pillow`, `tzdata` 2026.3 or later, `pytest`.

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
python scripts/extract_lodging.py   # once per OSM refresh; writes data/cache/lodging/
python scripts/fetch_cloud.py       # once per event; writes data/cache/cloud/
python scripts/build_geojson.py     # docs/data/<event>-path.geojson, <event>-centre-profile.json
python scripts/build.py             # data/out/<event>-places.{csv,json}, <event>-outside.{csv,json}
python scripts/build_site_data.py   # docs/data/<event>-places.json, <event>-outside.json
python scripts/build_countries.py   # docs/data/<event>-countries.geojson
python scripts/build_coverage.py    # docs/data/<event>-coverage.json
python scripts/build_images.py      # docs/og.png, homepage thumbnails, site icons
python -m pytest tests/ -q
```

Then copy `data/out/<event>-places.csv` and `data/out/<event>-outside.csv`
into `docs/data/`.

`build.py` fetches UK travel advice at run time and takes about 8 minutes, most
of it the centre line solve. It runs without the lodging or cloud caches and
leaves those columns empty.

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

Data in `data/out/` and `docs/data/`: ODbL 1.0 (`LICENSE-DATA.md`). The lodging
columns come from OpenStreetMap, which is share-alike. Required attributions
are listed in `LICENSE-DATA.md`.
