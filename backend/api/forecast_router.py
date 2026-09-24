from fastapi import APIRouter
from backend.schemas import LocationRequest, ForecastResponse, GridAnalysisRequest
from backend.agents.data_ingestion import ingest_weather_data, ingest_bulk_weather_data
from backend.agents.forecaster import run_forecast, run_regional_analysis

router = APIRouter()

@router.post("/api/v1/forecast", response_model=ForecastResponse)
async def get_forecast(request: LocationRequest):
    weather_data = ingest_weather_data(request.latitude, request.longitude)
    forecast_result = run_forecast(weather_data)
    
    from backend.agents.forecaster import generate_forecast
    
    return ForecastResponse(
        status="ok",
        message="Veriler başarıyla analiz edildi.",
        data={
            "solar_ghi": weather_data.solar_irradiation_w_m2,
            "wind_speed": weather_data.wind_speed_m_s,
            "temperature_c": weather_data.temperature_c,
            "recommendation": forecast_result.recommendation,
            "general_recommendation": forecast_result.recommendation, # Normalize key
            "reason": forecast_result.reasoning,
            "forecast_24h": [h for h in generate_forecast(weather_data.solar_irradiation_w_m2, weather_data.wind_speed_m_s, 24)],
            "forecast_48h": [h for h in generate_forecast(weather_data.solar_irradiation_w_m2, weather_data.wind_speed_m_s, 48)],
            "latitude": weather_data.latitude,
            "longitude": weather_data.longitude
        }
    )

@router.post("/api/v1/grid-analysis", response_model=ForecastResponse)
async def get_grid_analysis(request: GridAnalysisRequest):
    """
    Poligon içindeki tüm ızgara noktaları için toplu analiz yapar.
    """
    # 1. Toplu Veri Okuma (Dosyaları sadece bir kez açar)
    weather_list = ingest_bulk_weather_data(request.points)
    
    # 2. Bölgesel Analiz (Ortalama, Sweet Spot, Tavsiye)
    analysis_result = run_regional_analysis(weather_list)
    
    return ForecastResponse(
        status="ok",
        message="Bölgesel ızgara analizi tamamlandı.",
        data=analysis_result
    )
