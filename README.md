# fast-flights-g4

A companion package to [fast-flights](https://github.com/AWeirdDev/flights) that adds **Allegiant (G4)** flight data to search results.

## What It Adds

fast-flights v3.0 parses `payload[3]` from Google Flights, which contains data for major carriers (Delta, American, Southwest, United, Frontier). However, Google stores Allegiant flight data in a separate part of the response (`payload[2]`) that fast-flights does not parse.

This package fills that gap. It deep-scans `payload[2]` to extract Allegiant flights and merges them with the results from fast-flights.

### Carrier Coverage

| Carrier | fast-flights v3.0 | fast-flights-g4 |
|---------|-------------------|-----------------|
| DL, AA, WN, UA | Yes | Yes |
| F9 (Frontier) | Yes (v3.0+) | Yes |
| G4 (Allegiant) | **Missing** | **Yes** |

**Example:** Searching TYS→LAS returns 3 flights with fast-flights alone. With fast-flights-g4, you get 5 — including the Allegiant nonstop at $395, which is the cheapest option.

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

Output:
```
$230.0: F9 1847 (1 stops)
$395.0: G4 92 (0 stops)
$434.0: DL 5279 (1 stops)
$434.0: AA 6003 (1 stops)
$477.0: WN 1801 (1 stops)
```

### Lower-level API

```python
from fast_flights_g4 import GoogleFlightsParser

parser = GoogleFlightsParser()
results = parser.parse(html, query)
```

## Under the Hood

1. `search_flights()` fetches Google Flights HTML via fast-flights
2. Fast-flights v3.0 parses `payload[3]` for major carriers (DL, AA, WN, UA, F9)
3. A deep-scan recursive walker searches `payload[2]` for Allegiant leg entries
4. Results are merged, deduplicated, and sorted by price

G4 flights are found inside `price_data[0]` as 25-element arrays where `leg[9]` is the price — a structure that differs completely from how other carriers store their data.

## Allegiant Notes

- Only serves select routes (TYS, ATL, and a few other hubs)
- Typically the cheapest option when present
- Does not appear on international routes

## Dependencies

- [fast-flights](https://github.com/AWeirdDev/flights) >= 3.0
- selectolax >= 0.3.20
