# Totality Path & Nearby Locations
# Copyright (C) 2026 Arav Panwar
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. See <https://www.gnu.org/licenses/>.

"""Which eclipse a build is for, and the few choices made for it by hand.

Each script takes the event as its one argument, the id of a file in
data/elements/. Anything that can be worked out from the elements or from
the places found is worked out; data/events.json holds only what cannot,
such as how far along the path the map stops.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ELEMENTS = ROOT / 'data' / 'elements'
SETTINGS = ROOT / 'data' / 'events.json'


def available() -> list[str]:
    return sorted(p.stem for p in ELEMENTS.glob('*.json'))


def from_argv(argv: list[str] | None = None) -> str:
    """The event named on the command line, or exit saying which exist."""
    args = sys.argv[1:] if argv is None else argv
    events = available()
    if len(args) != 1 or args[0] not in events:
        script = Path(sys.argv[0]).name
        sys.exit(f'usage: python scripts/{script} <event>, one of {", ".join(events)}')
    return args[0]


def settings(event: str) -> dict:
    blob = json.loads(SETTINGS.read_text(encoding='utf-8')) if SETTINGS.exists() else {}
    return blob.get(event, {})


def day(event: str) -> date:
    return date.fromisoformat(event)


def long_date(event: str) -> str:
    """2 August 2027."""
    d = day(event)
    return f'{d.day} {d:%B %Y}'


def month_name(event: str) -> str:
    return f'{day(event):%B}'
