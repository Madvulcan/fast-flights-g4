"""
Phase 1: Deep-Scan Discovery Module

Recursively walks the entire payload[2] tree from Google Flights to find ALL
25-element leg entries regardless of nesting depth. This is the core mechanism
for extracting Allegiant (G4) flight data that fast-flights misses.

Part of fast-flights-g4: https://github.com/madvulcan/fast-flights-g4
"""

from __future__ import annotations
import json
import logging
from typing import Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Leg field indices (25-element arrays in payload[2])
LEG_AIRLINE_CODE = 0
LEG_AIRLINE_NAME = 1
LEG_DETAIL_INFO = 2
LEG_ORIGIN_CODE = 3
LEG_DEP_DATE = 4
LEG_DEP_TIME = 5
LEG_DEST_CODE = 6
LEG_ARR_DATE = 7
LEG_ARR_TIME = 8
LEG_DURATION = 9
LEG_STOPS = 12
LEG_FLIGHT_ID = 17

# Detail sub-array indices (leg[2][0], 33 elements)
DETAIL_ORIGIN_CODE = 3
DETAIL_ORIGIN_NAME = 4
DETAIL_DEST_NAME = 5
DETAIL_DEST_CODE = 6
DETAIL_DEP_TIME = 8
DETAIL_ARR_TIME = 10
DETAIL_DURATION = 11
DETAIL_AIRCRAFT = 17
DETAIL_DEP_DATE = 20
DETAIL_ARR_DATE = 21
DETAIL_FLIGHT_NO = 22


@dataclass
class LegDiscovery:
    """A discovered flight leg with its tree context."""
    leg: list
    path: list[int] = field(default_factory=list)
    parent: list = field(default_factory=list)
    index_in_parent: int = 0
    depth: int = 0
    source_label: str = 'unknown'

    @property
    def airline_code(self) -> str:
        return self.leg[LEG_AIRLINE_CODE] if len(self.leg) > LEG_AIRLINE_CODE else '??'

    @property
    def identity(self) -> str:
        origin = self.leg[LEG_ORIGIN_CODE] if len(self.leg) > LEG_ORIGIN_CODE else ''
        dest = self.leg[LEG_DEST_CODE] if len(self.leg) > LEG_DEST_CODE else ''
        dep_time = str(self.leg[LEG_DEP_TIME]) if len(self.leg) > LEG_DEP_TIME else ''
        return f"{self.airline_code}|{origin}|{dest}|{dep_time}"


def is_leg_entry(data: Any) -> bool:
    """Check if data is a 25-element flight leg entry."""
    if not isinstance(data, list) or len(data) < 20:
        return False
    code = data[LEG_AIRLINE_CODE]
    if not isinstance(code, str) or not (1 <= len(code) <= 3):
        return False
    name = data[LEG_AIRLINE_NAME]
    return isinstance(name, list) and len(name) >= 1


def deep_scan_legs(
    data: Any,
    path: Optional[list[int]] = None,
    depth: int = 0,
    max_depth: int = 30,
    source_label: str = 'unknown',
) -> list[LegDiscovery]:
    """Recursively scan any data structure for flight leg entries.

    Scans the ENTIRE tree and finds ALL 25-element arrays matching the flight
    leg pattern, regardless of nesting depth. The max_depth parameter (default: 30)
    prevents infinite recursion on malformed payloads.

    Args:
        data: JSON-decoded protobuf object
        path: Indices tracing from root to current data
        depth: Current recursion depth (internal)
        max_depth: Safety limit preventing stack overflow
        source_label: Which branch ('flight_data' or 'price_data')

    Returns:
        List of LegDiscovery objects for all legs found
    """
    if path is None:
        path = []
    if depth > max_depth or not isinstance(data, list):
        return []

    results: list[LegDiscovery] = []
    for i, item in enumerate(data):
        if is_leg_entry(item):
            results.append(LegDiscovery(
                leg=item, path=path + [i], parent=data,
                index_in_parent=i, depth=depth, source_label=source_label,
            ))
        elif isinstance(item, list):
            results.extend(deep_scan_legs(
                item, path=path + [i], depth=depth + 1,
                max_depth=max_depth, source_label=source_label,
            ))
    return results


def extract_payload(html: str) -> list:
    """Extract the JavaScript payload from Google Flights HTML."""
    from selectolax.lexbor import LexborHTMLParser
    parser = LexborHTMLParser(html)
    script = parser.css_first(r"script.ds\:1")
    if script is None:
        raise ValueError("Could not find <script class='ds:1'> in HTML")
    js_text = script.text()
    data_str = js_text.split("data:", 1)[1].rsplit(",", 1)[0]
    if data_str.endswith("errorHasStatus: true"):
        raise ValueError("Google returned an error status")
    return json.loads(data_str)
