"""
GreenGrid — Bakım Tahmincisi (maintenance.py)
==============================================
Önerilen enerji sistemi için bakım takvimi üretir.

Aralıklar statik DEĞİL — konumun çevresel verilerine göre ayarlanır:
  - Tozlu bölge → panel temizliği daha sık
  - Sert rüzgar → şanzıman bakımı daha erken
  - Yüksek yağış → hidro giriş daha sık temizlenir

Kaynaklar:
  - NREL Operations & Maintenance Best Practices
  - IEC 61400 (rüzgar türbini bakım standartları)
  - Micro-hydro Design Manual (Adam Harvey)
"""


def maintenance_schedule(energy_type: str, f: dict) -> list[dict]:
    """
    Verilen enerji türü ve çevresel veriye göre bakım takvimi döner.

    Parametreler:
        energy_type: "Solar" | "Wind" | "Hydro"
        f:           gather_all() çıktısı (features sözlüğü)

    Dönüş:
        Liste of dict: [{task, interval_days, reason, priority}, ...]
        priority: "Yüksek" | "Orta" | "Düşük"
    """

    if energy_type == "Solar":
        return _solar_maintenance(f)
    elif energy_type == "Wind":
        return _wind_maintenance(f)
    elif energy_type == "Hydro":
        return _hydro_maintenance(f)
    else:
        return []


# ──────────────────────────────────────────────
# GÜNEŞ PANELİ BAKIM TAKVİMİ
# ──────────────────────────────────────────────
def _solar_maintenance(f: dict) -> list[dict]:
    """
    Güneş paneli bakım görevleri.

    Kirleme (soiling) mantığı:
      - Az yağmur + düşük nem = TOZ bölgesi → 21 günde bir temizlik
      - Orta yağış = yağmur kısmen temizler → 45 gün
      - Yüksek yağış = doğal temizlik → 75 gün

    Sıcaklık mantığı:
      - Yüksek sıcaklık = termal stres → daha sık inverter kontrolü
    """
    rain = f["precip_mm_day"]
    humidity = f["humidity_pct"]
    temp = f["temp_c"]

    # ── Panel temizliği ──
    dusty = rain < 1.5 and humidity < 50
    if dusty:
        cleaning_days = 21
        cleaning_reason = (
            f"Düşük yağış ({rain:.1f} mm/gün) ve düşük nem (%{humidity:.0f}) "
            f"→ yüksek toz birikimi. Sık temizlik şart."
        )
        cleaning_priority = "Yüksek"
    elif rain < 3:
        cleaning_days = 45
        cleaning_reason = (
            f"Orta seviye yağış ({rain:.1f} mm/gün) panelleri "
            f"kısmen temizliyor ama yeterli değil."
        )
        cleaning_priority = "Orta"
    else:
        cleaning_days = 75
        cleaning_reason = (
            f"Yüksek yağış ({rain:.1f} mm/gün) panelleri "
            f"doğal olarak temizliyor. Rutin kontrol yeterli."
        )
        cleaning_priority = "Düşük"

    # ── İnverter kontrolü ──
    # Sıcak bölgelerde inverter daha hızlı yıpranır
    if temp > 25:
        inverter_days = 120
        inverter_reason = (
            f"Yüksek ortalama sıcaklık ({temp:.1f}°C) → "
            f"inverter termal stresi artırıyor."
        )
    else:
        inverter_days = 180
        inverter_reason = "Standart 6 aylık inverter kontrol periyodu."

    return [
        {
            "task":          "Panel temizliği",
            "interval_days": cleaning_days,
            "reason":        cleaning_reason,
            "priority":      cleaning_priority,
        },
        {
            "task":          "Görsel inceleme (çatlak, sıcak nokta)",
            "interval_days": 90,
            "reason":        "3 aylık termal kamera ile hot-spot taraması. "
                             "Mikro çatlaklar verimi %5-20 düşürebilir.",
            "priority":      "Orta",
        },
        {
            "task":          "İnverter kontrol ve firmware güncellemesi",
            "interval_days": inverter_days,
            "reason":        inverter_reason,
            "priority":      "Yüksek",
        },
        {
            "task":          "Kablolama, bağlantı kutusu, montaj torku",
            "interval_days": 365,
            "reason":        "Yıllık elektriksel ve yapısal denetim. "
                             "Gevşek bağlantılar ark oluşturabilir.",
            "priority":      "Orta",
        },
    ]


# ──────────────────────────────────────────────
# RÜZGAR TÜRBİNİ BAKIM TAKVİMİ
# ──────────────────────────────────────────────
def _wind_maintenance(f: dict) -> list[dict]:
    """
    Rüzgar türbini bakım görevleri.

    Sert koşul tanımı:
      - Rüzgar > 9 m/s VEYA nem > %75
      - Sert koşullar → şanzıman ve kanat bakımı daha sık
    """
    ws50 = f["wind_50m_ms"]
    humidity = f["humidity_pct"]
    harsh = ws50 > 9 or humidity > 75

    # ── Kanat incelemesi ──
    if ws50 > 8:
        blade_days = 60
        blade_reason = (
            f"Yüksek rüzgar hızı ({ws50:.1f} m/s) → "
            f"kanat ön kenar erozyonu riski yüksek. "
            f"2 ayda bir drone incelemesi önerilir."
        )
        blade_priority = "Yüksek"
    else:
        blade_days = 90
        blade_reason = "Standart 3 aylık kanat görsel incelemesi (drone ile)."
        blade_priority = "Orta"

    # ── Şanzıman (gearbox) bakımı ──
    gearbox_days = 120 if harsh else 180
    gearbox_reason = (
        f"{'Sert' if harsh else 'Normal'} çalışma koşulları "
        f"(rüzgar: {ws50:.1f} m/s, nem: %{humidity:.0f}). "
        f"Yağ numunesi analizi ve filtrasyon kontrolü."
    )

    return [
        {
            "task":          "Kanat görsel incelemesi (drone)",
            "interval_days": blade_days,
            "reason":        blade_reason,
            "priority":      blade_priority,
        },
        {
            "task":          "Şanzıman yağ analizi",
            "interval_days": gearbox_days,
            "reason":        gearbox_reason,
            "priority":      "Yüksek",
        },
        {
            "task":          "Cıvata torku ve sapma (yaw) sistemi kontrolü",
            "interval_days": 180,
            "reason":        "Titreşim bağlantıları gevşetir. "
                             "Yaw motoru ve rulman kontrolü.",
            "priority":      "Orta",
        },
        {
            "task":          "Tam revizyon (jeneratör, rulmanlar)",
            "interval_days": 365 * 5,
            "reason":        "5 yıllık büyük bakım. Jeneratör sargıları, "
                             "ana rulman, fren sistemi tam denetim.",
            "priority":      "Yüksek",
        },
    ]


# ──────────────────────────────────────────────
# HİDROELEKTRİK BAKIM TAKVİMİ
# ──────────────────────────────────────────────
def _hydro_maintenance(f: dict) -> list[dict]:
    """
    Hidroelektrik bakım görevleri.

    Sediman mantığı:
      - Yüksek yağış = yüksek erozyon = çok sediman
      - Sediman giriş ızgarasını tıkar → sık temizlik
    """
    rain = f["precip_mm_day"]
    sediment_risk = rain > 5

    # ── Giriş ızgara temizliği ──
    if sediment_risk:
        intake_days = 30
        intake_reason = (
            f"Yüksek yağış ({rain:.1f} mm/gün) → "
            f"yüksek sediman yükü. Aylık temizlik şart."
        )
        intake_priority = "Yüksek"
    elif rain > 2.5:
        intake_days = 45
        intake_reason = (
            f"Orta yağış ({rain:.1f} mm/gün) → "
            f"düzenli sediman birikimi. 45 günde bir temizlik."
        )
        intake_priority = "Orta"
    else:
        intake_days = 60
        intake_reason = "Düşük sediman riski. 2 ayda bir rutin kontrol."
        intake_priority = "Düşük"

    return [
        {
            "task":          "Giriş ızgarası ve çökelti temizliği",
            "interval_days": intake_days,
            "reason":        intake_reason,
            "priority":      intake_priority,
        },
        {
            "task":          "Türbin rulman yağlama",
            "interval_days": 90,
            "reason":        "Sürekli çalışan bileşen. "
                             "Yağ seviyesi ve kalitesi kontrolü.",
            "priority":      "Orta",
        },
        {
            "task":          "Cebri boru (penstock) ve vana incelemesi",
            "interval_days": 180,
            "reason":        "Basınçlı sistem bütünlük kontrolü. "
                             "Korozyon, sızıntı, conta durumu.",
            "priority":      "Yüksek",
        },
        {
            "task":          "Jeneratör tam revizyonu",
            "interval_days": 365 * 3,
            "reason":        "3 yıllık büyük bakım. Sargı direnci, "
                             "fırça/halka durumu, titreşim analizi.",
            "priority":      "Yüksek",
        },
    ]


# ──────────────────────────────────────────────
# Test
# ──────────────────────────────────────────────
if __name__ == "__main__":

    # Gerçek test verileri (data_fetcher çıktılarından)
    test_cases = [
        {
            "name": "Konya → Solar bakım takvimi",
            "type": "Solar",
            "features": {
                "ghi_kwh_m2_day": 4.93, "wind_50m_ms": 4.98,
                "temp_c": 11.31, "humidity_pct": 62.42,
                "precip_mm_day": 1.08, "slope_deg": 0.57,
            },
        },
        {
            "name": "Çanakkale → Wind bakım takvimi",
            "type": "Wind",
            "features": {
                "ghi_kwh_m2_day": 4.45, "wind_50m_ms": 7.21,
                "temp_c": 16.18, "humidity_pct": 73.39,
                "precip_mm_day": 1.68, "slope_deg": 0.0,
            },
        },
        {
            "name": "Rize → Hydro bakım takvimi",
            "type": "Hydro",
            "features": {
                "ghi_kwh_m2_day": 4.14, "wind_50m_ms": 3.33,
                "temp_c": 10.71, "humidity_pct": 78.13,
                "precip_mm_day": 3.24, "slope_deg": 32.01,
            },
        },
    ]

    for tc in test_cases:
        print(f"\n{'='*60}")
        print(f"  {tc['name']}")
        print(f"{'='*60}")

        schedule = maintenance_schedule(tc["type"], tc["features"])

        for i, task in enumerate(schedule, 1):
            # Aralığı insanca göster
            days = task["interval_days"]
            if days >= 365:
                interval_str = f"{days // 365} yıl"
            elif days >= 30:
                interval_str = f"{days} gün (~{days // 30} ay)"
            else:
                interval_str = f"{days} gün"

            priority_emoji = {
                "Yüksek": "🔴",
                "Orta":   "🟡",
                "Düşük":  "🟢",
            }[task["priority"]]

            print(f"\n  {i}. {task['task']}")
            print(f"     ⏱️  Her {interval_str}")
            print(f"     {priority_emoji} Öncelik: {task['priority']}")
            print(f"     💬 {task['reason']}")