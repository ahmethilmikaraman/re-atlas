# Yenilenebilir Enerji Karar Destek Sistemi - Yazılım ve Mimari Dokümantasyonu

Bu doküman, "02 // Yenilenebilir Enerji Tahmini ve Analizi" projesinin temel kullanım senaryolarını, güncellenmiş Python odaklı teknoloji yığınını ve veri mimarisini tanımlar.

## 1. Temel Özellikler ve Kullanıcı Akışı (User Flow)

Sistem, kullanıcının makro ölçekten mikro ölçeğe inerek analiz yapmasını sağlayan etkileşimli bir harita deneyimi sunar.

*   **Hiyerarşik Coğrafi Görüntüleme:** 
    *   Kullanıcı sisteme girdiğinde tüm Türkiye haritasını ve genel enerji potansiyeli ısı haritasını (heatmap) görür.
    *   **Tıklama Akışı:** Bölge Seçimi (Zoom) -> İl Seçimi (Zoom & Sınır Çizimi) -> İlçe Seçimi (Zoom & Alt Sınır Çizimi).
*   **Grid (Izgara) Tabanlı Alan Seçimi:** 
    *   İlçe veya spesifik bir koordinat seviyesine inildiğinde, harita üzerinde belirli kilometrekarelik (örneğin 1x1 km veya Uber H3 altıgen gridleri) hücresel bir yapı belirir.
    *   Kullanıcı tek bir grid hücresi seçebilir veya çokgen (polygon) çizerek birden fazla grid alanını kapsayan bir bölgeyi işaretleyebilir.
*   **Yapay Zeka Destekli Yatırım Tavsiyesi (Karar Destek Motoru):**
    *   Seçilen grid hücrelerinin arkasındaki meteorolojik ve topografik mock datalar (Rüzgar hızı, güneş ışınımı, rakım, eğim vb.) modele beslenir.
    *   Sistem, seçilen alan için en uygun yenilenebilir enerji tipini (Güneş Paneli, Rüzgar Türbini veya Hibrit) gerekçeleriyle birlikte tavsiye eder ve 48 saatlik tahmini üretim simülasyonu sunar.

## 2. Teknoloji Yığını (Python/Streamlit Odaklı Revizyon)

Projenin hızlı ve Python temelli geliştirilebilmesi için teknoloji yığını aşağıdaki gibi standardize edilmiştir:

| Katman | Teknoloji / Kütüphane | Açıklama |
|--------|-----------------------|----------|
| **Arayüz (UI)** | `Streamlit` | Tüm front-end geliştirme süreci için ana framework. |
| **Haritalama** | `Folium` + `streamlit-folium` | Etkileşimli harita render işlemleri, grid çizimleri ve tıklama olayları (click events) için. |
| **State Management** | `st.session_state` | Seçili il, ilçe ve koordinat durumlarını sayfa yenilendiğinde kaybetmemek için Streamlit'in yerleşik durum yönetimi. |
| **Grafik / Çizim** | `Plotly` veya `Altair` | 48 saatlik üretim tahminlerini göstermek için interaktif grafikler. |
| **Backend** | Python 3.11 + `FastAPI` + `Pydantic v2` | Veri işleme, model servisi ve harita için GeoJSON uç noktaları sağlayan API katmanı. |
| **HTTP Client** | `httpx` | Asenkron dış veri veya mikroservis istekleri için. |
| **Makine Öğrenmesi** | `scikit-learn` (Sınıflandırma) + `Prophet` | Yatırım tipi tavsiyesi (Classification) ve 48 Saatlik Tahmin (Time-Series) için. `NumPy` ve `Pandas` destekli. |
| **Cache / DB** | `SQLite` + `st.cache_data` | Sunucu tarafı veri tabanı ve arayüz tarafı hızlı veri önbellekleme. |
| **Veri Formatı** | `GeoJSON`, JSON | Harita sınırları (poligonlar) ve API haberleşmesi için. |
| **Geliştirme** | Antigravity | Bulut tabanlı geliştirme ortamı ve agent mimarisi altyapısı. |

## 3. Veri Stratejisi ve Mock Data Yaklaşımı

Zaman kısıtı (25 saat) ve büyük veri setlerini eğitme zorunluluğu nedeniyle, sistem gerçek mimariyi simüle eden **Mock Data (Sahte Veri)** jeneratörleri ile çalışacaktır.

### Mock Data Üretim Senaryosu
Arayüzden seçilen her spesifik lokasyon (Enlem/Boylam) için `Data Ingestion Agent` anlık olarak deterministik (koordinata bağlı, her tıklandığında aynı sonucu veren) sahte veri üretecektir:
*   **Güneş Işınımı (GHI):** Güney enlemlere inildikçe artan, gece saatlerinde sıfırlanan sentetik bir zaman serisi.
*   **Rüzgar Hızı (m/s):** Rakıma ve kıyı şeridine yakınlığa bağlı olarak baz değeri belirlenen, üzerine rastgele gürültü (noise) eklenmiş veri.
*   **Topografya (Eğim/Rakım):** Coğrafi koordinata göre atanmış statik risk veya maliyet çarpanları.

### Model Entegrasyonu (Tavsiye Sistemi)
Gerçek bir derin öğrenme modeli eğitmek yerine, kural tabanlı (rule-based) ve basit bir Makine Öğrenmesi (Örn: Random Forest veya Karar Ağacı) modeli kullanılacaktır. 
*   **Girdi:** Mock üretilmiş `[Ortalama_Rüzgar, Ortalama_Güneş, Eğim, Kurulum_Alani_m2]`
*   **Çıktı Karar Sınırları:** 
    *   Rüzgar > 6.5 m/s ve Eğim < %15 ise -> **Rüzgar Türbini Tavsiyesi**
    *   Güneş Işınımı > Belirli bir eşik ve Alan geniş ise -> **GES Tavsiyesi**
    *   Her ikisi de yüksekse -> **Hibrit Sistem Tavsiyesi**