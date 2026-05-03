# Yenilenebilir Enerji Karar Destek Sistemi - Agent Dokümantasyonu

Bu doküman, "02 // Yenilenebilir Enerji Tahmini ve Analizi" hackathon projesinin Antigravity üzerinde geliştirilmesi için gerekli olan ajan (agent) mimarisini ve yazılımsal özelliklerini tanımlar.

## Sistem Mimarisi Özeti
Sistem 5 temel ajandan oluşmaktadır. Ajanlar, veri toplama, makine öğrenmesi tahmini, coğrafi analiz, backend orkestrasyonu ve frontend (arayüz) geliştirme görevlerini üstlenir.

---

### 1. Data Ingestion Agent (Veri Toplama ve İşleme Ajanı)
**Rol:** Dış kaynaklardan (meteoroloji API'leri, güneş/rüzgar potansiyel verileri) verileri çekmek, temizlemek ve yapılandırmak.
*   **Kullanılan Teknolojiler:** Python 3.11, `httpx`, `Pydantic v2`
*   **Girdiler:** Koordinat bilgileri (Enlem/Boylam), Tarih/Saat aralığı.
*   **Çıktılar:** Temizlenmiş ve doğrulanmış JSON verisi. Pydantic şemalarından geçmiş yapılandırılmış data.
*   **Sorumluluklar:**
    *   `httpx` kullanarak asenkron dış API çağrıları yapmak (örneğin OpenMeteo veya benzeri ücretsiz servisler).
    *   Eksik verileri (NaN) NumPy ile saptamak ve doldurmak.
    *   Verileri `SQLite` önbelleğine (cache) yazmak ve aynı veriler için API isteklerini minimize etmek.

### 2. Forecasting Agent (Tahmin ve ML Ajanı)
**Rol:** Geçmiş verileri ve anlık hava durumunu kullanarak 48 saatlik üretim tahminlemesi yapmak.
*   **Kullanılan Teknolojiler:** Python 3.11, `Prophet` (opsiyonel/öncelikli), `NumPy`
*   **Girdiler:** Data Ingestion Agent'tan gelen zaman serisi (time-series) verileri.
*   **Çıktılar:** 48 saatlik (saatlik kırılımda) enerji üretim tahmin değerleri (JSON formatında).
*   **Sorumluluklar:**
    *   Güneş (Işınım) ve Rüzgar (Hız/Yön) verilerini baz alarak teorik enerji üretimini hesaplamak.
    *   Hızlı sonuç için Prophet modelini fit etmek ve gelecekteki 48 saat için `predict` fonksiyonunu çalıştırmak.

### 3. GeoSpatial Agent (Coğrafi Analiz ve Haritalama Ajanı)
**Rol:** Türkiye haritası üzerindeki yatırım uygunluk skorlarını (0-100 arası) hesaplamak ve harita arayüzünün anlayacağı formata çevirmek.
*   **Kullanılan Teknolojiler:** Python 3.11, `Pydantic v2`
*   **Girdiler:** Bölgesel enerji potansiyeli verileri, Türkiye sınırları poligon verileri.
*   **Çıktılar:** `GeoJSON` formatında, renk skalasına (heatmap) uygun ağırlıklandırılmış poligon veya nokta verileri.
*   **Sorumluluklar:**
    *   Rüzgar ve Güneş yatırımı için bölgelere özel "Yatırım Uygunluk Skoru" algoritmasını çalıştırmak.
    *   Frontend Leaflet kütüphanesinin doğrudan okuyup render edebileceği `FeatureCollection` tipinde GeoJSON üretmek.

### 4. API Orchestrator Agent (Backend Orkestrasyon Ajanı)
**Rol:** Tüm backend ajanlarını bir araya getiren ve Frontend'e veri sunan ana sunucu.
*   **Kullanılan Teknolojiler:** Python 3.11, `FastAPI`, `SQLite`
*   **Girdiler:** Frontend'den gelen HTTP GET/POST istekleri.
*   **Çıktılar:** RESTful API Endpoint yanıtları (JSON/GeoJSON).
*   **Sorumluluklar:**
    *   `/api/v1/forecast/{region}`: 48 saatlik tahmin verisini dönmek.
    *   `/api/v1/map/suitability`: GeoJSON yatırım haritasını dönmek.
    *   Veritabanı (`SQLite`) bağlantılarını yönetmek ve cache mekanizmasını kontrol etmek.
    *   CORS ayarlarını yaparak Frontend'in sorunsuz iletişim kurmasını sağlamak.

### 5. Frontend UI/UX Agent (Arayüz Geliştirme Ajanı)
**Rol:** Kullanıcının etkileşime gireceği etkileşimli, hızlı ve modern arayüzü inşa etmek.
*   **Kullanılan Teknolojiler:** React + Vite + TypeScript, TailwindCSS, `Leaflet` + `react-leaflet`, `Recharts`, `Zustand` (veya hızlı prototipleme için `Streamlit`).
*   **Girdiler:** API Orchestrator Agent'tan gelen uç nokta (endpoint) verileri, Kullanıcı tıklama/seçim olayları.
*   **Çıktılar:** DOM üzerinde render edilmiş interaktif web sayfası.
*   **Sorumluluklar:**
    *   **Harita Görünümü:** `react-leaflet` kullanarak Türkiye haritasını çizmek ve `GeoJSON` verisini katman olarak eklemek.
    *   **Grafikler:** Bölge seçildiğinde alt kısımda `Recharts` ile 48 saatlik üretim tahminini çizgi/bar grafik olarak göstermek.
    *   **Durum Yönetimi:** `Zustand` ile seçili bölge, yüklenme (loading) durumu ve hata yönetimini (state management) global olarak tutmak.
    *   **Tasarım:** `TailwindCSS` ile modern, karanlık/aydınlık mod destekli, temiz bir dashboard tasarlamak. *(Not: Eğer Streamlit kullanılacaksa, bu görev Python tarafında Streamlit componentleri ile hızlıca arayüz çizmeye kaydırılmalıdır).*

---

## Veri Akışı ve Entegrasyon Süreci (Workflow)
1. **Kullanıcı Etkileşimi:** Kullanıcı arayüze girer ve Türkiye haritası üzerinden bir il/bölge seçer. (Ajan 5)
2. **İstek Atılması:** Frontend, seçilen bölgenin koordinatlarını FastAPI'ye (`/api/v1/forecast`) gönderir. (Ajan 5 -> Ajan 4)
3. **Veri Kontrolü & Çekimi:** FastAPI, verinin `SQLite` cache'inde olup olmadığına bakar. Yoksa Data Ingestion Agent'ı tetikler. (Ajan 4 -> Ajan 1)
4. **Tahminleme:** Çekilen veri Forecasting Agent'a yollanır, Prophet ile 48 saatlik tahmin üretilir. (Ajan 1 -> Ajan 2)
5. **Görselleştirme:** FastAPI veriyi JSON olarak Frontend'e döner, Frontend bu veriyi Recharts ile grafiğe döker. (Ajan 4 -> Ajan 5)