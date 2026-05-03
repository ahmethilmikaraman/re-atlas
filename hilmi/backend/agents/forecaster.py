import math
from typing import List, Dict, Any
from backend.schemas import WeatherData, ForecastResult, HourlyForecast

def run_forecast(weather: WeatherData) -> ForecastResult:
    """
    Tek bir nokta için tahmin ve tavsiye üretir.
    """
    wind = weather.wind_speed_m_s
    solar = weather.solar_irradiation_w_m2
    
    if wind > 6.5 and solar > 1600:
        rec = "Hibrit Sistem"
        reasoning = "Bölgede hem rüzgar hem de güneş potansiyeli yüksektir."
    elif wind > 6.5:
        rec = "Rüzgar Türbini (RES)"
        reasoning = f"Ortalama rüzgar hızı {wind} m/s olup, rüzgar enerjisi yatırımı için elverişlidir."
    elif solar > 1600:
        rec = "Güneş Enerjisi (GES)"
        reasoning = f"Yıllık ortalama GHI değeri {solar} W/m2 olup, güneş enerjisi yatırımı için oldukça verimlidir."
    else:
        rec = "Yatırım Uygun Değil"
        reasoning = "Potansiyel düşük kalmaktadır."
    
    forecast_48h = []
    for hour in range(48):
        expected_power = 0.0
        if "GES" in rec or "Güneş" in rec or "Hibrit" in rec:
            day_hour = hour % 24
            if 6 < day_hour < 18:
                sun_factor = math.sin((day_hour - 6) * math.pi / 12)
                expected_power += (solar / 1000.0 * 50) * sun_factor
        if "RES" in rec or "Rüzgar" in rec or "Hibrit" in rec:
            wind_factor = 1.0 + (math.sin(hour * 0.5) * 0.2)
            expected_power += (wind * 8.0) * wind_factor
        forecast_48h.append(HourlyForecast(hour=hour, expected_power_kw=round(max(0.0, expected_power), 2)))
        
    return ForecastResult(recommendation=rec, reasoning=reasoning, forecast_48h=forecast_48h)

def generate_forecast(base_solar: float, base_wind: float, hours: int) -> List[Dict[str, Any]]:
    """
    Belirli bir baz değer üzerinden saatlik sentetik tahmin verisi üretir.
    """
    import random
    forecast = []
    for h in range(hours):
        hour_val = h % 24
        
        # Güneş Tahmini: Çan eğrisi (06:00 - 20:00 arası)
        if 6 <= hour_val <= 20:
            # Normalize edilmiş sinüs dalgası
            sun_factor = math.sin((hour_val - 6) * math.pi / 14)
            solar = base_solar * sun_factor * (0.8 + random.random() * 0.4) # +- %20 gürültü
        else:
            solar = random.random() * 5.0 # Gece gürültüsü
            
        # Rüzgar Tahmini: Baz değer etrafında +- %20 dalgalanma
        wind = base_wind * (0.8 + random.random() * 0.4)
        
        forecast.append({
            "hour": f"{hour_val:02d}:00",
            "solar": round(max(0, solar), 1),
            "wind": round(max(0, wind), 1)
        })
    return forecast

def run_regional_analysis(weather_list: List[WeatherData]) -> Dict[str, Any]:
    """
    Birden fazla noktanın verilerini analiz ederek bölgesel özet ve 'sweet spot' bulur.
    """
    if not weather_list:
        return {}

    total_solar = 0.0
    total_wind = 0.0
    sweet_spot = weather_list[0]
    max_score = -1.0

    points_data = []
    for w in weather_list:
        total_solar += w.solar_irradiation_w_m2
        total_wind += w.wind_speed_m_s
        
        score = (w.solar_irradiation_w_m2 / 2000.0) + (w.wind_speed_m_s / 12.0)
        if score > max_score:
            max_score = score
            sweet_spot = w
        
        points_data.append({
            "lat": w.latitude,
            "lon": w.longitude,
            "solar": w.solar_irradiation_w_m2,
            "wind": w.wind_speed_m_s
        })

    avg_solar = total_solar / len(weather_list)
    avg_wind = total_wind / len(weather_list)

    # Genel tavsiye algoritması
    if avg_wind > 6.5 and avg_solar > 1600:
        recommendation = "Karma (Hibrit) Sistem Önerilir"
    elif avg_wind > 6.5:
        recommendation = "Rüzgar Verimi Daha Yüksek"
    elif avg_solar > 1600:
        recommendation = "GES Kurulumuna Çok Uygun"
    else:
        recommendation = "Yatırım Potansiyeli Sınırlı"

    return {
        "points_data": points_data,
        "area_summary": {
            "avg_solar": round(avg_solar, 2),
            "avg_wind": round(avg_wind, 2),
            "point_count": len(weather_list)
        },
        "sweet_spot": {
            "lat": sweet_spot.latitude,
            "lon": sweet_spot.longitude,
            "solar": sweet_spot.solar_irradiation_w_m2,
            "wind": sweet_spot.wind_speed_m_s
        },
        "general_recommendation": recommendation,
        "forecast_24h": generate_forecast(avg_solar, avg_wind, 24),
        "forecast_48h": generate_forecast(avg_solar, avg_wind, 48)
    }
