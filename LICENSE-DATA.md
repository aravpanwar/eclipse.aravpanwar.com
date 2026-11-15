# Licence: data

Everything under `data/out/` and `docs/data/` is licensed under the
**Creative Commons Attribution 4.0 International (CC BY 4.0)**.

https://creativecommons.org/licenses/by/4.0/

The code is licensed separately, under AGPL 3.0. See `LICENSE`.

## Why CC BY

Every source that goes into the dataset asks for attribution at most, so the
dataset asks for nothing more. GeoNames is itself CC BY 4.0.

In short: use it, change it, build on it, including commercially, under any
licence you like. Keep the attributions below.

## Earlier versions

Versions before November 2026 carried lodging counts derived from
OpenStreetMap, which is ODbL and share-alike, so they were released under the
Open Database License (ODbL) v1.0. Copies taken from those versions stay under
ODbL. Those columns have since been dropped, and everything published from
November 2026 on is CC BY 4.0.

## What you must carry

Attribution for every source that went into the dataset:

- **Eclipse geometry.** Eclipse Predictions by Fred Espenak, NASA's GSFC.
  Based on the Five Millennium Canon of Solar Eclipses: -1999 to +3000.
- **Populated places.** GeoNames, CC BY 4.0.
  https://www.geonames.org/
- **Cloud.** Contains modified Copernicus Climate Change Service information
  (ERA5 hourly data on single levels). Neither the European Commission nor
  ECMWF is responsible for any use of this information.
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
published NASA values, and the checks are in `tests/`. The cloud and
advisory columns each carry limitations that are documented in the `caveats`
block of the JSON output and on the site's method page. Read those before
relying on any of it for a decision that costs money.
