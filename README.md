# eclipse.aravpanwar.com

Solar eclipse local circumstances computed from Besselian elements, then
intersected with populated places, so you can see what a location actually
costs you in seconds of totality.

Eclipse is a data row, not a constant: one record per event under
`data/elements/`, same computation for any of them.

Code is AGPL 3.0, data is ODbL 1.0. See `LICENSE` and `LICENSE-DATA.md`.

## The finding, for the 2 August 2027 eclipse

Luxor is the destination everyone names. It ranks **18th of 60 Egyptian places**
by seconds of totality sacrificed.

| Place | Totality | Sacrificed | From centerline | Population |
|---|---|---|---|---|
| Girga | 6m23s | 0.1 s | 1.0 km | 151,256 |
| Al Balyana | 6m22s | 0.2 s | 3.7 km | 68,413 |
| Nag Hammadi | 6m22s | 0.6 s | 6.9 km | 59,601 |
| Sohag | 6m22s | 0.9 s | 7.7 km | 266,944 |
| **Luxor** | **6m20s** | **2.7 s** | **15.1 km** | 422,407 |

Fourteen towns sit within 1.7 s of the theoretical maximum. Sohag has 267,000
people and beats Luxor by 1.8 s.

All 18 places within 3 s of the maximum are in Egypt. The best Spanish location
sacrifices 94.5 s.

### Supply does not follow the path

The obvious hypothesis, that lodging thins toward the centreline and that is
where the markup comes from, is not supported. Binned by distance from the
centreline, the median count of lodging within 25 km of an Egyptian place runs
12, 21, 1, 13, 6, 0. There is no gradient. Supply tracks the tourism cluster,
not the geometry.

What the counts do show is sharper:

| | Totality | Sacrificed | Lodging within 25 km | Within 80 km |
|---|---|---|---|---|
| Girga | 6m23s | 0.1 s | 4 | 22 |
| Luxor | 6m20s | 2.7 s | 115 | 127 |

Luxor has 29 times the lodging within 25 km and gives up 2.6 more seconds.
Widen to 80 km and the two are comparable, because at that radius both reach
the same Nile-valley cluster. Girga and Luxor are 103 km apart.

That is the sleep-and-stand case in two rows: the rooms and the maximum are not
in the same place, and the gap between them is a drive, not a compromise.

### Cloud does not complicate the choice

Median cloud cover at the local eclipse hour, from ERA5 over 1985-2024:

| Country | Places | Median cloud | Range |
|---|---|---|---|
| Egypt | 60 | 1.8% | 0.1-14.1 |
| Tunisia | 136 | 4.2% | 1.8-6.7 |
| Libya | 18 | 4.7% | 0.1-8.5 |
| Algeria | 186 | 12.5% | 4.3-22.3 |
| Spain | 118 | 16.1% | 12.2-25.3 |
| Morocco | 89 | 22.9% | 12.7-30.8 |
| Somalia | 8 | 36.6% | 30.9-41.3 |
| Saudi Arabia | 43 | 54.6% | 15.0-73.8 |
| Yemen | 114 | 61.5% | 32.8-79.8 |

Spain gives 4m48s with roughly one August day in four cloudy. Egypt gives
6m23s at 1.8%. Duration and clear sky point the same way, so there is no
trade to agonise over.

Checked against Jay Anderson's satellite-derived figures at eclipsophile.com:
Tarifa computes at 23.8% against his 26%, from an independent method and
dataset. Luxor computes at 3.1% against his 0.7%, and Melilla at 25.3%
against his 39%. Those two read high for the same reason: at 0.25 degrees one
ERA5 cell blends the Nile valley with the desert beside it, and Melilla with
the sea and the Rif. Treat these numbers as regional. Anderson is the better
source for a specific site and is linked, not reproduced, because his tables
state no licence.

## Usage

```
python scripts/extract_lodging.py   # once per OSM refresh, needs the extracts
python scripts/fetch_cloud.py       # once per event, needs ~/.cdsapirc
python scripts/build.py             # writes data/out/<event>-places.{csv,json}
python scripts/build_site_data.py   # writes docs/data/<event>-places.json, needs tzdata 2026.3+
python scripts/build_geojson.py     # writes docs/data/<event>-path.geojson
python scripts/build_countries.py   # writes docs/data/<event>-countries.geojson
python scripts/build_coverage.py    # writes docs/data/<event>-coverage.json from data/hotel_registers.json
python scripts/build_images.py      # writes docs/og.png and the site icons, needs Pillow
python -m pytest tests/ -q          # validation gate
```

`build.py` runs without the lodging or cloud caches and says which columns are
missing, so the core dataset is reproducible without a CDS account.

The full build takes about 7 minutes, dominated by the exact centerline solve.

## Validation

`python -m pytest tests/ -q`

The computation is checked against independently published values before any
downstream work is trusted:

| Check | Expected | Computed |
|---|---|---|
| Greatest eclipse on shadow axis | ~0 | 1.0e-5 Earth radii |
| Sun altitude at greatest eclipse | 81.7 deg | 81.69 deg |
| Duration at greatest eclipse | 06m23s | 382.5 s |
| Luxor duration | 6m19-6m23s | 380.0 s |
| Seconds Luxor sacrifices | a few | 3.1 s |
| Countries crossed | 9, not incl. Sudan | confirmed |
| Aden / Berbera | partial only | confirmed |
| Girga cloud, Aug | very low | 1.8% |
| Sanaa cloud, Aug | monsoon | 79.8% |

## Notes on correctness

**Delta T is load-bearing.** `mu` is tabulated against TDT but expresses a
Greenwich hour angle, a UT quantity. The frames differ by delta T, so it must
be subtracted in the hour angle. Omitting it leaves latitude correct and shifts
longitude by delta_T * 15 / 3600 degrees, about 32 km for this eclipse. This
eclipse assumes delta T = 76.0 s; NASA's older 2027 map used 71.7 s.

**Greatest eclipse is not greatest duration.** For total eclipses these are
different points, differing by 1-2 seconds and 100+ km. Greatest eclipse is
where the shadow axis passes closest to Earth's centre; greatest duration is
where totality lasts longest. Here they are 0.6 s and ~215 km apart. See
[Espenak on the distinction](https://eclipsewise.com/solar/SEhelp/SEgreatest.html).

**Two lunar radius constants.** k1 = 0.272488 for penumbral contacts,
k2 = 0.272281 for umbral. Duration and path limits use the umbral value.

**Lunar limb profile** shifts path limits by 1-2 km and duration by 1-3 s.
Limb-corrected predictions only appear 12-18 months before an event.

## Coverage

772 of 9,191 places in the nine path countries are inside totality.

| Country | Places | Best |
|---|---|---|
| Algeria | 186 | Arris, 5m30s |
| Tunisia | 136 | Mahires, 5m42s |
| Spain | 118 | Principe, 4m48s |
| Yemen | 114 | Baqim as Suq, 6m00s |
| Morocco | 89 | Mdiq, 4m52s |
| Egypt | 60 | Girga, 6m23s |
| Saudi Arabia | 43 | Al Lith, 6m10s |
| Libya | 18 | Benghazi, 6m09s |
| Somalia | 8 | Qandala, 5m27s |

Those counts are GeoNames density, not reality. Spain having 118 entries and
Somalia 8 says more about who edits the gazetteer than about where towns are.
A place missing here is missing from GeoNames.

## Licence

Code: AGPL 3.0 (`LICENSE`). Run a modified version as a network service and you
have to publish your changes.

Data under `data/out/` and `docs/data/`: ODbL 1.0 (`LICENSE-DATA.md`). The
lodging columns come from OpenStreetMap, which is share-alike, so the dataset
cannot be more permissive than that. Attributions you have to carry are listed
in `LICENSE-DATA.md`.

## Data sources

- Besselian elements: NASA GSFC. *Eclipse Predictions by Fred Espenak, NASA's GSFC.*
- Cloud: ERA5 hourly data on single levels, Copernicus Climate Change Service.
  Contains modified Copernicus Climate Change Service information.
- Lodging: OpenStreetMap contributors, ODbL 1.0, via Geofabrik extracts.
- Advisories: UK Foreign, Commonwealth & Development Office, Open Government
  Licence v3.0.
- Country outlines: Natural Earth 1:10m, UK point of view, v5.1.2, public
  domain.
- Hotel registers, for the stays coverage rating only: INE (Spain), HCP
  (Morocco), ONTT (Tunisia), GASTAT (Saudi Arabia), UN Tourism Statistics
  Database (Algeria, Egypt). Figures, periods and links in
  `data/hotel_registers.json`.
- Prior art worth using: [eclipsewhere.com](https://eclipsewhere.com) for
  curated cloud-first guidance, [Xavier Jubier's interactive map](http://xjubier.free.fr/en/site_pages/solar_eclipses/xSE_GoogleMap3.php?Ecl=+20270802)
  for point queries, [Eclipsophile](https://eclipsophile.com/tse2027/) for
  the authoritative cloud climatology.
