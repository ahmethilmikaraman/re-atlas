import hashlib
import math

def _get_deterministic_seed(lat: float, lon: float) -> float:
    """Koordinatlardan 0 ile 1 arasında deterministik bir çarpan üretir."""
    # Enlem ve boylamı string'e çevirip hash'liyoruz (2 ondalık hassasiyet)
    coord_str = f"{lat:.2f}_{lon:.2f}"
    hash_obj = hashlib.md5(coord_str.encode())
    # Hash'i integer'a çevirip normalize ediyoruz
    return int(hash_obj.hexdigest()[:8], 16) / 0xffffffff

def generate_wind_speed(lat: float, lon: float) -> float:
    """
    Koordinatlara göre deterministik ortalama rüzgar hızı üretir (m/s).
    """
    base_wind = 4.0
    seed_multiplier = _get_deterministic_seed(lat, lon)
    
    # Boylam veya enleme göre yapay dalgalanma (sin formülü ile)
    spatial_variance = math.sin(lat) + math.cos(lon)
    
    # Toplam hız (3.0 ile 10 civarı)
    wind_speed = base_wind + (seed_multiplier * 5.0) + spatial_variance
    return round(max(2.0, wind_speed), 2)

def generate_solar_irradiation(lat: float, lon: float) -> float:
    """
    Koordinatlara göre deterministik ortalama güneş ışınımı üretir (W/m2).
    Ekvatora yakın (düşük enlem) bölgelerde daha yüksektir.
    Türkiye için enlemler genelde 36 - 42 arasındadır.
    """
    seed_multiplier = _get_deterministic_seed(lat, lon)
    
    # Enlem düştükçe güneş artar. 42 enleminde 0, 36 enleminde 1 çarpanı.
    lat_factor = max(0, (42.0 - lat) / 6.0)
    base_solar = 150.0 + (lat_factor * 80.0)
    
    # Deterministik rastgelelik ekliyoruz
    solar_irradiance = base_solar + (seed_multiplier * 40.0)
    return round(max(100.0, solar_irradiance), 2)
