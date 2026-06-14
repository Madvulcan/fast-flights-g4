"""
fast-flights-g4: Unified Google Flights Parser with G4 (Allegiant) support.

A companion package to fast-flights (https://github.com/AWeirdDev/flights) that
adds Allegiant (G4) flight data by deep-scanning Google Flights' payload[2]
protobuf structure, which fast-flights does not parse.

 pip install fast-flights-g4
"""

from __future__ import annotations
import logging
from datetime import datetime

from .deep_scan import (
    LegDiscovery, extract_payload, deep_scan_legs, is_leg_entry,
    LEG_AIRLINE_CODE, LEG_AIRLINE_NAME, LEG_DETAIL_INFO,
    LEG_ORIGIN_CODE, LEG_DEP_DATE, LEG_DEP_TIME, LEG_DEST_CODE,
    LEG_ARR_DATE, LEG_ARR_TIME, LEG_DURATION, LEG_STOPS, LEG_FLIGHT_ID,
    DETAIL_ORIGIN_CODE, DETAIL_ORIGIN_NAME, DETAIL_DEST_NAME, DETAIL_DEST_CODE,
    DETAIL_DEP_TIME, DETAIL_ARR_TIME, DETAIL_DURATION, DETAIL_AIRCRAFT,
    DETAIL_DEP_DATE, DETAIL_ARR_DATE, DETAIL_FLIGHT_NO,
)

logger = logging.getLogger(__name__)


from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FlightResult:
    airline: str
    flight_number: str
    origin: str
    destination: str
    departure: datetime
    arrival: datetime
    duration_min: int = 0
    stops: int = 0
    price: float = 0.0
    currency: str = 'USD'
    confidence: float = 1.0
    raw_leg: list = field(default_factory=list)

    def __lt__(self, other):
        return self.price < other.price


def _safe_int(val, default=0):
    if val is None:
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def enrich_segments(leg_discovery, price_data=None, source_label='unknown'):
    """Extract enriched flight data from a leg discovery."""
    leg = leg_discovery.leg

    detail = None
    try:
        detail_info = leg[LEG_DETAIL_INFO] if len(leg) > LEG_DETAIL_INFO else None
        if detail_info and isinstance(detail_info, list) and len(detail_info) > 0:
            detail = detail_info[0]
    except (IndexError, TypeError):
        pass

    airline = '??'
    flight_number = '??'
    if detail and isinstance(detail, list) and len(detail) > DETAIL_FLIGHT_NO:
        try:
            flight_info = detail[DETAIL_FLIGHT_NO]
            if isinstance(flight_info, list) and len(flight_info) >= 2:
                airline = flight_info[0] or '??'
                flight_number = f"{flight_info[0]} {flight_info[1]}"
        except (IndexError, TypeError):
            pass
    if airline == '??' and len(leg) > LEG_AIRLINE_CODE:
        airline = leg[LEG_AIRLINE_CODE] or '??'

    origin = leg[LEG_ORIGIN_CODE] if len(leg) > LEG_ORIGIN_CODE and leg[LEG_ORIGIN_CODE] else '???'
    destination = leg[LEG_DEST_CODE] if len(leg) > LEG_DEST_CODE and leg[LEG_DEST_CODE] else '???'

    dep_time = leg[LEG_DEP_TIME] if len(leg) > LEG_DEP_TIME else [0, 0]
    arr_time = leg[LEG_ARR_TIME] if len(leg) > LEG_ARR_TIME else [0, 0]
    raw_duration = leg[LEG_DURATION] if len(leg) > LEG_DURATION else None
    duration = _safe_int(raw_duration, 0) if isinstance(raw_duration, (int, float)) else 0
    stops = _safe_int(leg[LEG_STOPS], 0) if len(leg) > LEG_STOPS else 0
    aircraft = detail[DETAIL_AIRCRAFT] or '' if detail and isinstance(detail, list) and len(detail) > DETAIL_AIRCRAFT else ''
    flight_id = leg[LEG_FLIGHT_ID] or '' if len(leg) > LEG_FLIGHT_ID else ''

    price = None
    confidence = 0.9
    if source_label == 'price_data' and len(leg) > 9:
        p = leg[9]
        if isinstance(p, (int, float)) and p > 0:
            price = float(p)
    if price is None and price_data is not None:
        try:
            idx = leg_discovery.path[0] if leg_discovery.path else -1
            if 0 <= idx < len(price_data):
                pe = price_data[idx]
                if isinstance(pe, list) and len(pe) == 25 and pe[9] and isinstance(pe[9], (int, float)):
                    price = float(pe[9])
                elif isinstance(pe, list) and len(pe) == 2:
                    inner = pe[1]
                    if isinstance(inner, list) and len(inner) >= 2:
                        if isinstance(inner[0], list) and len(inner[0]) > 1 and isinstance(inner[0][1], (int, float)):
                            price = float(inner[0][1])
                        elif isinstance(inner[1], (int, float)):
                            price = float(inner[1])
        except (IndexError, TypeError, ValueError):
            confidence = 0.5

    return {
        'airline': airline, 'flight_number': flight_number,
        'origin': origin, 'destination': destination,
        'dep_time': dep_time, 'arr_time': arr_time,
        'duration': duration, 'stops': stops,
        'aircraft': aircraft, 'flight_id': flight_id,
        'price': price, 'confidence': confidence,
    }


def merge_results(p2_results: list, p3_results: list) -> list:
    """Merge payload[2] and payload[3] results, preferring richer data."""
    merged_dict = {}
    for flight in p2_results:
        key = (flight['airline'], flight['flight_number'])
        merged_dict[key] = flight
    for p3_flight in p3_results:
        key = (p3_flight['airline'], p3_flight['flight_number'])
        if key in merged_dict:
            if p3_flight['confidence'] > merged_dict[key]['confidence']:
                merged_dict[key] = p3_flight
        else:
            merged_dict[key] = p3_flight
    merged = list(merged_dict.values())
    logger.info("Merged %d deep-scan + %d fast-flights = %d unique flights",
                len(p2_results), len(p3_results), len(merged))
    return merged


class GoogleFlightsParser:
    """Unified parser: fast-flights v3.0 for major carriers + deep-scan for G4."""

    def parse(self, html: str, query=None) -> list[FlightResult]:
        payload = extract_payload(html)
        p2_results = self._parse_payload_2(payload)
        p3_results = self._parse_payload_3(html, query)
        merged = merge_results(p2_results, p3_results)
        results = []
        for enriched in merged:
            result = self._to_result(enriched)
            if result:
                results.append(result)
        results.sort()
        return results

    def _parse_payload_2(self, payload: list) -> list:
        """Deep-scan payload[2] for discount carriers."""
        results = []
        if len(payload) > 2 and payload[2]:
            main = payload[2][0] if isinstance(payload[2], list) and len(payload[2]) > 0 else None
            if main and isinstance(main, list) and len(main) >= 2:
                fd_legs = deep_scan_legs(main[0], source_label='flight_data')
                pd_legs = deep_scan_legs(main[1], source_label='price_data') if isinstance(main[1], list) else []
                seen = {}
                for d in fd_legs + pd_legs:
                    if d.identity not in seen:
                        seen[d.identity] = d
                for disc in seen.values():
                    enriched = enrich_segments(disc, main[1], disc.source_label)
                    if enriched.get('price'):
                        results.append(enriched)
        return results

    def _parse_payload_3(self, html: str, query=None) -> list:
        """Parse payload[3] via fast-flights v3.0 (with legacy fallback)."""
        results = []
        try:
            from fast_flights import get_flights
            if query is None:
                raise ValueError("query required for v3.0 API")
            for f in get_flights(query):
                airline = f.airlines[0] if f.airlines else '??'
                results.append({
                    'airline': airline, 'flight_number': f.type,
                    'origin': f.flights[0].from_airport.code,
                    'destination': f.flights[-1].to_airport.code,
                    'dep_time': list(f.flights[0].departure.time),
                    'arr_time': list(f.flights[-1].arrival.time),
                    'duration': sum(l.duration for l in f.flights),
                    'stops': len(f.flights) - 1,
                    'aircraft': f.flights[0].plane_type if f.flights else '',
                    'flight_id': '', 'price': f.price, 'confidence': 1.0,
                    'source': 'fast-flights-v3',
                })
        except (ImportError, TypeError, ValueError) as e:
            logger.info(f"Falling back to legacy parse(): {e}")
            try:
                from fast_flights.parser import parse as parse_p3
                for f in parse_p3(html):
                    if f and f.flights:
                        results.append({
                            'airline': f.airlines[0] if f.airlines else '??',
                            'flight_number': f.airlines[0] if f.airlines else '??',
                            'origin': f.flights[0].from_airport.code,
                            'destination': f.flights[-1].to_airport.code,
                            'dep_time': [0, 0], 'arr_time': [0, 0],
                            'duration': sum(l.duration for l in f.flights),
                            'stops': len(f.flights) - 1,
                            'aircraft': '', 'flight_id': '',
                            'price': f.price, 'confidence': 1.0,
                            'source': 'fast-flights-legacy',
                        })
            except Exception as e2:
                logger.warning(f"Legacy parse also failed: {e2}")
        return results

    def _to_result(self, enriched: dict) -> Optional[FlightResult]:
        try:
            dt = enriched.get('dep_time') or [0, 0]
            at = enriched.get('arr_time') or [0, 0]
            price = enriched.get('price')
            if price is not None:
                price = float(price)
            return FlightResult(
                airline=enriched['airline'], flight_number=enriched['flight_number'],
                origin=enriched['origin'], destination=enriched['destination'],
                departure=datetime(2026, 1, 1, _safe_int(dt[0]), _safe_int(dt[1] if len(dt) > 1 else 0)),
                arrival=datetime(2026, 1, 1, _safe_int(at[0]), _safe_int(at[1] if len(at) > 1 else 0)),
                duration_min=enriched.get('duration', 0), stops=enriched.get('stops', 0),
                price=price, confidence=enriched.get('confidence', 1.0),
            )
        except Exception as e:
            logger.warning(f"Failed to convert: {e}")
            return None


def search_flights(origin: str, dest: str, date: str, adults: int = 1) -> list[FlightResult]:
    """Search Google Flights with G4 (Allegiant) support.

    Uses fast-flights v3.0 for major carriers (DL, AA, WN, UA, F9) and
    deep-scans payload[2] for Allegiant (G4) which fast-flights misses.

    Args:
        origin: Origin airport IATA code (e.g., 'TYS')
        dest: Destination airport IATA code (e.g., 'LAS')
        date: Departure date in YYYY-MM-DD format
        adults: Number of adult passengers

    Returns:
        List of FlightResult objects sorted by price
    """
    from fast_flights import fetch_flights_html, create_query, Passengers, FlightQuery as FFQuery
    query = create_query(
        flights=[FFQuery(date=date, from_airport=origin, to_airport=dest)],
        seat='economy', trip='one-way', passengers=Passengers(adults=adults),
    )
    html = fetch_flights_html(query)
    return GoogleFlightsParser().parse(html, query)
