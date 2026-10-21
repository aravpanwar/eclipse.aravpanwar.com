# Totality Path & Nearby Locations
# Copyright (C) 2026 Arav Panwar
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. See <https://www.gnu.org/licenses/>.

"""Wikipedia pageviews as a proxy for how much attention a place gets.

NOT USED IN THE PUBLISHED DATASET. Kept because the brief asked whether an
attention signal could identify overpriced locations without scraping prices,
and the answer, tested, is no. Three findings, in order of how badly each one
breaks the idea:

1. Coverage is 28%. Of 40 randomly sampled places along the path, only 11 have
   an English Wikipedia article with more than 50 views a month. GeoNames names
   carry diacritics ('Al Balyana', 'Abu Tisht') that do not match article
   titles, and stripping them recovers some but not most: many of these towns
   simply have no English article. A column that is empty for three places in
   four is not a column.

2. Worse than absent, it is quietly wrong. 'Nag Hammadi' returns about 28000
   views a month; the GeoNames spelling 'Nag Hammadi' with a circumflex returns
   15, because it resolves to something else rather than returning a 404. A
   missing value is safe, a plausible wrong one is not.

3. The ratio inverts. Attention per bed makes Girga, an obscure town with four
   hotels, score 1027 against Luxor's 157, so the metric ranks the unknown
   place as six times more overpriced than the famous one. It is measuring
   absence of supply, not excess of demand, and with denominators in the single
   digits it is mostly noise.

The functions below work and are left for anyone who wants to test the idea on
a different corpus, such as comparing a place against its own history to detect
eclipse-driven interest, which is a better-posed question than a cross-sectional
ratio. Nothing here feeds the build.


The point of this column is to identify places whose demand is likely to run
ahead of their capacity, without touching a single price. No prices are
scraped, quoted or stored anywhere in this project: a rate has a shelf life of
weeks and scraping one is a licence problem, whereas "how many people look this
place up" and "how many beds does it have" are both openly published and stay
true.

Attention per bed is the derived figure. A place with a lot of interest and few
rooms is where a premium can be charged; a place with the same interest and ten
times the rooms cannot sustain one. That is a structural claim about supply and
demand, not a measurement of what anyone is actually charging, and it should be
read as the former.

Caveats that belong on the page next to the number:

- English Wikipedia over-represents anglophone interest. Girga getting a
  quarter of Luxor's traffic says as much about who edits and reads English
  Wikipedia as about travel intent.
- Pageviews measure curiosity, not intent to travel. A place can be famous for
  reasons that bring nobody to it.
- Baseline attention is not eclipse attention. Comparing a place to itself over
  time would show eclipse-driven interest; this is a snapshot of the baseline.
"""

from __future__ import annotations

import json
import statistics
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict

API = ('https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/'
       '{project}/all-access/user/{title}/monthly/{start}/{end}')

SUMMARY = 'https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}'

USER_AGENT = ('eclipse.aravpanwar.com/0.1 (https://github.com/aravpanwar/eclipse.aravpanwar.com) '
              'build-time dataset generation')


@dataclass
class Attention:
    title: str
    project: str
    months: int
    median_monthly_views: int
    total_views: int
    resolved: bool

    def as_dict(self) -> dict:
        return asdict(self)


def _get(url: str, timeout: int = 34):
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def pageviews(title: str, start: str, end: str,
              project: str = 'en.wikipedia') -> Attention | None:
    """Monthly pageviews for one article.

    The most recent month is dropped: a request that reaches into the current
    month returns a partial count, and a partial month read as a full one makes
    a place look abandoned.
    """
    quoted = urllib.parse.quote(title.replace(' ', '_'), safe='')
    try:
        data = _get(API.format(project=project, title=quoted, start=start, end=end))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise

    items = data.get('items', [])
    if len(items) > 1:
        items = items[:-1]
    if not items:
        return None

    views = [int(i['views']) for i in items]
    return Attention(
        title=title,
        project=project,
        months=len(views),
        median_monthly_views=int(statistics.median(views)),
        total_views=sum(views),
        resolved=True,
    )


def attention_per_bed(median_monthly_views: int, lodging_count: int) -> float | None:
    """Monthly pageviews per lodging feature within reach.

    A ratio, not a price. High means interest outruns capacity, which is the
    condition under which a premium can be charged; it does not mean a premium
    is being charged. Undefined where there is no lodging at all, because
    dividing by zero would rank a place with no rooms as infinitely marked up
    when it is simply somewhere you cannot stay.
    """
    if not lodging_count:
        return None
    return round(median_monthly_views / lodging_count, 1)
