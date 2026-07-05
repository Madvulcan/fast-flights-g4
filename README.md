# fast-flights-g4

A companion package to [fast-flights](https://github.com/AWeirdDev/flights) that adds **Allegiant (G4)**, **Icelandair (FI)**, **Zipair (ZG)**, and other carriers that fast-flights misses by deep-scanning Google Flights' `payload[2]` protobuf structure.

The package was named fast-flights-g4 because the original scope was to add Allegiant flights to the results specifically, but other carriers have been added since.

## What It Adds

fast-flights v3.0 parses `payload[3]` from Google Flights, which contains data for major carriers (Delta, American, Southwest, United, Frontier). However, Google stores some carrier data — including Allegiant and select international carriers — in `payload[2]` which fast-flights does not parse.

This package deep-scans `payload[2]` to extract those carriers and merges them with fast-flights results.

### Carrier Coverage

| Carrier | fast-flights v3.0 | fast-flights-g4 |
|---------|-------------------|-----------------|
| DL, AA, WN, UA, F9 | Yes | Yes |
| G4 (Allegiant) | Partial* | **Yes** |
| FI (Icelandair) | **No** | **Yes** |
| ZG (Zipair) | **No** | **Yes** |
| Other payload[2] carriers | **No** | **Yes** |

*\* Allegiant sometimes appears in `payload[3]` (which fast-flights parses), but not consistently across all routes. The deep-scan ensures reliable coverage.*

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

### Basic search

```python
from fast_flights_g4 import search_flights

# Returns list of FlightResult sorted by price
results = search_flights('TYS', 'LAS', '2026-06-19')
for r in results:
    print(f"${r.price}: {r.airline} {r.flight_number} ({r.stops} stops)")
```

### With proxy or integration

```python
from fast_flights_g4 import search_flights

# Use a proxy to avoid IP blocks
results = search_flights('TYS', 'LAS', '2026-06-19', proxy='http://proxy:8080')

# Use Bright Data integration (requires fast-flights >= 3.0)
from fast_flights.integrations import BrightData
results = search_flights('TYS', 'LAS', '2026-06-19',
                         integration=BrightData(zone='my_zone'))
```

### Full parameter list

```python
results = search_flights(
    origin='TYS',
    dest='LAS',
    date='2026-06-19',
    adults=2,
    seat='economy',           # economy, premium-economy, business, first
    language='en-US',         # Response language
    currency='USD',           # Price currency
    max_stops=1,              # Maximum stops filter
    proxy=None,               # HTTP proxy URL
    integration=None,         # BrightData or other FetchIntegration
)
```

### Lower-level API

```python
from fast_flights_g4 import GoogleFlightsParser

parser = GoogleFlightsParser()
results = parser.parse(html, query)
```

## Under the Hood

1. Fetches Google Flights HTML via fast-flights (with optional proxy/integration)
2. fast-flights v3.0 parses `payload[3]` for major carriers
3. A deep-scan recursive walker searches `payload[2]` for additional carriers
4. Results are merged, deduplicated by normalized flight key, and sorted by price

## v0.2.0 Changes

- **Fixed dates**: Departure/arrival now use actual date from Google Flights data instead of hard-coded 2026-01-01
- **Fixed flight_number**: Deep-scan results get real flight numbers (e.g., 'DL 4698'); v3.0 results use airline code as identifier
- **Fixed dedup**: Merge uses normalized flight keys so 'DL' and 'DL 4698' correctly deduplicate
- **Added passthrough**: `proxy`, `integration`, `language`, `currency`, `max_stops`, and `seat` parameters now pass through to fast-flights
- **Removed dead code**: Legacy parser fallback (same function as v3.0 main path) removed
- **Multi-airline support**: `type='multi'` results now show concatenated airline names

## Dependencies

- [fast-flights](https://github.com/AWeirdDev/flights) >= 3.0
- selectolax >= 0.3.20
