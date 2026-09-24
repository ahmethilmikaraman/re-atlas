from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

class LocationRequest(BaseModel):
    latitude: float = Field(..., description="Latitude of the location", ge=-90, le=90)
    longitude: float = Field(..., description="Longitude of the location", ge=-180, le=180)

class GridAnalysisRequest(BaseModel):
    points: List[Dict[str, float]] # [{'lat': ..., 'lon': ...}, ...]

class WeatherData(BaseModel):
    latitude: float
    longitude: float
    wind_speed_m_s: float = Field(..., description="Ortalama rüzgar hızı (m/s)")
    solar_irradiation_w_m2: float = Field(..., description="Ortalama güneş ışınımı (W/m2)")
    temperature_c: float = Field(..., description="Ortalama sıcaklık (Santigrat)")

class HourlyForecast(BaseModel):
    hour: int
    expected_power_kw: float

class ForecastResult(BaseModel):
    recommendation: str
    reasoning: str
    forecast_48h: list[HourlyForecast]

class ForecastResponse(BaseModel):
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None
