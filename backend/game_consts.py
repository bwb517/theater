"""Shared game constants and geometry helpers.

Single source of truth for movement rates, the strength/will-to-fight/C2 enums,
and great-circle math. Imported by routers and the rules engine so the rules
layer and the live gameplay loop never disagree on the numbers.
"""
from __future__ import annotations

from math import radians, degrees, sin, cos, sqrt, atan2, asin

# km/h ground speed by unit type; 0 means the type cannot reposition.
MOVEMENT_RATES = {
    "Infantry": 4,
    "Armor": 25,
    "Artillery": 20,
    "Aviation": 150,
    "Logistics": 35,
    "SF": 6,
    "EW": 25,
    "Cyber": 0,
    "Naval": 30,
    "Air Defense": 20,
    "Mechanized Infantry": 30,
}

# Fallback ground speed for unrecognized unit types.
DEFAULT_MOVEMENT_RATE = 20

# Used only when a session does not carry an explicit time_per_turn_hours.
DEFAULT_TURN_HOURS = 24

# Strength ladder, ordered from healthiest (index 0) to destroyed (last).
STRENGTH_LADDER = ["Full", "Degraded", "Critical", "Destroyed"]
VALID_STRENGTHS = set(STRENGTH_LADDER)
STRENGTH_RANK = {s: i for i, s in enumerate(STRENGTH_LADDER)}

VALID_WTF = {"High", "Moderate", "Low", "Broken"}
VALID_C2 = {"Nominal", "Degraded", "Lost"}


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometres."""
    R = 6371.0
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat, dlng = lat2 - lat1, lng2 - lng1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def initial_bearing_deg(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Initial compass bearing (degrees) from point 1 toward point 2."""
    rlat1, rlat2 = radians(lat1), radians(lat2)
    dlng = radians(lng2 - lng1)
    x = sin(dlng) * cos(rlat2)
    y = cos(rlat1) * sin(rlat2) - sin(rlat1) * cos(rlat2) * cos(dlng)
    return (degrees(atan2(x, y)) + 360) % 360


def point_at_distance(lat: float, lng: float, bearing_deg: float, dist_km: float) -> tuple[float, float]:
    """Destination point reached by travelling dist_km along bearing from (lat,lng)."""
    R = 6371.0
    ang = dist_km / R
    brg = radians(bearing_deg)
    rlat, rlng = radians(lat), radians(lng)
    new_lat = asin(sin(rlat) * cos(ang) + cos(rlat) * sin(ang) * cos(brg))
    new_lng = rlng + atan2(
        sin(brg) * sin(ang) * cos(rlat),
        cos(ang) - sin(rlat) * sin(new_lat),
    )
    return degrees(new_lat), (degrees(new_lng) + 540) % 360 - 180
