"""
GreenGrid — Bölgesel Analiz Motoru (grid_analyzer.py) v2
========================================================
v2 değişiklikleri:
  - Smart insights: limiting factors + opportunity scores
  - Best zone detection: top %10 noktalar
  - Progressive rendering: düşük çözünürlükten yükseğe
  - Circle bounds desteği (lat,lon,radius_km → bounds)
"""

import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from data_fetcher import (
    fetch_nasa_power, safe_request, OPEN_TOPO_URL,
    estimate_flow_potential, _safe_val
)
from decision_engine import recommend


# ──────────────────────────────────────────────
# 1. Grid oluştur
# ──────────────────────────────────────────────
def generate_grid(bounds, resolution=5):
    lats = np.linspace(bounds["min_lat"], bounds["max_lat"], resolution)
    lons = np.linspace(bounds["min_lon"], bounds["max_lon"], resolution)
    points = []
    for i, lat in enumerate(lats):
        for j, lon in enumerate(lons):
            points.append({"lat": round(float(lat), 5),
                           "lon": round(float(lon), 5),
                           "row": i, "col": j})
    return points


def circle_to_bounds(lat, lon, radius_km):
    """Merkez + yarıçap → dikdörtgen bounds."""
    d_lat = radius_km / 111.0
    d_lon = radius_km / (111.0 * np.cos(np.radians(lat)))
    return {
        "min_lat": lat - d_lat, "max_lat": lat + d_lat,
        "min_lon": lon - d_lon, "max_lon": lon + d_lon,
    }


# ──────────────────────────────────────────────
# 2. Batch elevation
# ──────────────────────────────────────────────
def fetch_grid_elevations(points):
    chunk_size = 100
    all_elevs = []
    for i in range(0, len(points), chunk_size):
        chunk = points[i:i + chunk_size]
        locations = "|".join(f"{p['lat']},{p['lon']}" for p in chunk)
        try:
            r = safe_request("GET", OPEN_TOPO_URL,
                             params={"locations": locations},
                             max_retries=2, timeout=20)
            data = r.json()
            if data.get("status") == "OK" and data.get("results"):
                elevs = [float(res["elevation"]) if res.get("elevation") is not None
                         else 0.0 for res in data["results"]]
                all_elevs.extend(elevs)
            else:
                all_elevs.extend([0.0] * len(chunk))
        except Exception:
            all_elevs.extend([0.0] * len(chunk))
    return all_elevs


# ──────────────────────────────────────────────
# 3. Grid slope (API çağrısı yok)
# ──────────────────────────────────────────────
def calculate_grid_slopes(elevations, resolution, lat_step, lon_step):
    grid = np.array(elevations, dtype=float).reshape(resolution, resolution)
    slopes = np.zeros((resolution, resolution), dtype=float)
    dy = lat_step * 111_000
    dx = lon_step * 111_000 * 0.8
    for i in range(resolution):
        for j in range(resolution):
            diffs = []
            if i > 0: diffs.append(abs(grid[i, j] - grid[i - 1, j]) / dy)
            if i < resolution - 1: diffs.append(abs(grid[i, j] - grid[i + 1, j]) / dy)
            if j > 0: diffs.append(abs(grid[i, j] - grid[i, j - 1]) / dx)
            if j < resolution - 1: diffs.append(abs(grid[i, j] - grid[i, j + 1]) / dx)
            if diffs:
                slopes[i, j] = np.degrees(np.arctan(max(diffs)))
    return [round(float(s), 2) for s in slopes.flatten()]


# ──────────────────────────────────────────────
# 4. Hafif veri toplama (grid noktası)
# ──────────────────────────────────────────────
def gather_point_light(lat, lon, elevation, slope):
    try:
        nasa = fetch_nasa_power(lat, lon)
    except Exception:
        nasa = {"ghi_kwh_m2_day": 0, "wind_10m_ms": 0, "wind_50m_ms": 0,
                "temp_c": 15, "humidity_pct": 50, "precip_mm_day": 0,
                "monthly_ghi": [0] * 12, "monthly_wind": [0] * 12}

    flow = estimate_flow_potential(nasa["precip_mm_day"], slope, elevation)
    return {
        "lat": lat, "lon": lon, **nasa,
        "elevation_m": elevation, "slope_deg": slope,
        "wind_cv": 0.5, "confidence": 0.75,
        "water": {"status": "skipped", "has_water": False,
                  "distance_km": None, "type": None},
        "flow": flow,
    }


# ──────────────────────────────────────────────
# 5. Best zone detection (top %10)
# ──────────────────────────────────────────────
def detect_best_zones(results, top_pct=10):
    """Her enerji türü için en iyi %top_pct noktaları döner."""
    valid = [r for r in results if r["result"] is not None]
    if not valid:
        return {"Solar": [], "Wind": [], "Hydro": []}

    n_top = max(1, len(valid) * top_pct // 100)
    best_zones = {}

    for src in ["Solar", "Wind", "Hydro"]:
        sorted_pts = sorted(valid, key=lambda r: r["result"]["scores"][src], reverse=True)
        best_zones[src] = sorted_pts[:n_top]

    return best_zones


# ──────────────────────────────────────────────
# 6. Ana analiz fonksiyonu
# ──────────────────────────────────────────────
def analyze_grid(bounds, resolution=5, progress_callback=None):
    if progress_callback:
        progress_callback(0.05, "Grid noktaları oluşturuluyor...")

    points = generate_grid(bounds, resolution)

    if progress_callback:
        progress_callback(0.10, f"{len(points)} nokta · yükseklik alınıyor...")

    elevations = fetch_grid_elevations(points)

    if progress_callback:
        progress_callback(0.20, "Eğimler hesaplanıyor...")

    lat_step = (bounds["max_lat"] - bounds["min_lat"]) / max(1, resolution - 1)
    lon_step = (bounds["max_lon"] - bounds["min_lon"]) / max(1, resolution - 1)
    slopes = calculate_grid_slopes(elevations, resolution, lat_step, lon_step)

    if progress_callback:
        progress_callback(0.30, "NASA POWER verileri toplanıyor...")

    results = []
    total = len(points)

    with ThreadPoolExecutor(max_workers=6) as executor:
        future_map = {}
        for idx, pt in enumerate(points):
            future = executor.submit(gather_point_light,
                                     pt["lat"], pt["lon"],
                                     elevations[idx], slopes[idx])
            future_map[future] = (idx, pt)

        for i, future in enumerate(as_completed(future_map)):
            idx, pt = future_map[future]
            try:
                features = future.result()
                result = recommend(features)
                results.append({**pt, "features": features, "result": result})
            except Exception:
                results.append({**pt, "features": None, "result": None})

            if progress_callback:
                pct = 0.30 + 0.60 * (i + 1) / total
                progress_callback(pct, f"Nokta {i + 1}/{total}")

    results.sort(key=lambda r: (r["row"], r["col"]))

    if progress_callback:
        progress_callback(0.92, "Sonuçlar hesaplanıyor...")

    # Heatmap
    heatmaps = {"Solar": [], "Wind": [], "Hydro": []}
    for r in results:
        if r["result"] is None:
            continue
        for src in ["Solar", "Wind", "Hydro"]:
            score = r["result"]["scores"][src]
            if score > 0:
                heatmaps[src].append([r["lat"], r["lon"], score])

    # Best per source
    best = {}
    valid = [r for r in results if r["result"] is not None]
    for src in ["Solar", "Wind", "Hydro"]:
        if valid:
            top = max(valid, key=lambda r: r["result"]["scores"][src])
            best[src] = {"lat": top["lat"], "lon": top["lon"],
                         "score": top["result"]["scores"][src],
                         "raw": top["result"]["scores_raw"][src]}
        else:
            best[src] = None

    # Averages
    averages = {}
    for src in ["Solar", "Wind", "Hydro"]:
        scores = [r["result"]["scores"][src] for r in valid]
        averages[src] = round(np.mean(scores), 1) if scores else 0

    # Best zones
    best_zones = detect_best_zones(results)

    # Smart insights
    insights = generate_smart_insights(results, bounds, best, averages)

    if progress_callback:
        progress_callback(1.0, "Tamamlandı!")

    return {
        "points": results, "bounds": bounds, "resolution": resolution,
        "heatmaps": heatmaps, "best": best, "averages": averages,
        "best_zones": best_zones, "insights": insights,
    }


# ──────────────────────────────────────────────
# 7. Smart Insights (AI-like yorumlar)
# ──────────────────────────────────────────────
def generate_smart_insights(results, bounds, best, averages):
    valid = [r for r in results if r["result"] is not None]
    if not valid:
        return [{"type": "warning", "title": "Veri Yok",
                 "text": "Analiz edilebilecek veri bulunamadı."}]

    insights = []

    # ── Baskın enerji türü ──
    winners = {}
    for r in valid:
        w = r["result"]["recommendation"]
        winners[w] = winners.get(w, 0) + 1

    dominant = max(winners, key=winners.get)
    pct = winners[dominant] / len(valid) * 100
    names = {"Solar": "güneş", "Wind": "rüzgar", "Hydro": "hidro"}

    if pct >= 80:
        insights.append({
            "type": "success",
            "title": "Bölgesel Baskınlık",
            "text": f"Noktaların %{pct:.0f}'inde {names[dominant]} enerjisi "
                    f"en yüksek skoru alıyor. Bu bölge {names[dominant]} için çok uygun."
        })
    elif len(winners) >= 2:
        sorted_w = sorted(winners.items(), key=lambda x: -x[1])
        insights.append({
            "type": "info",
            "title": "Karma Potansiyel",
            "text": f"Bölgede hibrit sistem potansiyeli var: "
                    f"{names[sorted_w[0][0]]} %{sorted_w[0][1] / len(valid) * 100:.0f}, "
                    f"{names[sorted_w[1][0]]} %{sorted_w[1][1] / len(valid) * 100:.0f}."
        })

    # ── Limiting Factors ──
    avg_ghi = np.mean([r["features"]["ghi_kwh_m2_day"] for r in valid])
    avg_wind = np.mean([r["features"]["wind_50m_ms"] for r in valid])
    avg_slope = np.mean([r["features"]["slope_deg"] for r in valid])
    avg_humidity = np.mean([r["features"]["humidity_pct"] for r in valid])
    avg_rain = np.mean([r["features"]["precip_mm_day"] for r in valid])

    # Solar limitler
    if averages["Solar"] > 30:
        limiters = []
        if avg_humidity > 70:
            limiters.append(f"yüksek nem (%{avg_humidity:.0f})")
        if avg_slope > 15:
            limiters.append(f"dik eğim ({avg_slope:.0f}°)")
        if avg_rain > 3:
            limiters.append(f"yüksek yağış ({avg_rain:.1f} mm/gün)")
        if limiters:
            insights.append({
                "type": "warning",
                "title": "Solar Kısıtlayıcılar",
                "text": f"Güneş potansiyeli var ama {', '.join(limiters)} "
                        f"performansı düşürüyor."
            })

    # Wind limitler
    if averages["Wind"] > 30:
        limiters = []
        if avg_wind < 5:
            limiters.append(f"düşük rüzgar hızı ({avg_wind:.1f} m/s)")
        wind_scores = [r["result"]["scores"]["Wind"] for r in valid]
        if np.std(wind_scores) > 15:
            limiters.append("yüksek mekansal değişkenlik")
        if limiters:
            insights.append({
                "type": "warning",
                "title": "Rüzgar Kısıtlayıcıları",
                "text": f"Rüzgar potansiyeli var ama {', '.join(limiters)} "
                        f"dikkate alınmalı."
            })

    # Hidro limitler
    if averages["Hydro"] > 20:
        water_found = sum(1 for r in valid
                          if r["features"]["water"]["has_water"])
        if water_found == 0:
            insights.append({
                "type": "warning",
                "title": "Hidro Kısıtlayıcısı",
                "text": "Akış potansiyeli var ama doğrulanmış su kaynağı bulunamadı. "
                        "Sahada doğrulama gerekli."
            })

    # ── Yükseklik-skor ilişkisi ──
    elevs = [r["features"]["elevation_m"] for r in valid]
    if np.std(elevs) > 50:
        for src in ["Solar", "Wind", "Hydro"]:
            scores = [r["result"]["scores"][src] for r in valid]
            if np.std(scores) > 5:
                corr = np.corrcoef(elevs, scores)[0, 1]
                if abs(corr) > 0.5:
                    direction = "yüksek" if corr > 0 else "alçak"
                    insights.append({
                        "type": "info",
                        "title": f"{names[src].title()} & Yükseklik",
                        "text": f"{names[src].title()} skoru {direction} rakımlarda "
                                f"daha güçlü (korelasyon: {corr:.2f})."
                    })

    # ── Fırsat skoru ──
    overall_best = max(valid, key=lambda r: max(r["result"]["scores"].values()))
    ob_w = overall_best["result"]["recommendation"]
    ob_s = overall_best["result"]["scores"][ob_w]
    insights.append({
        "type": "success",
        "title": "En İyi Fırsat",
        "text": f"({overall_best['lat']:.4f}, {overall_best['lon']:.4f}) noktasında "
                f"{names[ob_w]} enerjisi {ob_s:.0f}/100 skor ile en yüksek potansiyele sahip."
    })

    return insights