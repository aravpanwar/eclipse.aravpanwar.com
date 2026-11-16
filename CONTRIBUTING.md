# Contributing

Corrections and suggestions are welcome, especially from people who know the
towns along a path.

## Start with an issue

Every change starts as an [issue](https://github.com/aravpanwar/eclipse.aravpanwar.com/issues), for example:

- a town shown in totality that isn't, or one left out that is
- a wrong time, duration or time zone for a town
- a wrong or missing country name or outline
- a problem with the map or the page
- an eclipse you'd like added

Say which eclipse and which town, and include a source where you can, such as
NASA's eclipse pages or a published local circumstances table. Most issues are
fixed directly, so you don't need to open a pull request.

Towns come from GeoNames, which lists places of 1,000 people or more. A town
that is missing from GeoNames is missing here too, and the fix belongs at
[geonames.org](https://www.geonames.org/), after which the next build picks it
up.

## Pull requests

If you'd like to make the change yourself, say so in the issue and wait for it
to be labelled `approved`. Then open a pull request that links the issue in its
description, for example `Closes #12`.

Pull requests that don't link an approved issue are closed automatically.

## Changing the code or data

Everything in `data/out/`, `docs/data/`, `docs/solar-eclipse/` and
`docs/thumbs/` is generated, so don't edit it by hand. Change the code in
`src/eclipse/` or `scripts/`, or the hand choices in `data/events.json`, then
rebuild the affected eclipses as described in the README.

Use plain hyphens, not en or em dashes.

Before opening a pull request, run:

```sh
python -m pytest tests/ -q
```

It must pass. Contributions to the data are released under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), and contributions
to the code under [AGPL 3.0](LICENSE).
