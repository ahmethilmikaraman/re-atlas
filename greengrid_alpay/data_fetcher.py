"""
GreenGrid — Veri Katmanı (data_fetcher.py) v6
==============================================
v6 değişiklikleri:
  - water.status: "ok" / "failed" / "not_found" ayrımı
    (API fail ≠ su yok — bu kritik fark)
  - confidence: water status'a göre daha doğru hesap
"""

import requests
import numpy as np
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# ──────────────────────────────────────────────
# API Adresleri
# ──────────────────────────────────────────────
NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"
OPEN_TOPO_URL  = "https://api.opentopodata.org/v1/srtm90m"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OVERPASS_URL   = "https://overpass-api.de/api/interpreter"

NASA_PARAMS = "ALLSKY_SFC_SW_DWN,WS10M,WS50M,T2M,RH2M,PRECTOTCORR"
AYLAR = ["JAN","FEB","MAR","APR","MAY","JUN",
         "JUL","AUG","SEP","OCT","NOV","DEC"]


def safe_request(method, url, max_retries=3, retry_delay=2, **kwargs):
    kwargs.setdefault("timeout", 30)
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, **kwargs) if method == "GET" else requests.post(url, **kwargs)
            r.raise_for_status()
            return r
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(retry_delay)
        except requests.exceptions.HTTPError as e:
            if r.status_code < 500:
                raise
            last_error = e
            if attempt < max_retries:
                time.sleep(retry_delay)
    raise last_error


def _safe_val(val, fallback=0.0):
    if val is None or val == -999.0 or val == -999:
        return fallback
    try:
        v = float(val)
        return fallback if (np.isnan(v) or np.isinf(v)) else v
    except (TypeError, ValueError):
        return fallback


# ── 1. NASA POWER ──
@lru_cache(maxsize=256)
def fetch_nasa_power(lat, lon):
    r = safe_request("GET", NASA_POWER_URL, params={
        "parameters": NASA_PARAMS, "community": "RE",
        "longitude": lon, "latitude": lat, "format": "JSON",
    }, timeout=30)
    data = r.json()["properties"]["parameter"]
    def monthly(key):
        return [_safe_val(data[key].get(m, -999)) for m in AYLAR]
    return {
        "ghi_kwh_m2_day": _safe_val(data["ALLSKY_SFC_SW_DWN"]["ANN"]),
        "wind_10m_ms":    _safe_val(data["WS10M"]["ANN"]),
        "wind_50m_ms":    _safe_val(data["WS50M"]["ANN"]),
        "temp_c":         _safe_val(data["T2M"]["ANN"], 15.0),
        "humidity_pct":   _safe_val(data["RH2M"]["ANN"], 50.0),
        "precip_mm_day":  _safe_val(data["PRECTOTCORR"]["ANN"]),
        "monthly_ghi":    monthly("ALLSKY_SFC_SW_DWN"),
        "monthly_wind":   monthly("WS50M"),
    }


# ── 2. OpenTopoData ──
@lru_cache(maxsize=512)
def fetch_elevation(lat, lon):
    r = safe_request("GET", OPEN_TOPO_URL, params={
        "locations": f"{lat},{lon}"}, timeout=10)
    data = r.json()
    if data.get("status") != "OK" or not data.get("results"):
        raise ValueError(f"OpenTopoData hatası: {data}")
    elev = data["results"][0]["elevation"]
    return float(elev) if elev is not None else 0.0


# ── 3. Eğim (batch) ──
def fetch_slope(lat, lon, dist_m=200):
    d_lat = dist_m / 111_000
    d_lon = dist_m / (111_000 * np.cos(np.radians(lat)))
    points = [
        (round(lat, 6), round(lon, 6)),
        (round(lat + d_lat, 6), round(lon, 6)),
        (round(lat - d_lat, 6), round(lon, 6)),
        (round(lat, 6), round(lon + d_lon, 6)),
        (round(lat, 6), round(lon - d_lon, 6)),
    ]
    locations = "|".join(f"{la},{lo}" for la, lo in points)
    try:
        r = safe_request("GET", OPEN_TOPO_URL,
                         params={"locations": locations}, timeout=15)
        data = r.json()
        if data.get("status") != "OK":
            return 0.0
        elevs = [float(res["elevation"]) if res.get("elevation") is not None
                 else None for res in data["results"]]
    except Exception:
        return 0.0

    center = elevs[0]
    neighbors = [e for e in elevs[1:] if e is not None]
    if center is None or not neighbors:
        return 0.0
    max_diff = max(abs(e - center) for e in neighbors)
    return round(np.degrees(np.arctan(max_diff / dist_m)), 2)


# ── 4. Rüzgar tutarlılığı ──
def fetch_wind_consistency(lat, lon):
    r = safe_request("GET", OPEN_METEO_URL, params={
        "latitude": lat, "longitude": lon,
        "hourly": "wind_speed_10m", "forecast_days": 7,
    }, timeout=15)
    speeds = np.array(r.json()["hourly"]["wind_speed_10m"], dtype=float)
    speeds = speeds[~np.isnan(speeds)]
    if len(speeds) == 0 or speeds.mean() == 0:
        return 1.0
    return round(float(speeds.std() / speeds.mean()), 3)


# ── 5. Overpass — hızlı fail + status ayrımı ──
def fetch_water_proximity(lat, lon, radius_km=10):
    """
    Dönüş:
      status: "ok" (API çalıştı, sonuç var/yok)
              "failed" (API çağrısı başarısız)
      has_water: True/False (sadece status=ok ise anlamlı)
    """
    radius_m = radius_km * 1000
    query = (
        f'[out:json][timeout:8];'
        f'(way(around:{radius_m},{lat},{lon})["waterway"="river"];'
        f'way(around:{radius_m},{lat},{lon})["natural"="water"];);'
        f'out center 5;'
    )
    try:
        r = safe_request("GET", OVERPASS_URL,
                         params={"data": query},
                         headers={"User-Agent": "GreenGrid/1.0",
                                  "Accept": "application/json"},
                         max_retries=1, timeout=8)
        elements = r.json().get("elements", [])

        if not elements:
            # API çalıştı ama su bulamadı → gerçekten su yok
            return {"status": "ok", "has_water": False,
                    "distance_km": None, "type": None}

        def dist(el):
            c = el.get("center", {})
            if not c:
                return float("inf")
            dlat = (c["lat"] - lat) * 111
            dlon = (c["lon"] - lon) * 111 * np.cos(np.radians(lat))
            return np.sqrt(dlat**2 + dlon**2)

        nearest = min(elements, key=dist)
        water_type = (nearest.get("tags", {}).get("waterway")
                      or nearest.get("tags", {}).get("natural", "water"))
        return {
            "status": "ok", "has_water": True,
            "distance_km": round(dist(nearest), 2),
            "type": water_type,
        }

    except Exception:
        # API fail → bilmiyoruz, "su yok" dememeliyiz
        return {"status": "failed", "has_water": False,
                "distance_km": None, "type": None}


# ── 6. Akış tahmini ──
def estimate_flow_potential(precip_mm_day, slope_deg, elevation_m):
    """
    Akış tahmini — ama çok temkinli.
    Bu sadece bir İPUCU, su doğrulaması DEĞİL.

    Tetiklenme eşikleri yükseltildi:
      - Yağış: 2.5+ mm/gün gerekli (1.5'ten yükseltildi)
      - Eğim: 10°+ gerekli (5°'den yükseltildi)
      - has_flow eşiği: 45+ (30'dan yükseltildi)
    """
    # Minimum yağış — 2.5 mm altı kesinlikle yetersiz
    if precip_mm_day < 2.5:
        return {"flow_score": 0, "has_estimated_flow": False,
                "reason": "Yetersiz yağış — yüzey akışı beklenmez"}

    # Minimum eğim — düz arazide su toplanmaz, akmaz
    if slope_deg < 8:
        return {"flow_score": 0, "has_estimated_flow": False,
                "reason": "Yetersiz eğim — su akışı için dik arazi gerekli"}

    # Katkılar (daha sıkı çarpanlar)
    rain_contrib = min(40, (precip_mm_day - 2.5) * 10)    # eski: (p-1.5)*14.3
    slope_contrib = min(35, max(0, (slope_deg - 10) * 2.5))  # eski: (s-5)*3
    elev_contrib = min(15, elevation_m / 80)               # eski: elev/50

    flow_score = rain_contrib + slope_contrib + elev_contrib

    # Eşik yükseltildi: 45 (eski: 30)
    has_flow = flow_score >= 45

    if has_flow:
        reason = (f"Yağış ({precip_mm_day:.1f} mm/gün) + eğim ({slope_deg:.0f}°) "
                  f"+ rakım ({elevation_m:.0f} m) → akış potansiyeli olabilir")
    else:
        reason = "Akış potansiyeli düşük"

    return {"flow_score": round(flow_score, 1),
            "has_estimated_flow": has_flow, "reason": reason}


# ── 7. Confidence ──
def calculate_confidence(features):
    score = 0.0
    # NASA (%50)
    if features["ghi_kwh_m2_day"] > 0 or features["wind_50m_ms"] > 0:
        score += 0.50
    # Yükseklik (%15)
    if features["elevation_m"] is not None:
        score += 0.15
    # Rüzgar CV (%10)
    if features["wind_cv"] < 1.0:
        score += 0.10
    # Su bilgisi (%15) — status'a göre farklı
    water_status = features["water"].get("status", "failed")
    if water_status == "ok" and features["water"]["has_water"]:
        score += 0.15  # su doğrulandı — tam puan
    elif water_status == "ok" and not features["water"]["has_water"]:
        score += 0.12  # API çalıştı, su yok — neredeyse tam
    elif water_status == "failed":
        score += 0.03  # API fail — bilmiyoruz
    # Akış tahmini (%10)
    if features["flow"].get("has_estimated_flow"):
        score += 0.10
    return round(min(1.0, score), 2)


# ── 8. Hepsini Bir Arada — PARALEL ──
def gather_all(lat, lon):
    print(f"\n📡 Veri toplanıyor: ({lat:.4f}, {lon:.4f})")
    results = {}

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(fetch_nasa_power, lat, lon): "nasa",
            executor.submit(fetch_elevation, lat, lon): "elevation",
            executor.submit(fetch_slope, lat, lon): "slope",
            executor.submit(fetch_wind_consistency, lat, lon): "wind_cv",
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
                label = {"nasa":"☀️ NASA","elevation":"🏔️ Yükseklik",
                         "slope":"📐 Eğim","wind_cv":"💨 Rüzgar"}[key]
                print(f"  {label} ✓")
            except Exception as e:
                print(f"  ❌ {key}: {e}")
                defaults = {"nasa": {"ghi_kwh_m2_day":0,"wind_10m_ms":0,
                    "wind_50m_ms":0,"temp_c":15,"humidity_pct":50,
                    "precip_mm_day":0,"monthly_ghi":[0]*12,"monthly_wind":[0]*12},
                    "elevation": 0.0, "slope": 0.0, "wind_cv": 1.0}
                results[key] = defaults[key]

    print("  💧 Su kaynağı...")
    water = fetch_water_proximity(lat, lon)
    status_label = {"ok":"✓","failed":"✗ (fallback aktif)"}
    print(f"  💧 {status_label.get(water['status'],'?')} "
          f"{'su bulundu' if water['has_water'] else 'su bulunamadı'}")

    nasa = results["nasa"]
    flow = estimate_flow_potential(nasa["precip_mm_day"],
                                  results["slope"], results["elevation"])

    features = {
        "lat": lat, "lon": lon, **nasa,
        "elevation_m": results["elevation"],
        "slope_deg": results["slope"],
        "wind_cv": results["wind_cv"],
        "water": water, "flow": flow,
    }
    features["confidence"] = calculate_confidence(features)
    print(f"  📊 Confidence: {features['confidence']}")
    print("  ✅ Tamamlandı!")
    return features


if __name__ == "__main__":
    import json
    for name, lat, lon in [
        ("Konya",37.87,32.49),("Çanakkale",40.18,26.40),("Rize",40.95,40.80)]:
        print(f"\n{'='*50}\n  {name} ({lat}, {lon})\n{'='*50}")
        try:
            f = gather_all(lat, lon)
            print(json.dumps(f, indent=2, ensure_ascii=False, default=str))
        except Exception as e:
            print(f"  ❌ {e}")