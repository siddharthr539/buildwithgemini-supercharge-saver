import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from google.cloud import firestore

# Hardcoded project ID as string to prevent issues on Agent Platform
PROJECT_ID = "qwiklabs-gcp-04-4c737e884f18"

_db: Optional[firestore.Client] = None

def get_db() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client(project=PROJECT_ID)
    return _db

def list_superchargers(city: Optional[str] = None) -> List[Dict[str, Any]]:
    """List Tesla Supercharger stations from Firestore, optionally filtered by city.

    Args:
        city: Optional city name to filter stations by (e.g. 'San Francisco', 'Concord', 'Oakland').

    Returns:
        A list of matching Supercharger station documents with their specs and pricing.
    """
    db = get_db()
    stations_ref = db.collection("supercharger_stations")
    
    results = []
    for doc in stations_ref.stream():
        data = doc.to_dict()
        if city:
            if city.lower() in data.get("city", "").lower() or city.lower() in data.get("name", "").lower():
                results.append(data)
        else:
            results.append(data)
            
    return results

def get_cheapest_supercharger(location_query: str) -> Dict[str, Any]:
    """Finds the lowest cost Supercharger station near a city/query based on current time-of-day rates.

    Args:
        location_query: The city or area name (e.g. 'San Francisco', 'Bay Area', 'Concord').

    Returns:
        The best matching Supercharger station with current active rate and off-peak rate details.
    """
    stations = list_superchargers(city=location_query if location_query.lower() != "bay area" else None)
    if not stations:
        return {"error": f"No stations found matching '{location_query}'."}

    # Determine current Pacific Time hour
    pt_now = datetime.datetime.now(ZoneInfo("America/Los_Angeles"))
    current_hour = pt_now.hour

    # Evaluate current rate tier for each station
    scored_stations = []
    for s in stations:
        rates = s.get("rates", {})
        # Off-peak is typically 10/11 PM to 7/8 AM
        if current_hour >= 23 or current_hour < 7:
            active_rate = rates.get("off_peak", 0.22)
            tier_name = "off_peak"
        elif 12 <= current_hour < 19:
            active_rate = rates.get("peak", 0.50)
            tier_name = "peak"
        else:
            active_rate = rates.get("mid_peak", 0.35)
            tier_name = "mid_peak"

        scored_stations.append({
            "station": s["name"],
            "city": s["city"],
            "address": s.get("address", ""),
            "speed_kw": s.get("speed_kw", 250),
            "stalls": s.get("stalls", 0),
            "current_rate_per_kwh": f"${active_rate:.2f}",
            "current_tier": tier_name,
            "off_peak_rate": f"${rates.get('off_peak', 0.22):.2f}",
            "off_peak_hours": s.get("off_peak_hours", "10:00 PM - 8:00 AM"),
            "raw_rate": active_rate
        })

    # Sort by cheapest active rate
    scored_stations.sort(key=lambda x: x["raw_rate"])
    cheapest = scored_stations[0]
    return {
        "current_time_pt": pt_now.strftime("%I:%M %p %Z"),
        "best_station": cheapest,
        "all_ranked_stations": scored_stations
    }

def record_charging_session(
    station_name: str,
    kwh_charged: float,
    total_cost_dollars: float,
    vehicle_model: str = "Tesla Model Y"
) -> Dict[str, Any]:
    """Records a completed or planned charging session into the Firestore database.

    Args:
        station_name: Name of the Supercharger station used.
        kwh_charged: Total kilowatt-hours added (e.g. 45.5).
        total_cost_dollars: Total cost in USD (e.g. 11.20).
        vehicle_model: Model of the vehicle charged.

    Returns:
        Confirmation details of the recorded charging session.
    """
    db = get_db()
    sessions_ref = db.collection("charging_sessions")
    now = datetime.datetime.now(ZoneInfo("America/Los_Angeles"))
    
    session_data = {
        "station_name": station_name,
        "kwh_charged": kwh_charged,
        "total_cost_dollars": total_cost_dollars,
        "vehicle_model": vehicle_model,
        "timestamp": now.isoformat(),
        "created_at": firestore.SERVER_TIMESTAMP
    }
    
    doc_ref = sessions_ref.document()
    doc_ref.set(session_data)
    
    return {
        "status": "success",
        "session_id": doc_ref.id,
        "recorded": {
            "station": station_name,
            "kwh": kwh_charged,
            "cost": f"${total_cost_dollars:.2f}",
            "time": now.strftime("%Y-%m-%d %I:%M %p %Z")
        }
    }

def get_current_location() -> Dict[str, Any]:
    """Resolves the current GPS coordinates and city of the user/vehicle.

    Returns:
        A dictionary containing latitude, longitude, and detected city.
    """
    # Defaults to San Francisco Financial District / Bay Area for testing simulation
    return {
        "city": "San Francisco",
        "state": "CA",
        "latitude": 37.7897,
        "longitude": -122.4014,
        "location_name": "Market & 3rd St, San Francisco, CA"
    }

def estimate_charging_cost(
    station_name: str,
    current_battery_pct: float,
    target_battery_pct: float = 80.0,
    battery_capacity_kwh: float = 75.0
) -> Dict[str, Any]:
    """Calculates required energy and estimated cost to charge to target percentage at a station.

    Args:
        station_name: The name or city of the Supercharger station.
        current_battery_pct: Current vehicle battery level (0-100), e.g. 15.0.
        target_battery_pct: Target battery level (default 80.0).
        battery_capacity_kwh: Vehicle battery pack size in kWh (default 75.0 for Model Y/3 Long Range).

    Returns:
        Detailed calculation of required kWh, charging duration, and estimated cost across tiers.
    """
    if current_battery_pct >= target_battery_pct:
        return {"error": f"Current battery ({current_battery_pct}%) is already at or above target ({target_battery_pct}%)."}

    kwh_needed = ((target_battery_pct - current_battery_pct) / 100.0) * battery_capacity_kwh
    
    # Lookup station
    stations = list_superchargers(city=station_name)
    if not stations:
        # Default fallback rates if station not found
        off_peak_rate, mid_peak_rate, peak_rate = 0.22, 0.35, 0.50
        matched_station = station_name
        speed_kw = 250
    else:
        st = stations[0]
        matched_station = st.get("name", station_name)
        rates = st.get("rates", {})
        off_peak_rate = rates.get("off_peak", 0.22)
        mid_peak_rate = rates.get("mid_peak", 0.35)
        peak_rate = rates.get("peak", 0.50)
        speed_kw = st.get("speed_kw", 250)

    # Estimate minutes on DC fast charging taper (rough average 120kW average rate on 250kW stall up to 80%)
    est_minutes = round((kwh_needed / min(speed_kw * 0.55, 130)) * 60)

    return {
        "station": matched_station,
        "battery_range": f"{current_battery_pct}% -> {target_battery_pct}%",
        "energy_needed_kwh": round(kwh_needed, 1),
        "estimated_duration_minutes": max(est_minutes, 15),
        "cost_by_tier": {
            "off_peak": f"${(kwh_needed * off_peak_rate):.2f} (@ ${off_peak_rate:.2f}/kWh)",
            "mid_peak": f"${(kwh_needed * mid_peak_rate):.2f} (@ ${mid_peak_rate:.2f}/kWh)",
            "peak": f"${(kwh_needed * peak_rate):.2f} (@ ${peak_rate:.2f}/kWh)"
        },
        "potential_savings_waiting_for_off_peak": f"${((peak_rate - off_peak_rate) * kwh_needed):.2f}"
    }

def get_battery_weather_impact(latitude: float = 37.7749, longitude: float = -122.4194) -> Dict[str, Any]:
    """Fetches real-time ambient weather from the Open-Meteo public API to calculate battery preconditioning and range impact.

    Args:
        latitude: Latitude of the station or vehicle (default 37.7749 for SF).
        longitude: Longitude of the station or vehicle (default -122.4194 for SF).

    Returns:
        Live ambient temperature, conditions, and estimated battery preconditioning/efficiency impact.
    """
    import urllib.request
    import json

    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={latitude}&longitude={longitude}&"
        f"current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,wind_speed_10m&"
        f"temperature_unit=fahrenheit"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SuperchargeSaver/1.0"})
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode())
            current = data.get("current", {})
            temp_f = current.get("temperature_2m", 68.0)
            wind_mph = current.get("wind_speed_10m", 0.0)

            # EV Lithium-ion battery impact assessment:
            # Below 50F or above 90F increases preconditioning time or HVAC draw
            if temp_f < 45.0:
                preconditioning_advice = "Cold ambient temp: Expect 15-20 min of active preconditioning for peak 250kW charging speed."
                efficiency_rating = "Reduced (~15% higher consumption due to cabin/battery heating)."
            elif temp_f > 85.0:
                preconditioning_advice = "Warm ambient temp: Minimal preconditioning needed, battery cooling system will activate during fast charge."
                efficiency_rating = "Normal to slightly reduced (~5% higher consumption due to AC)."
            else:
                preconditioning_advice = "Optimal ambient temp (55°F - 80°F): Battery will reach peak charging speed quickly."
                efficiency_rating = "Optimal range efficiency."

            return {
                "source": "Open-Meteo Public API",
                "coordinates": f"{latitude}, {longitude}",
                "ambient_temperature": f"{temp_f}°F",
                "feels_like": f"{current.get('apparent_temperature', temp_f)}°F",
                "wind_speed": f"{wind_mph} mph",
                "battery_impact": efficiency_rating,
                "preconditioning_advice": preconditioning_advice
            }
    except Exception as e:
        return {
            "error": f"Failed to retrieve weather data: {str(e)}",
            "ambient_temperature": "68°F (estimated)",
            "preconditioning_advice": "Allow 10-15 minutes of navigation preconditioning before arriving at Supercharger."
        }

def geocode_address(address: str) -> Dict[str, Any]:
    """Uses the Google Maps Geocoding API to turn a street address or location name into geographic coordinates.

    Args:
        address: The address, place name, or intersection to geocode (e.g. '1455 Van Ness Ave, San Francisco, CA').

    Returns:
        A dictionary containing formatted address, latitude, and longitude.
    """
    import os
    import urllib.request
    import urllib.parse
    import json
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return {"error": "GOOGLE_MAPS_API_KEY environment variable is not configured."}

    encoded_addr = urllib.parse.quote(address)
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_addr}&key={api_key}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SuperchargeSaver/1.0"})
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode())
            if data.get("status") != "OK" or not data.get("results"):
                return {"error": f"Geocoding failed with status: {data.get('status')}"}

            first = data["results"][0]
            loc = first["geometry"]["location"]
            return {
                "address": first.get("formatted_address", address),
                "location": {
                    "latitude": loc["lat"],
                    "longitude": loc["lng"]
                }
            }
    except Exception as e:
        return {"error": f"Failed to geocode address: {str(e)}"}


def find_nearby_places(
    place_type: str,
    latitude: float,
    longitude: float,
    radius_meters: float = 1500.0,
    max_results: int = 5,
    min_rating: float = 4.8
) -> Dict[str, Any]:
    """Uses the Google Maps Places API (New) to search for nearby amenities (coffee shops, restaurants) near coordinates, strictly filtering for 5-star or highest rated spots.

    Args:
        place_type: Type of place to search for (e.g. 'coffee_shop', 'cafe', 'restaurant').
        latitude: Center latitude to search from (e.g. from a Supercharger location).
        longitude: Center longitude to search from.
        radius_meters: Search radius in meters (default 1500.0m / ~0.9 miles).
        max_results: Maximum places to return (default 5).
        min_rating: Minimum Google rating threshold (default 4.8 to surface 5-star and premier rated places).

    Returns:
        A list of nearby 5-star / top-rated places with their name, Google rating, review count, address, and coordinates.
    """
    import os
    import urllib.request
    import json
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return {"error": "GOOGLE_MAPS_API_KEY environment variable is not configured."}

    # Query Places API (New) searchNearby with rating and user reviews in field mask
    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.rating,places.userRatingCount"
    }

    body = json.dumps({
        "includedTypes": [place_type],
        "maxResultCount": 20,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": radius_meters
            }
        }
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode())
            places_raw = data.get("places", [])
            places_list = []
            for p in places_raw:
                rating = p.get("rating", 0.0)
                review_count = p.get("userRatingCount", 0)
                # Filter for 5-star or premier rating threshold
                if rating >= min_rating:
                    display_name = p.get("displayName", {}).get("text", "Unknown Place")
                    addr = p.get("formattedAddress", "")
                    loc = p.get("location", {})
                    places_list.append({
                        "name": display_name,
                        "rating": f"{rating} ★",
                        "numeric_rating": rating,
                        "reviews_count": review_count,
                        "address": addr,
                        "location": {
                            "latitude": loc.get("latitude"),
                            "longitude": loc.get("longitude")
                        }
                    })

            # Sort by rating descending, then review count descending
            places_list.sort(key=lambda x: (x["numeric_rating"], x["reviews_count"]), reverse=True)
            trimmed_places = places_list[:max_results]

            return {
                "place_type": place_type,
                "center": {"latitude": latitude, "longitude": longitude},
                "min_rating_filter": f"{min_rating}+ stars",
                "places_found": len(trimmed_places),
                "places": trimmed_places
            }
    except Exception as e:
        return {"error": f"Failed to search nearby places: {str(e)}"}
