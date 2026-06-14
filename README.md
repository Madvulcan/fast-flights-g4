# fast-flights-g4

A companion package to [fast-flights](https://github.com/AWeirdDev/flights) that adds **Allegiant (G4)**, **Icelandair (FI)**, **Zipair (ZG)**, and other carriers that fast-flights misses by deep-scanning Google Flights' `payload[2]` protobuf structure.

## What It Adds

fast-flights v3.0 parses `payload[3]` from Google Flights, which contains data for major carriers (Delta, American, Southwest, United, Frontier). However, Google stores some carrier data — including Allegiant and select international carriers — in `payload[2]` which fast-flights does not parse.

This package deep-scans `payload[2]` to extract those carriers and merges them with fast-flights results.

### Carrier Coverage

| Carrier | fast-flights v3.0 | fast-flights-g4 |
|---------|-------------------|-----------------|
| DL, AA, WN, UA, F9 | Yes | Yes |
| G4 (Allegiant) | **No** | **Yes** |
| FI (Icelandair) | **No** | **Yes** |
| ZG (Zipair) | **No** | **Yes** |
| Other payload[2] carriers | **No** | **Yes** |

**The deep-scan approach:** Google's `payload[2]` structure is undocumented and inconsistent — different carriers appear at different nesting depths with different formats. Rather than guessing the structure, we recursively walk the entire tree and find all 25-element arrays matching the flight leg pattern.

### Example: TYS→LAS

```
$230: F9  1847 (1 stop)   ← fast-flights v3.0
$395: G4  92   (nonstop)  ← deep-scan only (Allegiant)
$434: DL  5279 (1 stop)   ← fast-flights v3.0
$434: AA  6003 (1 stop)   ← fast-flights v3.0
$477: WN  1801 (1 stop)   ← fast-flights v3.0
```

Without this package, the Allegiant nonstop is invisible.

### Example: JFK→LHR

```
$415: FI  614  (nonstop)  ← deep-scan only (Icelandair)
```

## Installation

```bash
pip install fast-flights-g4
```

Requires Python 3.10+. Dependencies (`fast-flights>=3.0`, `selectolax`) are installed automatically.

## Usage

```python
from fast_flights_g4 import search_flights

# Returns list of FlightResult sorted by price
results = search_flights('TYS', 'LAS', '2026-06-19')
for r in results:
    print(f"${r.price}: {r.airline} {r.flight_number} ({r.stops} stops)")
```

### Lower-level API

```python
from fast_flights_g4 import GoogleFlightsParser

parser = GoogleFlightsParser()
results = parser.parse(html, query)
```

## Under the Hood

1. Fetches Google Flights HTML via fast-flights
2. fast-flights v3.0 parses `payload[3]` for major carriers
3. A deep-scan recursive walker searches `payload[2]` for additional carriers
4. Results are merged, deduplicated by (airline, flight_number), and sorted by price

## Dependencies

- [fast-flights](https://github.com/AWeirdDev/flights) >= 3.0
- selectolax >= 0.3.20
