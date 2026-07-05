"""
fast-flights-g4: Unified Google Flights Parser with extended carrier support.

A companion package to fast-flights (https://github.com/AWeirdDev/flights) that
adds Allegiant (G4) and other carriers by deep-scanning Google Flights' payload[2]
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
from typing import Optional, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from fast_flights.integrations.base import FetchIntegration, DataSourceIntegration


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


def _build_datetime(date_tuple, time_tuple, fallback_year=2026):
    """Build a datetime from payload date/time tuples.

    date_tuple: (year, month, day) or similar 3-int sequence
    time_tuple: (hour, minute) or similar 2-int sequence
    """
    try:
        if isinstance(date_tuple, (list, tuple)) and len(date_tuple) >= 3:
            y, m, d = int(date_tuple[0]), int(date_tuple[1]), int(date_tuple[2])
        else:
            y, m, d = fallback_year, 1, 1

        if isinstance(time_tuple, (list, tuple)):
            h = _safe_int(time_tuple[0]) if len(time_tuple) > 0 else 0
            mi = _safe_int(time_tuple[1]) if len(time_tuple) > 1 else 0
        else:
            h, mi = 0, 0

        return datetime(y, m, d, h, mi)
    except (ValueError, TypeError, IndexError):
        return datetime(fallback_year, 1, 1, 0, 0)


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
    if flight_number == '??' and airline != '??':
        flight_number = airline

    origin = leg[LEG_ORIGIN_CODE] if len(leg) > LEG_ORIGIN_CODE and leg[LEG_ORIGIN_CODE] else '???'
    destination = leg[LEG_DEST_CODE] if len(leg) > LEG_DEST_CODE and leg[LEG_DEST_CODE] else '???'

    dep_time = leg[LEG_DEP_TIME] if len(leg) > LEG_DEP_TIME else [0, 0]
    arr_time = leg[LEG_ARR_TIME] if len(leg) > LEG_ARR_TIME else [0, 0]

    # Extract date tuples from deep-scan leg structure
    dep_date = leg[LEG_DEP_DATE] if len(leg) > LEG_DEP_DATE else None
    arr_date = leg[LEG_ARR_DATE] if len(leg) > LEG_ARR_DATE else None

    # Also try getting dates from detail sub-array
    if dep_date is None and detail and isinstance(detail, list) and len(detail) > DETAIL_DEP_DATE:
        dep_date = detail[DETAIL_DEP_DATE]
    if arr_date is None and detail and isinstance(detail, list) and len(detail) > DETAIL_ARR_DATE:
        arr_date = detail[DETAIL_ARR_DATE]

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

    departure_dt = _build_datetime(dep_date, dep_time)
    arrival_dt = _build_datetime(arr_date, arr_time)

    return {
        'airline': airline, 'flight_number': flight_number,
        'origin': origin, 'destination': destination,
        'departure': departure_dt, 'arrival': arrival_dt,
        'dep_time': dep_time, 'arr_time': arr_time,
        'dep_date': dep_date, 'arr_date': arr_date,
        'duration': duration, 'stops': stops,
        'aircraft': aircraft, 'flight_id': flight_id,
        'price': price, 'confidence': confidence,
    }


def _normalize_flight_key(airline: str, flight_number: str) -> str:
    """Normalize a flight identifier for dedup.

    Turns 'DL 4698' and 'DL' into comparable forms by extracting
    the airline code prefix from the flight_number when present.
    """
    fn = flight_number.strip()
    # If flight_number starts with the airline code, use it
    if fn and airline and fn.startswith(airline):
        return fn  # e.g., 'DL 4698'
    # Otherwise, use airline code alone
    return airline


def merge_results(p2_results: list, p3_results: list) -> list:
    """Merge payload[2] and payload[3] results, preferring richer data.

    Uses normalized flight keys for dedup so that a flight appearing as
    'DL' (from v3.0 direct) and 'DL 4698' (from deep-scan) merges correctly.
    Prefers the entry with higher confidence or a more specific flight_number.
    """
    merged_dict = {}
    for flight in p2_results:
        key = _normalize_flight_key(flight['airline'], flight['flight_number'])
        merged_dict[key] = flight

    for p3_flight in p3_results:
        key = _normalize_flight_key(p3_flight['airline'], p3_flight['flight_number'])
        if key in merged_dict:
            existing = merged_dict[key]
            # Prefer the entry with more specific flight_number or higher confidence
            p3_specific = len(p3_flight['flight_number'].strip()) > len(existing['flight_number'].strip())
            if p3_flight['confidence'] > existing['confidence'] or p3_specific:
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
        """Parse payload[3] via fast-flights v3.0 API.

        Uses get_flights(query) which calls the v3.0 JavaScript-based parser
        internally. No separate legacy fallback needed — v3.0 IS the JS parser.
        """
        results = []
        try:
            from fast_flights import get_flights
            if query is None:
                raise ValueError("query required for v3.0 API")
            for f in get_flights(query):
                # Build airline and flight_number
                # f.type = airline code ('DL', 'AA', 'G4') or 'multi' for mixed-airline itineraries
                # f.airlines = list of airline display names (e.g., ['American', 'Alaska'])
                # The v3.0 model doesn't expose individual flight numbers per leg,
                # so we build the best identifier we can.
                type_code = f.type or '??'
                airlines_list = f.airlines or []

                # Use the airline code as both airline and flight_number base
                if type_code == 'multi' and airlines_list:
                    airline = '+'.join(airlines_list)
                    flight_number = 'multi'
                elif airlines_list:
                    airline = airlines_list[0]
                    flight_number = type_code
                else:
                    airline = type_code
                    flight_number = type_code

                # Build proper departure/arrival datetimes from the v3.0 model
                first_leg = f.flights[0] if f.flights else None
                last_leg = f.flights[-1] if f.flights else None

                if first_leg:
                    dep_date = first_leg.departure.date  # (year, month, day)
                    dep_time = first_leg.departure.time  # (hour, minute)
                    departure = _build_datetime(dep_date, dep_time)
                    origin = first_leg.from_airport.code
                else:
                    dep_date, dep_time = None, (0, 0)
                    departure = datetime(2026, 1, 1, 0, 0)
                    origin = '???'

                if last_leg:
                    arr_date = last_leg.arrival.date
                    arr_time = last_leg.arrival.time
                    arrival = _build_datetime(arr_date, arr_time)
                    destination = last_leg.to_airport.code
                else:
                    arr_date, arr_time = None, (0, 0)
                    arrival = datetime(2026, 1, 1, 0, 0)
                    destination = '???'

                results.append({
                    'airline': airline, 'flight_number': flight_number,
                    'origin': origin, 'destination': destination,
                    'departure': departure, 'arrival': arrival,
                    'dep_time': list(dep_time) if dep_time else [0, 0],
                    'arr_time': list(arr_time) if arr_time else [0, 0],
                    'dep_date': list(dep_date) if dep_date else None,
                    'arr_date': list(arr_date) if arr_date else None,
                    'duration': sum(l.duration for l in f.flights),
                    'stops': len(f.flights) - 1,
                    'aircraft': f.flights[0].plane_type if f.flights else '',
                    'flight_id': '', 'price': f.price, 'confidence': 1.0,
                    'source': 'fast-flights-v3',
                })
        except (ImportError, TypeError, ValueError) as e:
            logger.info(f"fast-flights v3.0 parse failed: {e}")
        return results

    def _to_result(self, enriched: dict) -> Optional[FlightResult]:
        try:
            # Use pre-built datetime objects if available (from deep-scan or v3.0)
            departure = enriched.get('departure')
            arrival = enriched.get('arrival')

            # Fallback: build from separate date/time fields
            if departure is None or not isinstance(departure, datetime):
                departure = _build_datetime(
                    enriched.get('dep_date'),
                    enriched.get('dep_time', [0, 0]),
                )
            if arrival is None or not isinstance(arrival, datetime):
                arrival = _build_datetime(
                    enriched.get('arr_date'),
                    enriched.get('arr_time', [0, 0]),
                )

            price = enriched.get('price')
            if price is not None:
                price = float(price)

            return FlightResult(
                airline=enriched['airline'], flight_number=enriched['flight_number'],
                origin=enriched['origin'], destination=enriched['destination'],
                departure=departure, arrival=arrival,
                duration_min=enriched.get('duration', 0), stops=enriched.get('stops', 0),
                price=price, confidence=enriched.get('confidence', 1.0),
            )
        except Exception as e:
            logger.warning(f"Failed to convert: {e}")
            return None


def search_flights(
    origin: str,
    dest: str,
    date: str,
    adults: int = 1,
    *,
    seat: Literal['economy', 'premium-economy', 'business', 'first'] = 'economy',
    language: str = '',
    currency: str = '',
    max_stops: int | None = None,
    proxy: str | None = None,
    integration: 'FetchIntegration | DataSourceIntegration | None' = None,
) -> list[FlightResult]:
    """Search Google Flights with extended carrier support.

    Uses fast-flights v3.0 for major carriers (DL, AA, WN, UA, F9) and
    deep-scans payload[2] for Allegiant (G4) and other carriers that
    fast-flights misses.

    Args:
        origin: Origin airport IATA code (e.g., 'TYS')
        dest: Destination airport IATA code (e.g., 'LAS')
        date: Departure date in YYYY-MM-DD format
        adults: Number of adult passengers
        seat: Seat class — 'economy', 'premium-economy', 'business', or 'first'
        language: Response language code (e.g., 'en-US')
        currency: Currency code (e.g., 'USD')
        max_stops: Maximum number of stops to include
        proxy: HTTP proxy URL for the fetch request
        integration: fast-flights integration (e.g., BrightData) for fetching

    Returns:
        List of FlightResult objects sorted by price
    """
    from fast_flights import (
        fetch_flights_html, create_query, Passengers,
        FlightQuery as FFQuery, get_flights,
    )
    from fast_flights.integrations.base import DataSourceIntegration

    query = create_query(
        flights=[FFQuery(date=date, from_airport=origin, to_airport=dest, max_stops=max_stops)],
        seat=seat, trip='one-way', passengers=Passengers(adults=adults),
        language=language, currency=currency,
    )

    # If a DataSourceIntegration is provided, let get_flights handle everything
    if integration is not None and isinstance(integration, DataSourceIntegration):
        # DataSourceIntegration returns its own rich data type (not HTML),
        # so deep-scan is not possible. Return fast-flights results directly.
        ff_results = get_flights(query, proxy=proxy, integration=integration)
        results = []
        try:
            for f in ff_results:
                type_code = f.type or '??'
                airlines_list = f.airlines or []
                if type_code == 'multi' and airlines_list:
                    airline = '+'.join(airlines_list)
                    flight_number = 'multi'
                elif airlines_list:
                    airline = airlines_list[0]
                    flight_number = type_code
                else:
                    airline = type_code
                    flight_number = type_code

                first_leg = f.flights[0] if f.flights else None
                last_leg = f.flights[-1] if f.flights else None
                dep_dt = _build_datetime(
                    first_leg.departure.date if first_leg else None,
                    first_leg.departure.time if first_leg else (0, 0),
                ) if first_leg else datetime(2026, 1, 1)
                arr_dt = _build_datetime(
                    last_leg.arrival.date if last_leg else None,
                    last_leg.arrival.time if last_leg else (0, 0),
                ) if last_leg else datetime(2026, 1, 1)
                origin = first_leg.from_airport.code if first_leg else '???'
                dest = last_leg.to_airport.code if last_leg else '???'

                results.append(FlightResult(
                    airline=airline, flight_number=flight_number,
                    origin=origin, destination=dest,
                    departure=dep_dt, arrival=arr_dt,
                    duration_min=sum(l.duration for l in f.flights),
                    stops=len(f.flights) - 1,
                    price=float(f.price), confidence=1.0,
                ))
        except Exception as e:
            logger.warning(f"Failed to parse integration results: {e}")
        results.sort()
        return results

    html = fetch_flights_html(query, proxy=proxy, fetch_integration=integration)
    return GoogleFlightsParser().parse(html, query)
