import rasterio
import numpy as np
import os
from typing import List, Dict
from backend.schemas import WeatherData

# Dosya yolları
GHI_TIF = os.path.join("data", "GHI.tif")
WIND_TIF = os.path.join("data", "WIND.tif")

def read_tif_value(tif_path: str, lat: float, lon: float) -> float:
    """
    Belirtilen GeoTIFF dosyasından verilen koordinattaki değeri anlık olarak okur.
    """
    try:
        with rasterio.open(tif_path) as dataset:
            row, col = dataset.index(lon, lat)
            if 0 <= row < dataset.height and 0 <= col < dataset.width:
                window = rasterio.windows.Window(col, row, 1, 1)
                value = dataset.read(1, window=window)
                return float(value[0, 0])
            else:
                return 0.0
    except Exception as e:
        print(f"Hata: {tif_path} okunurken bir problem oluştu: {e}")
        return 0.0

def ingest_weather_data(lat: float, lon: float) -> WeatherData:
    """
    GeoTIFF dosyalarından gerçek verileri anlık olarak okur.
    """
    solar = read_tif_value(GHI_TIF, lat, lon)
    wind = read_tif_value(WIND_TIF, lat, lon)
    temp = 15.0 + ((42.0 - lat) * 1.5) - (wind * 0.2)
    
    return WeatherData(
        latitude=lat,
        longitude=lon,
        wind_speed_m_s=round(wind, 2),
        solar_irradiation_w_m2=round(solar, 2),
        temperature_c=round(temp, 1)
    )

def ingest_bulk_weather_data(points: List[Dict[str, float]]) -> List[WeatherData]:
    """
    Birden fazla koordinat için GeoTIFF dosyalarını sadece bir kez açarak toplu okuma yapar.
    """
    results = []
    try:
        with rasterio.open(GHI_TIF) as ghi_ds, rasterio.open(WIND_TIF) as wind_ds:
            for p in points:
                lat, lon = p['lat'], p['lon']
                
                # GHI oku
                r1, c1 = ghi_ds.index(lon, lat)
                solar = 0.0
                if 0 <= r1 < ghi_ds.height and 0 <= c1 < ghi_ds.width:
                    solar = float(ghi_ds.read(1, window=rasterio.windows.Window(c1, r1, 1, 1))[0, 0])
                
                # WIND oku
                r2, c2 = wind_ds.index(lon, lat)
                wind = 0.0
                if 0 <= r2 < wind_ds.height and 0 <= c2 < wind_ds.width:
                    wind = float(wind_ds.read(1, window=rasterio.windows.Window(c2, r2, 1, 1))[0, 0])
                
                temp = 15.0 + ((42.0 - lat) * 1.5) - (wind * 0.2)
                
                results.append(WeatherData(
                    latitude=lat,
                    longitude=lon,
                    wind_speed_m_s=round(wind, 2),
                    solar_irradiation_w_m2=round(solar, 2),
                    temperature_c=round(temp, 1)
                ))
    except Exception as e:
        print(f"Toplu okuma hatası: {e}")
        
    return results
