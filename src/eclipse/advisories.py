# Totality Path & Nearby Locations
# Copyright (C) 2026 Arav Panwar
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. See <https://www.gnu.org/licenses/>.

"""Travel advisories from the FCDO, fetched at build time.

Queried once per build and committed, never per visitor. The brief requires the
issuing body and the date checked to be shown, and both come straight from the
feed rather than being asserted by hand.

Handling is deliberately soft but unmissable: the advisory attaches to the
country group, never to individual rows, and nothing is hidden or reordered
because of it. A ranking that optimises for duration, clear sky and low crowds
will surface places under serious advisories at the top, because on those axes
they genuinely win. The map should not lie about what is in the path.
"""

from __future__ import annotations

import html
import json
import re
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

FCDO_API = 'https://www.gov.uk/api/content/foreign-travel-advice/{slug}'
FCDO_PAGE = 'https://www.gov.uk/foreign-travel-advice/{slug}'

ISSUER = 'UK Foreign, Commonwealth & Development Office'
ISSUER_SHORT = 'FCDO'

# GeoNames country code -> gov.uk slug.
SLUGS = {
    'ES': 'spain', 'MA': 'morocco', 'DZ': 'algeria', 'TN': 'tunisia',
    'LY': 'libya', 'EG': 'egypt', 'SA': 'saudi-arabia', 'YE': 'yemen',
    'SO': 'somalia', 'SD': 'sudan',
}

# The FCDO taxonomy, most severe first. Ordering is ours, for sorting badges;
# the strings are theirs. Enumerated by sampling the feed across countries
# rather than assumed, because the obvious guesses (a bare 'avoid_all_travel')
# do not appear: whole-country advisories carry an explicit
# '_to_whole_country' suffix, and getting that wrong sorts the most severe
# advisory in the path, Yemen's, as the least severe.
SEVERITY = [
    'avoid_all_travel_to_whole_country',
    'avoid_all_travel_to_parts',
    'avoid_all_but_essential_travel_to_whole_country',
    'avoid_all_but_essential_travel_to_parts',
]

LABELS = {
    'avoid_all_travel_to_whole_country':
        'Advises against all travel to the whole country',
    'avoid_all_travel_to_parts':
        'Advises against all travel to parts of the country',
    'avoid_all_but_essential_travel_to_whole_country':
        'Advises against all but essential travel to the whole country',
    'avoid_all_but_essential_travel_to_parts':
        'Advises against all but essential travel to parts of the country',
}


@dataclass
class Advisory:
    country_code: str
    country: str
    alert_status: list[str]
    labels: list[str]
    worst: str | None
    reviewed_at: str | None
    updated_at: str | None
    checked_at: str
    issuer: str
    issuer_short: str
    url: str
    unknown_statuses: list[str]
    regions: list[str]

    def as_dict(self) -> dict:
        return asdict(self)


def _rank(status: str) -> int:
    """Severity rank, lower is worse.

    An unrecognised value sorts as most severe, not least. If the FCDO adds a
    category we have not seen, the failure mode should be over-warning rather
    than quietly dropping a serious advisory to the bottom.
    """
    try:
        return SEVERITY.index(status)
    except ValueError:
        return -1


_TAG = re.compile(r'<[^>]+>')
_WS = re.compile(r'\s+')
_HEADING = re.compile(r'<h[23][^>]*>(.*?)</h[23]>', re.I | re.S)


def _regional_headings(details: dict) -> list[str]:
    """Names of the regions a 'to parts' advisory actually covers.

    A 'to parts of the country' badge with no parts named is worse than no
    badge: Egypt's advisory covers the Libya border and Sinai, nowhere near the
    Nile valley towns that top the duration ranking, so an unqualified warning
    on Girga implies something the FCDO is not saying. Surfacing the region
    names lets the reader see whether the advisory is about anywhere they were
    considering.
    """
    for part in details.get('parts', []) or []:
        if part.get('slug') != 'regional-risks':
            continue
        body = part.get('body') or ''
        out: list[str] = []
        for raw in _HEADING.findall(body):
            name = _WS.sub(' ', html.unescape(_TAG.sub('', raw))).strip()
            if name and name.lower() != 'regional risks':
                out.append(name)
        return out
    return []


def fetch(country_code: str, timeout: int = 34) -> Advisory:
    """Fetch one country's advisory. Build time only."""
    slug = SLUGS[country_code]
    req = urllib.request.Request(
        FCDO_API.format(slug=slug),
        headers={'User-Agent': 'eclipse.aravpanwar.com/0.1 (+https://github.com/aravpanwar/eclipse.aravpanwar.com)'},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.load(resp)

    details = payload.get('details', {}) or {}
    status = [s for s in (details.get('alert_status') or []) if s]
    status.sort(key=_rank)

    return Advisory(
        country_code=country_code,
        country=(details.get('country') or {}).get('name') or slug.title(),
        alert_status=status,
        labels=[LABELS.get(s, s.replace('_', ' ').capitalize()) for s in status],
        unknown_statuses=[s for s in status if s not in SEVERITY],
        regions=_regional_headings(details),
        worst=status[0] if status else None,
        reviewed_at=details.get('reviewed_at'),
        updated_at=payload.get('public_updated_at') or payload.get('updated_at'),
        checked_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        issuer=ISSUER,
        issuer_short=ISSUER_SHORT,
        url=FCDO_PAGE.format(slug=slug),
    )


def fetch_all(country_codes: list[str]) -> dict[str, Advisory]:
    out: dict[str, Advisory] = {}
    for cc in country_codes:
        out[cc] = fetch(cc)
    return out
