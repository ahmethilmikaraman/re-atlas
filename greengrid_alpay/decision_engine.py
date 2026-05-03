"""
GreenGrid — Karar Motoru (decision_engine.py) v4
=================================================
v4 değişiklikleri:
  - Confidence artık skorlara çarpan olarak etki ediyor
  - CV çarpanı 80 → 60 (daha gerçekçi)
  - Elevation ağırlığı %15 → %10 (hız %65'e çıktı)
  - Humidity eşiği 40 → 60 (%60 altı ceza yok)
  - Water status: "failed" vs "not_found" ayrımı
  - Hidro 3 durumlu: su doğrulandı / API fail ama akış var / hiçbiri
"""

import numpy as np


def _clip(x, lo=0, hi=100):
    return max(lo, min(hi, x))


# ──────────────────────────────────────────────
# 1. GÜNEŞ
# ──────────────────────────────────────────────
def score_solar(f):
    """
    %60 GHI | %15 eğim | %15 nem | %10 yağış
    """
    ghi = f["ghi_kwh_m2_day"]
    ghi_score = _clip(((ghi - 3.0) / 3.5) * 100)

    # Güneş eğim: düz = iyi
    slope = f["slope_deg"]
    if slope <= 5:
        slope_score = 90
    elif slope <= 20:
        slope_score = 90 - (slope - 5)
    else:
        slope_score = max(0, 75 - (slope - 20) * 5)
    slope_score = _clip(slope_score)

    # Nem: %60 altı ceza yok, %60-90 arası yumuşak ceza
    humidity = f["humidity_pct"]
    humidity_score = _clip(100 - max(0, humidity - 60) * 1.5)

    rain_score = _clip(100 - f["precip_mm_day"] * 8)

    total = (0.60 * ghi_score + 0.15 * slope_score +
             0.15 * humidity_score + 0.10 * rain_score)

    breakdown = {
        "GHI (kWh/m²/gün)": f"{ghi:.2f} → {ghi_score:.0f}/100",
        "Eğim":             f"{slope:.1f}° → {slope_score:.0f}/100  (düz = iyi)",
        "Nem":              f"%{humidity:.0f} → {humidity_score:.0f}/100",
        "Yağış":            f"{f['precip_mm_day']:.1f} mm/gün → {rain_score:.0f}/100",
    }
    return round(total, 1), breakdown


# ──────────────────────────────────────────────
# 2. RÜZGAR
# ──────────────────────────────────────────────
def score_wind(f):
    """
    %65 hız | %25 tutarlılık | %10 yükseklik
    Yükseklik ağırlığı düşürüldü — tek başına belirleyici değil.
    """
    ws50 = f["wind_50m_ms"]
    speed_score = _clip(((ws50 - 4.0) / 4.0) * 100)

    # CV çarpanı yumuşatıldı: 80 → 60
    # Üstel yerine doğrusal ama daha az agresif
    cv = f["wind_cv"]
    consistency_score = _clip(100 - cv * 60)

    # Yükseklik ağırlığı %10'a düşürüldü
    elev_score = _clip(50 + f["elevation_m"] / 25)

    total = (0.65 * speed_score + 0.25 * consistency_score +
             0.10 * elev_score)

    breakdown = {
        "Rüzgar @50m":    f"{ws50:.2f} m/s → {speed_score:.0f}/100",
        "Tutarlılık (CV)": f"{cv:.2f} → {consistency_score:.0f}/100",
        "Yükseklik":      f"{f['elevation_m']:.0f} m → {elev_score:.0f}/100",
    }
    return round(total, 1), breakdown


# ──────────────────────────────────────────────
# 3. HİDRO — 3 durumlu mantık
# ──────────────────────────────────────────────
def score_hydro(f):
    """
    3 DURUM:
      A) Su doğrulandı (Overpass OK + su var)
         %35 yakınlık + %25 eğim + %25 yağış + %15 akış → tavan yok

      B) API fail/atlandı + akış potansiyeli var
         %40 akış + %35 eğim + %25 yağış → tavan 45
         (su doğrulanmamış — çok temkinli ol)

      C) API çalıştı, su bulamadı + akış potansiyeli var
         → tavan 30 (API aktif olarak su aradı, bulamadı)

      D) Hiçbir şey yok → 0

    Hidro eğim: dik = iyi ama SADECE su varsa anlamlı.
    Minimum eğim eşiği: 8° (düz arazide hidro saçma)
    """
    water = f["water"]
    slope = f["slope_deg"]
    rain  = f["precip_mm_day"]
    flow  = f.get("flow", {})

    water_status = water.get("status", "failed")

    # Minimum eğim kontrolü — düz arazide hidro mantıksız
    if slope < 8:
        head_score = 0
    else:
        head_score = _clip((slope - 8) * 5)  # eski: (slope-3)*7

    rain_score = _clip(rain * 20)  # eski: rain*25
    flow_score = flow.get("flow_score", 0)

    # ── DURUM A: Su doğrulandı ──
    if water["has_water"]:
        dist = water["distance_km"]
        proximity = _clip(100 - dist * 10)
        label = f"✅ {water['type']}: {dist:.1f} km → {proximity:.0f}/100"

        total = (0.35 * proximity + 0.25 * head_score +
                 0.25 * rain_score + 0.15 * flow_score)

        bd = {
            "Su kaynağı":   label,
            "Eğim (head)":  f"{slope:.1f}° → {head_score:.0f}/100  (dik = iyi)",
            "Yağış (akış)": f"{rain:.1f} mm/gün → {rain_score:.0f}/100",
            "Akış tahmini": f"{flow_score:.0f}/100",
        }
        return round(total, 1), bd

    # ── DURUM B: API fail/atlandı + akış potansiyeli var ──
    if water_status in ("failed", "skipped") and flow.get("has_estimated_flow"):
        raw = 0.40 * flow_score + 0.35 * head_score + 0.25 * rain_score
        total = min(45.0, raw)  # eski: 65

        bd = {
            "Su kaynağı":   "⚠️ Doğrulanmadı — akış tahmini (maks 45)",
            "Akış tahmini": f"{flow_score:.0f}/100 ({flow.get('reason','')})",
            "Eğim (head)":  f"{slope:.1f}° → {head_score:.0f}/100  (dik = iyi)",
            "Yağış (akış)": f"{rain:.1f} mm/gün → {rain_score:.0f}/100",
        }
        return round(total, 1), bd

    # ── DURUM C: API çalıştı, su yok ama akış var ──
    if water_status == "ok" and flow.get("has_estimated_flow"):
        raw = 0.40 * flow_score + 0.35 * head_score + 0.25 * rain_score
        total = min(30.0, raw)  # eski: 40

        bd = {
            "Su kaynağı":   "❌ API aradı, bulamadı — maks 30",
            "Akış tahmini": f"{flow_score:.0f}/100 ({flow.get('reason','')})",
            "Eğim (head)":  f"{slope:.1f}° → {head_score:.0f}/100",
            "Yağış (akış)": f"{rain:.1f} mm/gün → {rain_score:.0f}/100",
        }
        return round(total, 1), bd

    # ── DURUM D: Hiçbir şey yok ──
    return 0.0, {"Su kaynağı": "Su ve akış potansiyeli bulunamadı → 0/100"}


# ──────────────────────────────────────────────
# 4. ANA ÖNERİ — Confidence skora etki ediyor
# ──────────────────────────────────────────────
def recommend(features):
    solar_raw, solar_bd = score_solar(features)
    wind_raw,  wind_bd  = score_wind(features)
    hydro_raw, hydro_bd = score_hydro(features)

    confidence = features.get("confidence", 0.8)

    # ── Confidence düzeltmesi ──
    # Düşük confidence → skorları orantılı düşür
    # Ama tamamen sıfırlama — minimum %60 tutulur
    # conf_mult: 1.0 → 0.85 → 0.7 → 0.6 aralığında
    conf_mult = max(0.6, confidence)

    solar = round(solar_raw * conf_mult, 1)
    wind  = round(wind_raw  * conf_mult, 1)
    hydro = round(hydro_raw * conf_mult, 1)

    scores = {"Solar": solar, "Wind": wind, "Hydro": hydro}
    winner = max(scores, key=scores.get)
    top = scores[winner]

    # ── Fizibilite ──
    if top >= 65:
        feas = "Yüksek"
    elif top >= 40:
        feas = "Orta"
    elif top >= 20:
        feas = "Düşük"
    else:
        feas = "Uygun Değil"

    # Confidence düşükse uyarı ekle
    if confidence < 0.6:
        feas += " (⚠️ veri eksik)"

    # ── Açıklamalar ──
    reasons = {
        "Solar": (f"GHI {features['ghi_kwh_m2_day']:.1f} kWh/m²/gün, "
                  f"eğim {features['slope_deg']:.1f}°, "
                  f"nem %{features['humidity_pct']:.0f}."),
        "Wind":  (f"Rüzgar {features['wind_50m_ms']:.1f} m/s @50m, "
                  f"CV={features['wind_cv']:.2f}."),
        "Hydro": (f"Eğim {features['slope_deg']:.1f}° (head), "
                  f"yağış {features['precip_mm_day']:.1f} mm/gün."
                  + (f" Su ({features['water']['type']}): "
                     f"{features['water']['distance_km']:.1f} km."
                     if features["water"]["has_water"]
                     else f" {features.get('flow',{}).get('reason','')}")),
    }

    if top < 20:
        reason = (f"Bu konum yenilenebilir enerji için uygun görünmüyor. "
                  f"En yüksek: {winner} {top:.0f}/100.")
    else:
        reason = reasons[winner]

    return {
        "recommendation": winner,
        "scores":         scores,
        "scores_raw":     {"Solar": solar_raw, "Wind": wind_raw, "Hydro": hydro_raw},
        "feasibility":    feas,
        "confidence":     confidence,
        "reason":         reason,
        "breakdown":      {"Solar": solar_bd, "Wind": wind_bd, "Hydro": hydro_bd},
    }


# ──────────────────────────────────────────────
# Test
# ──────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        ("Konya ☀️", {
            "ghi_kwh_m2_day":4.93,"wind_50m_ms":4.98,"humidity_pct":62.42,
            "precip_mm_day":1.08,"slope_deg":0.57,"elevation_m":1030,
            "wind_cv":0.597,"confidence":0.9,
            "water":{"status":"ok","has_water":True,"distance_km":2.84,"type":"water"},
            "flow":{"flow_score":0,"has_estimated_flow":False,"reason":"Yetersiz yağış"},
        }),
        ("Çanakkale 💨", {
            "ghi_kwh_m2_day":4.45,"wind_50m_ms":7.21,"humidity_pct":73.39,
            "precip_mm_day":1.68,"slope_deg":0.0,"elevation_m":0,
            "wind_cv":0.738,"confidence":0.85,
            "water":{"status":"ok","has_water":False,"distance_km":None,"type":None},
            "flow":{"flow_score":0,"has_estimated_flow":False,"reason":"Yetersiz"},
        }),
        ("Rize — API FAIL 💧", {
            "ghi_kwh_m2_day":4.14,"wind_50m_ms":3.33,"humidity_pct":78.13,
            "precip_mm_day":3.24,"slope_deg":32.01,"elevation_m":871,
            "wind_cv":0.45,"confidence":0.78,
            "water":{"status":"failed","has_water":False,"distance_km":None,"type":None},
            "flow":{"flow_score":62,"has_estimated_flow":True,
                    "reason":"Yağış+eğim+rakım → akış var"},
        }),
        ("Rize — API OK 💧", {
            "ghi_kwh_m2_day":4.14,"wind_50m_ms":3.33,"humidity_pct":78.13,
            "precip_mm_day":3.24,"slope_deg":32.01,"elevation_m":871,
            "wind_cv":0.45,"confidence":0.93,
            "water":{"status":"ok","has_water":True,"distance_km":7.39,"type":"river"},
            "flow":{"flow_score":62,"has_estimated_flow":True,
                    "reason":"Yağış+eğim+rakım → akış var"},
        }),
        ("Rize — API OK ama su yok 🤔", {
            "ghi_kwh_m2_day":4.14,"wind_50m_ms":3.33,"humidity_pct":78.13,
            "precip_mm_day":3.24,"slope_deg":32.01,"elevation_m":871,
            "wind_cv":0.45,"confidence":0.85,
            "water":{"status":"ok","has_water":False,"distance_km":None,"type":None},
            "flow":{"flow_score":62,"has_estimated_flow":True,
                    "reason":"Yağış+eğim+rakım → akış var"},
        }),
    ]

    for name, f in tests:
        r = recommend(f)
        emoji = {"Solar":"☀️","Wind":"💨","Hydro":"💧"}[r["recommendation"]]
        raw = r["scores_raw"][r["recommendation"]]
        adj = r["scores"][r["recommendation"]]

        print(f"\n{'='*60}")
        print(f"  {name}")
        print(f"  🏆 {r['recommendation']} {emoji}  "
              f"ham={raw:.1f} → düzeltilmiş={adj:.1f}  "
              f"conf={r['confidence']}  feas={r['feasibility']}")
        print(f"  💬 {r['reason']}")

        for src in ["Solar","Wind","Hydro"]:
            bar = "█" * int(r["scores"][src]/2) + "░" * (50-int(r["scores"][src]/2))
            print(f"    {src:6s} [{bar}] {r['scores'][src]:.1f} "
                  f"(ham: {r['scores_raw'][src]:.1f})")

        for src, bd in r["breakdown"].items():
            print(f"    ── {src} ──")
            for k, v in bd.items():
                print(f"       {k}: {v}")