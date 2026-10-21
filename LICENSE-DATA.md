# Licence: data

Everything under `data/out/` and `docs/data/` is licensed under the
**Open Database License (ODbL) v1.0**.

https://opendatacommons.org/licenses/odbl/1-0/

The code is licensed separately, under AGPL 3.0. See `LICENSE`.

## Why ODbL and not something more permissive

The lodging columns are derived from OpenStreetMap, which is ODbL. ODbL is
share-alike, so a dataset containing OSM-derived data cannot be released under
a permissive licence such as CC BY. Rather than split the dataset or drop the
columns, the whole thing is ODbL. GeoNames requires attribution only, which
ODbL satisfies.

In short: use it, change it, build on it, including commercially. If you
publish a database derived from it, publish that under ODbL too, and keep the
attributions below.

## What you must carry

Attribution for every source that went into the dataset:

- **Eclipse geometry.** Eclipse Predictions by Fred Espenak, NASA's GSFC.
  Based on the Five Millennium Canon of Solar Eclipses: -1999 to +3000.
- **Populated places.** GeoNames, CC BY 4.0.
  https://www.geonames.org/
- **Cloud.** Contains modified Copernicus Climate Change Service information
  (ERA5 hourly data on single levels). Neither the European Commission nor
  ECMWF is responsible for any use of this information.
- **Places to stay.** © OpenStreetMap contributors, ODbL 1.0.
  https://www.openstreetmap.org/copyright
- **Hotel registers**, used only for the stays coverage rating. INE (Spain),
  HCP (Morocco), ONTT (Tunisia), GASTAT (Saudi Arabia) and the UN Tourism
  Statistics Database (Algeria, Egypt). Sources in `data/hotel_registers.json`.
- **Country outlines.** Natural Earth, public domain. No attribution is
  required; it is listed for provenance. https://www.naturalearthdata.com/
- **Travel advisories.** Contains public sector information licensed under the
  Open Government Licence v3.0, from the UK Foreign, Commonwealth &
  Development Office.

## What is not covered

Cloud figures published by Jay Anderson at eclipsophile.com are not
reproduced anywhere in this dataset. That site states no licence, so it is
linked, never copied. Anderson uses the satellite record rather than
reanalysis and is the better source for a specific site. The ERA5 numbers here
were computed independently.

## Accuracy

The dataset is offered as-is. The eclipse geometry is validated against
published NASA values, and the checks are in `tests/`. The cloud, lodging and
advisory columns each carry limitations that are documented in the `caveats`
block of the JSON output and on the site's method page. Read those before
relying on any of it for a decision that costs money.
