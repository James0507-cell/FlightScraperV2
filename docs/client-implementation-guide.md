# Client Implementation Guide: Search Feature

This guide explains how to implement the flight search feature in your trip planning application using the FlightScraperV2 API.

## Architecture Overview

The scraper provides a **session-based API** designed specifically for interactive trip planning applications:

```
User searches → Create session → Get offers → User clicks flight → Get details
```

The session approach avoids re-running the full browser search every time a user clicks a flight card.

## API Base URL

```
http://<your-server>:8000
```

All examples below use `http://localhost:8000` for local development.

---

## Step-by-Step Implementation

### Step 1: User Enters Search Criteria

Your application collects:
- Origin airport code (e.g., `DVO`)
- Destination airport code (e.g., `MNL`)
- Departure date (e.g., `2026-07-02`)
- Return date (optional - if provided, it's a round-trip search)
- Passengers (optional, default: 1)
- Cabin class (optional, default: `economy`)

### Step 2: Create a Search Session

When the user clicks "Search", create a session:

```http
POST /api/v1/sessions
Content-Type: application/json

{
  "origin": "DVO",
  "destination": "MNL",
  "depart_date": "2026-07-02",
  "return_date": "2026-07-08",
  "passengers": 1,
  "cabin": "economy",
  "session_ttl": 600
}
```

**Response:**

```json
{
  "session_id": "a1b2c3d4e5f6",
  "origin": "DVO",
  "destination": "MNL",
  "depart_date": "2026-07-02",
  "return_date": "2026-07-08",
  "offer_count": 27,
  "offers": [
    {
      "origin_airport": "DVO",
      "destination_airport": "MNL",
      "departure_date": "2026-07-02",
      "departure_time": "2026-07-02T11:30:00",
      "arrival_time": "2026-07-02T13:35:00",
      "duration_minutes": 125,
      "stops": 0,
      "price": 3001,
      "currency": "PHP",
      "airlines": ["Cebu Pacific"],
      "flight_numbers": ["964"],
      "emissions_kg": 72,
      "is_best": true
    }
  ],
  "expires_at": "2026-05-21T14:10:00+00:00"
}
```

**Store the `session_id`** - you'll need it for all subsequent requests.

### Step 3: Display Flight Results

Render the `offers` array as flight cards in your UI. Each offer contains:

| Field | Description |
|-------|-------------|
| `origin_airport` | Departure airport code |
| `destination_airport` | Arrival airport code |
| `departure_time` | ISO 8601 departure datetime |
| `arrival_time` | ISO 8601 arrival datetime |
| `duration_minutes` | Flight duration in minutes |
| `stops` | Number of stops (0 = direct) |
| `price` | Price in smallest currency unit (e.g., cents/pesos) |
| `currency` | Currency code (e.g., `PHP`) |
| `airlines` | Array of airline names |
| `flight_numbers` | Array of flight numbers |
| `is_best` | Whether Google marks this as the best option |

### Step 4: User Clicks a Flight Card

When the user clicks a flight card, call the details endpoint with the offer's index:

#### One-Way Flight

```http
POST /api/v1/sessions/{session_id}/details
Content-Type: application/json

{
  "offer_index": 0
}
```

**Response:**

```json
{
  "selected_outbound_offer": { ... },
  "return_offers": [],
  "selected_itinerary": { ... },
  "booking_options": [
    {
      "provider_code": "5J",
      "provider_name": "Cebu Pacific",
      "provider_display_domain": "www.cebupacificair.com",
      "price": 3001,
      "currency": "PHP",
      "deeplink_url": "https://...",
      "fare_name": "Economy"
    }
  ],
  "booking_option_count": 1,
  "return_offer_count": 0,
  "notes": ["selected offer expanded into booking options"],
  "timings": {
    "total_seconds": 34.24,
    "session_age_seconds": 45.0
  }
}
```

#### Round-Trip: Get Return Flight Options

First, get the return flight options (without selecting one):

```http
POST /api/v1/sessions/{session_id}/details
Content-Type: application/json

{
  "offer_index": 0
}
```

**Response:**

```json
{
  "selected_outbound_offer": { ... },
  "return_offers": [
    {
      "origin_airport": "MNL",
      "destination_airport": "DVO",
      "departure_date": "2026-07-08",
      "departure_time": "2026-07-08T08:00:00",
      "arrival_time": "2026-07-08T10:00:00",
      "duration_minutes": 120,
      "stops": 0,
      "price": 3001,
      "airlines": ["Cebu Pacific"],
      "flight_numbers": ["965"]
    }
  ],
  "selected_itinerary": null,
  "booking_options": [],
  "booking_option_count": 0,
  "return_offer_count": 16,
  "notes": ["selected outbound offer expanded into return-flight choices"]
}
```

#### Round-Trip: Select Return Flight + Get Booking Options

Once the user selects a return flight:

```http
POST /api/v1/sessions/{session_id}/details
Content-Type: application/json

{
  "offer_index": 0,
  "return_offer_index": 0
}
```

**Response:**

```json
{
  "selected_outbound_offer": { ... },
  "return_offers": [ ... ],
  "selected_itinerary": {
    "origin_airport": "DVO",
    "destination_airport": "MNL",
    "return_origin_airport": "MNL",
    "return_destination_airport": "DVO",
    "price": 6002,
    "segments": [ ... ],
    "return_segments": [ ... ]
  },
  "booking_options": [ ... ],
  "booking_option_count": 1,
  "return_offer_count": 16,
  "notes": [
    "selected outbound offer expanded into return-flight choices",
    "selected return offer 0 expanded into booking options"
  ]
}
```

### Step 5: Display Booking Options

The `booking_options` array contains provider booking links:

| Field | Description |
|-------|-------------|
| `provider_name` | Airline or booking site name |
| `provider_display_domain` | Display domain for the provider |
| `price` | Price for this booking option |
| `currency` | Currency code |
| `deeplink_url` | Google deeplink URL |
| `fare_name` | Fare class name |
| `resolved_booking_url` | Resolved booking URL (may be null) |

---

## Code Examples

### JavaScript / TypeScript (Fetch API)

```typescript
interface FlightOffer {
  origin_airport: string;
  destination_airport: string;
  departure_time: string;
  arrival_time: string;
  duration_minutes: number;
  stops: number;
  price: number;
  currency: string;
  airlines: string[];
  flight_numbers: string[];
}

interface SessionResponse {
  session_id: string;
  offer_count: number;
  offers: FlightOffer[];
  expires_at: string;
}

interface OfferDetailsResponse {
  selected_outbound_offer: FlightOffer;
  return_offers: FlightOffer[];
  selected_itinerary: FlightOffer | null;
  booking_options: BookingOption[];
  booking_option_count: number;
  return_offer_count: number;
}

const BASE_URL = 'http://localhost:8000';

// Step 1: Create session
async function searchFlights(params: {
  origin: string;
  destination: string;
  depart_date: string;
  return_date?: string;
}): Promise<SessionResponse> {
  const response = await fetch(`${BASE_URL}/api/v1/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  return response.json();
}

// Step 2: Get offer details (one-way)
async function getOfferDetails(
  sessionId: string,
  offerIndex: number
): Promise<OfferDetailsResponse> {
  const response = await fetch(
    `${BASE_URL}/api/v1/sessions/${sessionId}/details`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ offer_index: offerIndex }),
    }
  );
  return response.json();
}

// Step 3: Get return flight options (round-trip)
async function getReturnOptions(
  sessionId: string,
  offerIndex: number
): Promise<OfferDetailsResponse> {
  const response = await fetch(
    `${BASE_URL}/api/v1/sessions/${sessionId}/details`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ offer_index: offerIndex }),
    }
  );
  return response.json();
}

// Step 4: Get booking options (round-trip with return selected)
async function getBookingOptions(
  sessionId: string,
  offerIndex: number,
  returnOfferIndex: number
): Promise<OfferDetailsResponse> {
  const response = await fetch(
    `${BASE_URL}/api/v1/sessions/${sessionId}/details`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        offer_index: offerIndex,
        return_offer_index: returnOfferIndex,
      }),
    }
  );
  return response.json();
}

// Step 5: Clean up session
async function deleteSession(sessionId: string): Promise<void> {
  await fetch(`${BASE_URL}/api/v1/sessions/${sessionId}`, {
    method: 'DELETE',
  });
}
```

### React Component Example

```tsx
import { useState } from 'react';

const BASE_URL = 'http://localhost:8000';

function FlightSearch() {
  const [offers, setOffers] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSearch = async (searchParams) => {
    setLoading(true);
    try {
      const response = await fetch(`${BASE_URL}/api/v1/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(searchParams),
      });
      const data = await response.json();
      setSessionId(data.session_id);
      setOffers(data.offers);
    } finally {
      setLoading(false);
    }
  };

  const handleOfferClick = async (offerIndex) => {
    setLoading(true);
    try {
      const response = await fetch(
        `${BASE_URL}/api/v1/sessions/${sessionId}/details`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ offer_index: offerIndex }),
        }
      );
      const data = await response.json();
      setDetails(data);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {/* Search form */}
      {/* Flight cards */}
      {/* Details modal */}
    </div>
  );
}
```

### Python Example (httpx)

```python
import httpx

BASE_URL = "http://localhost:8000"

def search_flights(origin, destination, depart_date, return_date=None):
    """Create a search session and return offers."""
    payload = {
        "origin": origin,
        "destination": destination,
        "depart_date": depart_date,
    }
    if return_date:
        payload["return_date"] = return_date

    with httpx.Client(timeout=120.0) as client:
        response = client.post(f"{BASE_URL}/api/v1/sessions", json=payload)
        return response.json()

def get_offer_details(session_id, offer_index, return_offer_index=None):
    """Get details for a specific offer."""
    payload = {"offer_index": offer_index}
    if return_offer_index is not None:
        payload["return_offer_index"] = return_offer_index

    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            f"{BASE_URL}/api/v1/sessions/{session_id}/details",
            json=payload,
        )
        return response.json()

def delete_session(session_id):
    """Clean up a session."""
    with httpx.Client() as client:
        client.delete(f"{BASE_URL}/api/v1/sessions/{session_id}")

# Example usage
session = search_flights("DVO", "MNL", "2026-07-02", "2026-07-08")
print(f"Found {session['offer_count']} offers")

details = get_offer_details(session["session_id"], 0)
print(f"Booking options: {details['booking_option_count']}")

delete_session(session["session_id"])
```

---

## Important Notes

### Session Lifetime

- Sessions expire after `session_ttl` seconds (default: 600 = 10 minutes)
- Expired sessions return `404 Not Found`
- Clean up sessions when the user navigates away or completes booking
- The server automatically cleans up expired sessions every 60 seconds

### Performance Expectations

| Operation | Expected Time |
|-----------|---------------|
| Create session | 5-10 seconds |
| Get offer details | 30-40 seconds |
| Get return options | 30-40 seconds |
| Get booking options | 30-50 seconds |
| Delete session | < 1 second |

### Error Handling

| Status Code | Meaning | Action |
|-------------|---------|--------|
| `200` | Success | Process response |
| `404` | Session not found or expired | Create new session |
| `500` | Server error | Retry or show error |
| `503` | Service unavailable | Wait and retry |

### Best Practices

1. **Create session once per search** - Don't create multiple sessions for the same search
2. **Store session_id in state** - Keep it in your app state or URL params
3. **Clean up sessions** - Call `DELETE /api/v1/sessions/{id}` when done
4. **Handle session expiry** - If you get a 404, create a new session
5. **Show loading states** - Detail requests take 30-50 seconds
6. **Cache details locally** - Don't re-fetch details the user already viewed
7. **Use the legacy endpoints only for non-interactive use** - Session API is faster for browsing

---

## Flow Diagrams

### One-Way Flow

```
User enters search
    ↓
POST /api/v1/sessions → session_id + offers[]
    ↓
Display flight cards
    ↓
User clicks flight card
    ↓
POST /api/v1/sessions/{id}/details → booking_options[]
    ↓
Display booking options
    ↓
User clicks "Book" → redirect to provider
    ↓
DELETE /api/v1/sessions/{id} (cleanup)
```

### Round-Trip Flow

```
User enters search (with return date)
    ↓
POST /api/v1/sessions → session_id + offers[]
    ↓
Display outbound flight cards
    ↓
User clicks outbound flight
    ↓
POST /api/v1/sessions/{id}/details → return_offers[]
    ↓
Display return flight cards
    ↓
User clicks return flight
    ↓
POST /api/v1/sessions/{id}/details → booking_options[]
    ↓
Display booking options
    ↓
User clicks "Book" → redirect to provider
    ↓
DELETE /api/v1/sessions/{id} (cleanup)
```

---

## Legacy API (Not Recommended for Interactive Apps)

The legacy endpoints (`/api/v1/scrape` and `/api/v1/scrape/details`) still work but each call triggers a full browser search (~35 seconds). Use the session-based API for interactive applications.

See `api-reference.md` for legacy endpoint documentation.
