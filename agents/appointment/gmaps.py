import os
import httpx

_TIMEOUT = 5.0


def get_travel_time(origin: str, destination: str) -> dict | None:
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("WARNING: GOOGLE_MAPS_API_KEY not set")
        return None
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {"origins": origin, "destinations": destination, "key": api_key}
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None
