import os, requests, time
from dotenv import load_dotenv

load_dotenv(r"D:\AI\.env")

class WeatherService:
    BASE_URL = "http://api.weatherapi.com/v1/current.json"

    def __init__(self):
        self.api_key = os.getenv("WEATHER_API_KEY", "")
        self.city = os.getenv("WEATHER_CITY", "Ho Chi Minh City")
        self.CACHE_TTL = int(os.getenv("WEATHER_UPDATE_INTERVAL", "600"))
        self._cache = None
        self._cache_time = 0

    def get_current(self) -> dict | None:
        """Fetch current weather, returns sensor-compatible dict or None on error."""
        now = time.time()
        if self._cache and (now - self._cache_time) < self.CACHE_TTL:
            return self._cache

        if not self.api_key:
            print("⚠️ WEATHER_API_KEY not set")
            return None

        try:
            resp = requests.get(
                self.BASE_URL,
                params={"key": self.api_key, "q": self.city, "aqi": "no"},
                timeout=5
            )
            resp.raise_for_status()
            data = resp.json()
            current = data["current"]
            location = data["location"]

            uv = float(current.get("uv", 0))
            cloud = float(current.get("cloud", 0))
            is_day = int(current.get("is_day", 1))

            # Estimate lux: clear sky daylight ~100,000 lux; UV index ~11 at peak
            # lux ≈ uv/11 * 100000 * (1 - cloud/100)
            if is_day:
                lux = round((uv / 11) * 100_000 * (1 - cloud / 100))
            else:
                lux = 0

            result = {
                "temperature": round(float(current["temp_c"]), 1),
                "humidity":    round(float(current["humidity"]), 1),
                "light":       lux,
                # extra weather metadata
                "uv":          uv,
                "cloud":       cloud,
                "condition":   current["condition"]["text"],
                "icon":        "https:" + current["condition"]["icon"],
                "city":        location["name"],
                "country":     location["country"],
                "wind_kph":    current.get("wind_kph", 0),
                "feelslike_c": current.get("feelslike_c", current["temp_c"]),
                "is_day":      is_day,
            }

            self._cache = result
            self._cache_time = now
            print(f"🌤️ Weather updated: {result['city']} {result['temperature']}°C "
                  f"{result['humidity']}% {result['light']} lux")
            return result

        except requests.RequestException as e:
            print(f"❌ WeatherAPI request error: {e}")
            return None
        except (KeyError, ValueError) as e:
            print(f"❌ WeatherAPI parse error: {e}")
            return None

    def invalidate_cache(self):
        self._cache = None
        self._cache_time = 0


# Singleton
_weather_instance = None

def get_weather_service() -> WeatherService:
    global _weather_instance
    if not _weather_instance:
        _weather_instance = WeatherService()
    return _weather_instance
