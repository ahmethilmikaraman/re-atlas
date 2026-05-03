from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api import forecast_router
from contextlib import asynccontextmanager
import os
import subprocess
import sys

# Startup logic for heatmap generation
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Uygulama başlarken ısı haritalarını otomatik üret
    print("RE-Atlas: Isı haritaları otomatik üretiliyor...")
    try:
        script_path = os.path.join(os.path.dirname(__file__), "scripts", "generate_heatmaps.py")
        # Alt süreç olarak çalıştırarak import hatalarından kaçınalım
        subprocess.run([sys.executable, script_path], check=True)
        print("RE-Atlas: Isı haritaları başarıyla güncellendi.")
    except Exception as e:
        print(f"RE-Atlas: Isı haritası üretilirken hata oluştu: {e}")
    
    yield
    # Shutdown logic (optional)
    print("RE-Atlas: Backend kapatılıyor...")

app = FastAPI(title="RE-Atlas Backend API", version="1.0.0", lifespan=lifespan)

# Frontend'in sorunsuz istek atabilmesi için CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router'ları ana uygulamaya bağla
app.include_router(forecast_router.router)

@app.get("/")
def read_root():
    return {"message": "RE-Atlas Backend API Çalışıyor"}
