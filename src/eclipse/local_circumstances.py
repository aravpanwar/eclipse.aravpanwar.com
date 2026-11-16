# Totality Path & Nearby Locations
# Copyright (C) 2026 Arav Panwar
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. See <https://www.gnu.org/licenses/>.

"""Local circumstances of a solar eclipse from Besselian elements.

Method follows the Explanatory Supplement to the Astronomical Ephemeris (1974)
and Meeus, *Elements of Solar Eclipses* (1989), which is the same basis Espenak
used for the NASA predictions we take elements from.

Sign conventions and units, stated once because mixing them up is the classic
source of silent kilometre-scale errors:

  x, y, l1, l2   Earth equatorial radii
  d, mu          degrees
  tan f1, f2     dimensionless
  longitude      degrees, EAST POSITIVE (enters as mu + lon; see note below)
  t              decimal hours from t0, in TDT

The observer's position enters through the fundamental plane: a plane through
Earth's centre perpendicular to the shadow axis, with +y north and +x east.

The local hour angle of the shadow axis is H = mu + longitude for east-positive
longitude, mu being the Greenwich hour angle. Meeus writes it mu - longitude
because he counts longitude positive west. Getting this sign backwards mirrors the path about the sub-shadow
meridian: duration at the peak still looks right, but the peak lands on the
wrong side, which is why the greatest-duration point is the load-bearing test
rather than Luxor's duration alone.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path

# IAU 1976 / WGS84-consistent flattening used for eclipse work.
FLATTENING = 1.0 / 298.257
EARTH_RADIUS_KM = 6378.137

# Fraction of Earth's equatorial radius per km, for converting l1/l2 offsets.
_KM_PER_RADIUS = EARTH_RADIUS_KM


@dataclass
class Elements:
    """Polynomial Besselian elements for one eclipse."""

    x: list[float]
    y: list[float]
    d: list[float]
    l1: list[float]
    l2: list[float]
    mu: list[float]
    tan_f1: float
    tan_f2: float
    t0_tdt_hours: float
    delta_t_seconds: float
    # Latitudes to look for the centre line in, south then north. Only a
    # path that doubles back, as 2033's does in the Arctic, needs it narrowed.
    lat_window: tuple[float, float] | None = None

    @classmethod
    def from_json(cls, path: str | Path) -> "Elements":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        e = raw["elements"]
        return cls(
            x=e["x"], y=e["y"], d=e["d"], l1=e["l1"], l2=e["l2"], mu=e["mu"],
            tan_f1=raw["tan_f1"], tan_f2=raw["tan_f2"],
            t0_tdt_hours=raw["t0_tdt_hours"],
            delta_t_seconds=raw["delta_t_seconds"],
        )

    def at(self, t: float) -> dict[str, float]:
        """Evaluate every element at t decimal hours from t0.

        a = a0 + a1*t + a2*t^2 + a3*t^3
        """
        def poly(c: list[float]) -> float:
            return c[0] + c[1] * t + c[2] * t * t + c[3] * t * t * t

        return {
            "x": poly(self.x),
            "y": poly(self.y),
            "d": poly(self.d),
            "l1": poly(self.l1),
            "l2": poly(self.l2),
            "mu": poly(self.mu),
        }

    def rates(self, t: float) -> dict[str, float]:
        """Time derivatives, per hour. Needed for the contact-time solution."""
        def dpoly(c: list[float]) -> float:
            return c[1] + 2.0 * c[2] * t + 3.0 * c[3] * t * t

        return {
            "x": dpoly(self.x),
            "y": dpoly(self.y),
            "d": dpoly(self.d),
            "mu": dpoly(self.mu),
        }


def geocentric_observer(lat_deg: float, lon_deg: float, elevation_m: float = 0.0):
    """Geodetic latitude to the geocentric quantities the method needs.

    Returns (rho_sin_phi_prime, rho_cos_phi_prime) in Earth equatorial radii,
    accounting for flattening and observer height.
    """
    lat = math.radians(lat_deg)
    # u is the "reduced" or parametric latitude.
    u = math.atan(math.tan(lat) * (1.0 - FLATTENING))
    height = elevation_m / 1000.0 / _KM_PER_RADIUS

    rho_sin = (1.0 - FLATTENING) * math.sin(u) + height * math.sin(lat)
    rho_cos = math.cos(u) + height * math.cos(lat)
    return rho_sin, rho_cos


def fundamental_plane(lat_deg, lon_deg, elevation_m, el, delta_t_seconds=0.0):
    """Observer coordinates (xi, eta, zeta) in the fundamental plane.

    mu is tabulated against TDT but expresses a Greenwich hour angle, which is
    a UT quantity. The two frames differ by delta_T, so mu is reduced by
    delta_T * 15 / 3600 degrees here. Leaving that out keeps latitude right
    but moves the whole path west, by about 30 km at the latitude of 2027's
    path, far more than any other error in the calculation.
    """
    rho_sin, rho_cos = geocentric_observer(lat_deg, lon_deg, elevation_m)
    d = math.radians(el["d"])
    mu = el["mu"] - delta_t_seconds / 3600.0 * 15.0
    # Local hour angle of the shadow axis. East longitude positive.
    h = math.radians(mu + lon_deg)

    xi = rho_cos * math.sin(h)
    eta = rho_sin * math.cos(d) - rho_cos * math.cos(h) * math.sin(d)
    zeta = rho_sin * math.sin(d) + rho_cos * math.cos(h) * math.cos(d)
    return xi, eta, zeta


def _shadow_radii(el, zeta, tan_f1, tan_f2):
    """Penumbral and umbral shadow radii at the observer's distance zeta."""
    l1 = el["l1"] - zeta * tan_f1
    l2 = el["l2"] - zeta * tan_f2
    return l1, l2


@dataclass
class Circumstances:
    """Local circumstances for one observer."""

    latitude: float
    longitude: float
    elevation_m: float
    in_totality: bool
    magnitude: float
    obscuration: float
    duration_seconds: float | None
    max_eclipse_ut_hours: float | None
    second_contact_ut_hours: float | None
    third_contact_ut_hours: float | None
    sun_altitude_deg: float | None
    sun_azimuth_deg: float | None
    distance_from_axis_radii: float

    def as_dict(self) -> dict:
        return asdict(self)


def _relative_position(lat, lon, elev, elements: Elements, t):
    """(u, v) offset of the observer from the shadow axis, and derivatives."""
    el = elements.at(t)
    rt = elements.rates(t)
    xi, eta, zeta = fundamental_plane(lat, lon, elev, el, elements.delta_t_seconds)

    d = math.radians(el["d"])
    mu_rate = math.radians(rt["mu"])
    d_rate = math.radians(rt["d"])

    u = el["x"] - xi
    v = el["y"] - eta

    # Derivatives of the observer's fundamental-plane coordinates.
    # xi' = mu' * rho_cos * cos(h); eta' = mu' * xi * sin(d) - zeta * d'
    rho_sin, rho_cos = geocentric_observer(lat, lon, elev)
    h = math.radians(el["mu"] - elements.delta_t_seconds / 3600.0 * 15.0 + lon)
    xi_rate = mu_rate * rho_cos * math.cos(h)
    eta_rate = mu_rate * xi * math.sin(d) - zeta * d_rate

    u_rate = rt["x"] - xi_rate
    v_rate = rt["y"] - eta_rate
    return u, v, u_rate, v_rate, el, zeta


def _time_of_maximum(lat, lon, elev, elements: Elements, tol=1e-9, max_iter=60):
    """Iterate to the instant the observer is closest to the shadow axis.

    Newton step on d/dt (u^2 + v^2) = 0, i.e. tau = -(u*u' + v*v')/(u'^2 + v'^2).
    """
    t = 0.0
    for _ in range(max_iter):
        u, v, u_r, v_r, _, _ = _relative_position(lat, lon, elev, elements, t)
        denom = u_r * u_r + v_r * v_r
        if denom == 0.0:
            break
        tau = -(u * u_r + v * v_r) / denom
        t += tau
        if abs(tau) < tol:
            break
    return t


def compute(lat: float, lon: float, elevation_m: float, elements: Elements) -> Circumstances:
    """Local circumstances at one point."""
    t_max = _time_of_maximum(lat, lon, elevation_m, elements)
    u, v, u_r, v_r, el, zeta = _relative_position(lat, lon, elevation_m, elements, t_max)

    m = math.hypot(u, v)                      # distance from axis, Earth radii
    l1, l2 = _shadow_radii(el, zeta, elements.tan_f1, elements.tan_f2)

    # Magnitude: fraction of the solar diameter covered.
    if (l1 + l2) == 0:
        magnitude = 0.0
    else:
        magnitude = (l1 - m) / (l1 + l2)

    in_totality = m < abs(l2)

    duration = None
    t2 = t3 = None
    if in_totality:
        # Relative speed of the observer across the umbra, radii per hour.
        n = math.hypot(u_r, v_r)
        if n > 0:
            # Half-chord of the umbral crossing.
            discriminant = l2 * l2 - (u * v_r - v * u_r) ** 2 / (n * n)
            if discriminant > 0:
                half = math.sqrt(discriminant) / n
                t2 = t_max - half
                t3 = t_max + half
                duration = (t3 - t2) * 3600.0

    alt, az = _sun_altaz(lat, lon, elevation_m, elements, t_max)

    delta_hours = elements.delta_t_seconds / 3600.0
    to_ut = lambda t: (elements.t0_tdt_hours + t - delta_hours) if t is not None else None

    return Circumstances(
        latitude=lat,
        longitude=lon,
        elevation_m=elevation_m,
        in_totality=in_totality,
        magnitude=magnitude,
        obscuration=_obscuration(m, l1, l2),
        duration_seconds=duration,
        max_eclipse_ut_hours=to_ut(t_max),
        second_contact_ut_hours=to_ut(t2),
        third_contact_ut_hours=to_ut(t3),
        sun_altitude_deg=alt,
        sun_azimuth_deg=az,
        distance_from_axis_radii=m,
    )


def _sun_altaz(lat, lon, elev, elements: Elements, t):
    """Sun altitude and azimuth, from the shadow-axis geometry.

    The Sun is very nearly along the shadow axis, so its topocentric direction
    follows from d and the local hour angle.
    """
    el = elements.at(t)
    d = math.radians(el["d"])
    h = math.radians(el["mu"] - elements.delta_t_seconds / 3600.0 * 15.0 + lon)
    phi = math.radians(lat)

    sin_alt = (math.sin(phi) * math.sin(d)
               + math.cos(phi) * math.cos(d) * math.cos(h))
    sin_alt = max(-1.0, min(1.0, sin_alt))
    alt = math.degrees(math.asin(sin_alt))

    az = math.degrees(math.atan2(
        -math.cos(d) * math.sin(h),
        math.sin(d) * math.cos(phi) - math.cos(d) * math.sin(phi) * math.cos(h),
    ))
    return alt, az % 360.0


def _obscuration(m, l1, l2):
    """Fraction of the solar AREA covered. Distinct from magnitude."""
    if (l1 + l2) == 0:
        return 0.0
    if m >= l1:
        return 0.0
    if m < abs(l2):
        return 1.0
    # Sun and Moon radii in the same units, as seen in the plane.
    r_s = (l1 + l2) / 2.0
    r_m = (l1 - l2) / 2.0
    if r_s <= 0 or r_m <= 0:
        return 0.0
    # Circular segment overlap.
    c = max(-1.0, min(1.0, (r_s * r_s + m * m - r_m * r_m) / (2.0 * r_s * m)))
    a = max(-1.0, min(1.0, (r_m * r_m + m * m - r_s * r_s) / (2.0 * r_m * m)))
    alpha = 2.0 * math.acos(c)
    beta = 2.0 * math.acos(a)
    area = (0.5 * (beta - math.sin(beta)) * r_m * r_m
            + 0.5 * (alpha - math.sin(alpha)) * r_s * r_s)
    return area / (math.pi * r_s * r_s)
