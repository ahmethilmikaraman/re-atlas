import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMapEvents, useMap, Polygon, ImageOverlay, CircleMarker, Tooltip } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import * as turf from '@turf/turf';
import { getForecast, getGridAnalysis } from '../api';
import { TrendingUp } from 'lucide-react';

// Alan noktalarının ağırlık merkezini (centroid) hesaplar
const calcCentroid = (points: [number, number][]): [number, number] => {
  const lat = points.reduce((sum, p) => sum + p[0], 0) / points.length;
  const lon = points.reduce((sum, p) => sum + p[1], 0) / points.length;
  return [lat, lon];
};

// Poligon alanını (Shoelace formülü) hesaplar — km² cinsinden yaklaşık değer
const calcAreaKm2 = (points: [number, number][]): number => {
  if (points.length < 3) return 0;
  const R = 6371; // km
  const toRad = (d: number) => d * Math.PI / 180;
  let area = 0;
  const n = points.length;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    const xi = toRad(points[i][1]) * Math.cos(toRad(points[i][0]));
    const xj = toRad(points[j][1]) * Math.cos(toRad(points[j][0]));
    const yi = toRad(points[i][0]);
    const yj = toRad(points[j][0]);
    area += (xj - xi) * (yj + yi);
  }
  return Math.abs(area / 2) * R * R;
};

// React-Leaflet için özel turuncu ve şimşekli ikon
const customMarkerHtml = `
  <div style="display: flex; flex-direction: column; align-items: center; filter: drop-shadow(0px 4px 4px rgba(0,0,0,0.4));">
    <div style="width: 36px; height: 36px; background-color: #f97316; border-radius: 50%; border: 3px solid white; display: flex; align-items: center; justify-content: center; z-index: 10;">
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="white" stroke="white" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
      </svg>
    </div>
    <div style="width: 0; height: 0; border-left: 6px solid transparent; border-right: 6px solid transparent; border-top: 10px solid #f97316; margin-top: -1px;"></div>
  </div>
`;

const OrangeBoltIcon = L.divIcon({
  html: customMarkerHtml,
  className: '',
  iconSize: [36, 46],
  iconAnchor: [18, 46],
  popupAnchor: [0, -46],
});

// Alan seçim noktası ikonu: numaralı, beyaz kenarlı turuncu daire
const makeAreaVertexIcon = (index: number) => L.divIcon({
  html: `
    <div style="
      width: 28px; height: 28px;
      background: #f97316;
      border: 3px solid white;
      border-radius: 50%;
      box-shadow: 0 0 0 2px #f97316, 0 4px 12px rgba(0,0,0,0.5);
      display: flex; align-items: center; justify-content: center;
      color: white; font-weight: 800; font-size: 12px;
      cursor: grab;
      font-family: sans-serif;
    ">${index + 1}</div>
  `,
  className: '',
  iconSize: [28, 28],
  iconAnchor: [14, 14],
  popupAnchor: [0, -16],
});

interface MapAreaProps {
  center: [number, number];
  provinceName: string;
  showAnalysis: boolean;
  activeLayer: 'normal' | 'solar' | 'wind';
  onAnalysisReady: (forecastData: any, areaPoints: [number, number][], areaKm2: number) => void;
  onCloseAnalysis: () => void;
}

interface ForecastData {
  status: string;
  data: {
    latitude: number;
    longitude: number;
    weather: {
      wind_speed_m_s: number;
      solar_irradiation_w_m2: number;
      temperature_c: number;
    };
    forecast: {
      recommendation: string;
      reasoning: string;
      hourly_power_generation_kw: number[];
    };
  }
}

const ClickHandler = ({ onMapClick }: { onMapClick: (lat: number, lon: number) => void }) => {
  useMapEvents({
    click(e) {
      onMapClick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
};

// Harita olaylarını (zoom vb.) takip eden bileşen
const MapEventsTracker = ({ setZoom }: { setZoom: (z: number) => void }) => {
  const map = useMapEvents({
    zoomend() {
      setZoom(map.getZoom());
    },
  });
  return null;
};

// Taşınabilir alan noktası marker'ı
const DraggableAreaMarker = ({
  position, index, onDragEnd
}: {
  position: [number, number];
  index: number;
  onDragEnd: (index: number, lat: number, lon: number) => void;
}) => {
  const markerRef = React.useRef<any>(null);

  const eventHandlers = React.useMemo(() => ({
    dragend() {
      const marker = markerRef.current;
      if (marker) {
        const latlng = marker.getLatLng();
        onDragEnd(index, latlng.lat, latlng.lng);
      }
    },
  }), [index, onDragEnd]);

  return (
    <Marker
      draggable={true}
      eventHandlers={eventHandlers}
      position={position}
      icon={makeAreaVertexIcon(index)}
      ref={markerRef}
    />
  );
};

const MapMover = ({ center, clickedPos }: { center: [number, number], clickedPos: [number, number] | null }) => {
  const map = useMap();
  useEffect(() => {
    if (clickedPos) {
      map.flyTo(clickedPos, 14, { duration: 1.5 });
    } else {
      map.flyTo(center, 10, { duration: 1.5 });
    }
  }, [center, clickedPos, map]);
  return null;
};

// Harita fitBounds'u sadece istendiğinde (fitTrigger değişince) çalıştırır.
// useRef ile showAnalysis ve areaPoints'ı her zaman güncel okur (stale closure olmaz)
const MapResizer = ({
  showAnalysis, areaPoints, fitTrigger
}: {
  showAnalysis: boolean;
  areaPoints: [number, number][];
  fitTrigger: number;
}) => {
  const map = useMap();
  // Her render'da ref'leri güncelle — effect kapanımı değil, ref okunur
  const showRef = React.useRef(showAnalysis);
  const ptsRef = React.useRef(areaPoints);
  showRef.current = showAnalysis;
  ptsRef.current = areaPoints;

  useEffect(() => {
    if (fitTrigger === 0) return;
    const timer = setTimeout(() => {
      map.invalidateSize({ animate: false });
      const pts = ptsRef.current;
      if (pts.length >= 2) {
        const bounds = L.latLngBounds(pts.map(p => L.latLng(p[0], p[1])));
        if (showRef.current) {
          // Panel sağda açık → sol yarıya sığdır
          const mapWidth = map.getSize().x;
          map.fitBounds(bounds, {
            paddingTopLeft: [60, 60],
            paddingBottomRight: [Math.round(mapWidth * 0.55), 60],
            animate: true,
          });
        } else {
          map.fitBounds(bounds, { padding: [60, 60], animate: true });
        }
      }
    }, 520);
    return () => clearTimeout(timer);
  }, [fitTrigger]); // ONLY fitTrigger — stale closure riski yok
  return null;
};

// Alan için özel merkez (centroid) ikonu — analiz yapıldıktan sonra
const CentroidIcon = L.divIcon({
  html: `<div style="width:18px;height:18px;background:#22c55e;border:3px solid white;border-radius:50%;box-shadow:0 0 10px rgba(34,197,94,0.8)"></div>`,
  className: '',
  iconSize: [18, 18],
  iconAnchor: [9, 9],
  popupAnchor: [300, 0],
});

// Alan merkezinde tıklanabilir yeşil analiz butonu (3+ nokta seçildiğinde)
const makeCentroidBtn = (label: string, bg: string, glow: string) => L.divIcon({
  html: `
    <div style="display:flex;flex-direction:column;align-items:center;filter:drop-shadow(0 4px 8px rgba(0,0,0,0.5));cursor:pointer;">
      <div style="background:${bg};color:white;font-size:11px;font-weight:800;padding:5px 12px;border-radius:20px;border:2px solid white;white-space:nowrap;box-shadow:0 0 14px ${glow};">${label}</div>
      <div style="width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-top:8px solid ${bg};margin-top:-1px;"></div>
    </div>`,
  className: '',
  iconSize: [110, 36],
  iconAnchor: [55, 44],
  popupAnchor: [0, -44],
});
const CentroidAnalyzeIcon = makeCentroidBtn('🚀 Analiz Et', '#16a34a', 'rgba(34,197,94,0.7)');
const CentroidOpenIcon = makeCentroidBtn('📊 Paneli Aç', '#2563eb', 'rgba(59,130,246,0.7)');
const CentroidCloseIcon = makeCentroidBtn('✕ Kapat', '#64748b', 'rgba(100,116,139,0.5)');

export const MapArea: React.FC<MapAreaProps> = ({ center, provinceName, showAnalysis, activeLayer, onAnalysisReady, onCloseAnalysis }) => {
  const [clickedPos, setClickedPos] = useState<[number, number] | null>(null);
  const [forecastData, setForecastData] = useState<ForecastData | null>(null);
  const [loading, setLoading] = useState(false);

  // Mod Yönetimi
  const [selectionMode, setSelectionMode] = useState<'single' | 'area'>('single');
  const [areaPoints, setAreaPoints] = useState<[number, number][]>([]);
  const [centroid, setCentroid] = useState<[number, number] | null>(null);
  const [areaAnalysisData, setAreaAnalysisData] = useState<ForecastData | null>(null);
  const [areaLoading, setAreaLoading] = useState(false);
  const [areaKm2, setAreaKm2] = useState<number>(0);
  const [fitTrigger, setFitTrigger] = useState(0); // artar → fitBounds tetiklenir
  const [gridPoints, setGridPoints] = useState<any[]>([]); // Analiz sonrası gelen verili noktalar
  const [gridLoading, setGridLoading] = useState(false);
  const [gridStep, setGridStep] = useState<number>(1);
  const [currentZoom, setCurrentZoom] = useState(6); // Varsayılan zoom seviyesi
  const [maskCoords, setMaskCoords] = useState<any[]>([]);
  const [showCoordinates, setShowCoordinates] = useState(true); // Koordinat gösterim toggle

  // İl değiştiğinde tüm state'leri sıfırla
  useEffect(() => {
    setClickedPos(null);
    setForecastData(null);
    setAreaPoints([]);
    setCentroid(null);
    setAreaAnalysisData(null);
  }, [center]);

  // Alan noktaları değiştikçe canlı alan (km²) hesapla
  useEffect(() => {
    if (areaPoints.length >= 3) {
      setAreaKm2(parseFloat(calcAreaKm2(areaPoints).toFixed(2)));
    } else {
      setAreaKm2(0);
    }
  }, [areaPoints]);

  // Türkiye Maskesi (Inverted Polygon) için GeoJSON yükle
  useEffect(() => {
    fetch('/turkey.json')
      .then(res => res.json())
      .then(geoJson => {
        const worldCoords = [[90, -180], [90, 180], [-90, 180], [-90, -180]];
        const holes: any[] = [];

        // GeoJSON yapısına göre (FeatureCollection veya Feature) koordinatları ayıkla
        const features = geoJson.features || [geoJson];
        
        features.forEach((feature: any) => {
          const { type, coordinates } = feature.geometry;
          if (type === 'Polygon') {
            coordinates.forEach((ring: any) => {
              holes.push(ring.map((c: any) => [c[1], c[0]]));
            });
          } else if (type === 'MultiPolygon') {
            coordinates.forEach((polygon: any) => {
              polygon.forEach((ring: any) => {
                holes.push(ring.map((c: any) => [c[1], c[0]]));
              });
            });
          }
        });

        setMaskCoords([worldCoords, ...holes]);
      })
      .catch(err => console.error("Turkey Mask GeoJSON Error:", err));
  }, []);

  const handleMapClick = async (lat: number, lon: number) => {
    if (selectionMode === 'single') {
      setClickedPos([lat, lon]);
      setLoading(true);
      const data = await getForecast(lat, lon);
      setForecastData(data);
      setLoading(false);
    } else {
      // Önceki analiz varsa yeni alan için sıfırla
      if (centroid) {
        setCentroid(null);
        setAreaAnalysisData(null);
        setAreaPoints([[lat, lon]]);
        onCloseAnalysis();
      } else {
        setAreaPoints(prev => [...prev, [lat, lon]]);
      }
    }
  };

  const handlePopupClose = () => {
    setClickedPos(null);
    setForecastData(null);
  };

  const handleAreaPopupClose = () => {
    setCentroid(null);
    setAreaAnalysisData(null);
    setAreaPoints([]);
    setGridPoints([]);
  };

  // Alanı analiz et: Izgara oluştur, toplu veri oku, sonucu App'e ilet
  const handleAnalyzeArea = async () => {
    if (areaPoints.length < 3) return;

    setAreaLoading(true);
    setGridLoading(true);
    setAreaAnalysisData(null);

    // 1. Turf ile Poligon ve Alan Hesaplama
    const polygonCoords = [...areaPoints, areaPoints[0]].map(p => [p[1], p[0]]); // [lon, lat]
    const poly = turf.polygon([polygonCoords]);
    const areaM2 = turf.area(poly);
    const areaKm2Val = areaM2 / 1000000;
    setAreaKm2(parseFloat(areaKm2Val.toFixed(2)));

    // 2. Dinamik Grid Aralığı (Step) Belirleme
    let step = 1; // km
    if (areaKm2Val < 1) step = 0.05;      // 50m
    else if (areaKm2Val < 10) step = 0.2; // 200m
    else if (areaKm2Val < 100) step = 0.5; // 500m
    else step = 2;                        // 2km
    setGridStep(step);

    // 3. Grid Noktalarını Oluştur ve Filtrele
    const bbox = turf.bbox(poly);
    let grid = turf.pointGrid(bbox, step, { units: 'kilometers' });

    // Sadece poligon içindekileri al
    const pointsInside = grid.features.filter(f => turf.booleanPointInPolygon(f, poly));

    // Maksimum 1000 nokta sınırı
    const finalPoints = pointsInside.slice(0, 1000).map(f => ({
      lat: f.geometry.coordinates[1],
      lon: f.geometry.coordinates[0]
    }));

    // 4. Backend'e Toplu İstek At
    const response = await getGridAnalysis(finalPoints);

    if (response && response.status === 'ok') {
      setAreaAnalysisData(response);
      setGridPoints(response.data.points_data);
      setCentroid(calcCentroid(areaPoints));
      setFitTrigger(t => t + 1);
      onAnalysisReady(response, areaPoints, areaKm2Val);
    }

    setAreaLoading(false);
    setGridLoading(false);
  };

  // Tüm alan seçimlerini ve analizleri temizle
  const handleClearArea = () => {
    setAreaPoints([]);
    setGridPoints([]);
    setAreaAnalysisData(null);
    setCentroid(null);
    setAreaKm2(0);
    onCloseAnalysis();
  };

  // Centroid butonuna tıklama: analiz et VEYA paneli aç/kapat
  const handleCentroidClick = React.useCallback(() => {
    if (!centroid) {
      // İlk analiz: fitTrigger handleAnalyzeArea içinde artar
      handleAnalyzeArea();
    } else if (showAnalysis) {
      // Panel açık → kapat
      onCloseAnalysis();
    } else {
      // Panel kapalı → aç + haritayı sola sabitle (fitTrigger artır)
      setFitTrigger(t => t + 1);
      onAnalysisReady(areaAnalysisData, areaPoints, areaKm2);
    }
  }, [centroid, showAnalysis, areaAnalysisData, areaPoints, areaKm2]);

  // Vertex sürüklendiğinde o noktanın koordinatını güncelle
  const handleVertexDrag = React.useCallback((index: number, lat: number, lon: number) => {
    setAreaPoints(prev => {
      const updated = [...prev];
      updated[index] = [lat, lon];
      return updated;
    });
  }, []);

  // --- Koordinat giriş paneli state ---
  const [coordInput, setCoordInput] = useState({ lat: '', lon: '' });

  const handleGoToCoord = () => {
    const lat = parseFloat(coordInput.lat);
    const lon = parseFloat(coordInput.lon);
    if (isNaN(lat) || isNaN(lon)) return;
    handleMapClick(lat, lon);
    setCoordInput({ lat: '', lon: '' });
  };

  // Alan modunda belirli bir noktanın koordinatını input'tan güncelle
  const handleAreaPointEdit = (index: number, field: 'lat' | 'lon', value: string) => {
    const num = parseFloat(value);
    if (isNaN(num)) return;
    setAreaPoints(prev => {
      const updated = [...prev];
      updated[index] = field === 'lat' ? [num, updated[index][1]] : [updated[index][0], num];
      return updated;
    });
  };

  // Türkiye Sınırları (maxBounds)
  const turkeyBounds: L.LatLngBoundsExpression = [[42.63, 24.], [34.5, 46.61]];

  return (
    <div className="w-full h-full relative z-0">
      <MapContainer
        center={center}
        zoom={6}
        minZoom={6}
        maxBounds={turkeyBounds}
        maxBoundsViscosity={1.0}
        zoomControl={false}
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* Türkiye Dışını Karartan Maske (Inverted Polygon) */}
        {maskCoords.length > 0 && (
          <Polygon
            positions={maskCoords}
            pathOptions={{
              fillColor: '#000000',
              fillOpacity: 0.6,
              stroke: false,
              interactive: false
            }}
          />
        )}

        {/* Heatmap Overlays */}
        {activeLayer === 'solar' && (
          <ImageOverlay
            url="/solar_heatmap.png"
            bounds={[[35.0, 25.0], [43.0, 45.0]]}
            opacity={0.8}
            zIndex={1000}
          />
        )}
        {activeLayer === 'wind' && (
          <ImageOverlay
            url="/wind_heatmap.png"
            bounds={[[34.18875, 25.42125], [43.47125, 44.83875]]}
            opacity={0.8}
            zIndex={1000}
          />
        )}

        {/* Harita resize + fitBounds yöneticisi — sadece fitTrigger artınca çalışır */}
        <MapResizer showAnalysis={showAnalysis} areaPoints={areaPoints} fitTrigger={fitTrigger} />
        {/* Harita uçuş (flyTo) yöneticisi */}
        <MapMover center={center} clickedPos={clickedPos} />
        {/* Tıklama olayları */}
        <ClickHandler onMapClick={handleMapClick} />
        {/* Zoom takibi */}
        <MapEventsTracker setZoom={setCurrentZoom} />

        {/* Çizilen Poligon */}
        {selectionMode === 'area' && areaPoints.length > 1 && (
          <Polygon positions={areaPoints} color="#f97316" fillColor="#f97316" fillOpacity={0.2} weight={2.5} dashArray="6" />
        )}

        {/* Taşınabilir vertex marker'lar */}
        {selectionMode === 'area' && areaPoints.map((pos, idx) => (
          <DraggableAreaMarker
            key={idx}
            index={idx}
            position={pos}
            onDragEnd={handleVertexDrag}
          />
        ))}

        {/* Birleşik centroid butonu: analiz yap / paneli aç / paneli kapat */}
        {selectionMode === 'area' && areaPoints.length >= 3 && (
          <Marker
            position={centroid ?? calcCentroid(areaPoints)}
            icon={
              !centroid ? CentroidAnalyzeIcon :
                showAnalysis ? CentroidCloseIcon :
                  CentroidOpenIcon
            }
            eventHandlers={{ click: handleCentroidClick }}
          />
        )}

        {/* Centroid marker ve alan analizi popup'ı */}
        {centroid && (
          <Marker position={centroid} icon={CentroidIcon}>
            <Popup className="custom-popup" autoPan={false} offset={[300, 0]} onClose={handleAreaPopupClose}>
              {areaLoading ? (
                <div className="p-4 flex flex-col items-center justify-center min-w-[240px]">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-500 mb-2"></div>
                  <span className="text-sm text-slate-600">Alan analiz ediliyor...</span>
                </div>
              ) : areaAnalysisData?.data ? (
                <div className="min-w-[300px]">
                  <div className="border-b-2 border-green-500 pb-2 mb-3">
                    <h4 className="text-lg font-bold text-slate-800 m-0">📐 Alan Analizi</h4>
                    <span className="text-xs text-slate-500">{areaPoints.length} nokta · {areaKm2} km²</span>
                  </div>

                  <div className="mb-3 text-sm text-slate-600">
                    <div className="grid grid-cols-2 gap-2">
                      <div><b>Merkez Enlem:</b> {areaAnalysisData?.data?.latitude !== undefined ? areaAnalysisData.data.latitude.toFixed(4) : '—'}</div>
                      <div><b>Merkez Boylam:</b> {areaAnalysisData?.data?.longitude !== undefined ? areaAnalysisData.data.longitude.toFixed(4) : '—'}</div>
                    </div>
                  </div>

                  <div className="bg-slate-50 p-3 rounded-lg border-l-4 border-green-500 mb-4 shadow-sm">
                    <b className="text-green-600 block text-[10px] uppercase tracking-wider mb-1">Genel Tavsiye</b>
                    <span className="text-base font-bold text-slate-800 block">{areaAnalysisData.data.general_recommendation}</span>
                    <div className="mt-2 pt-2 border-t border-slate-200">
                      <b className="text-indigo-600 block text-[10px] uppercase tracking-wider mb-1">En Verimli Nokta (Sweet Spot)</b>
                      <span className="text-xs text-slate-600">
                        📍 {areaAnalysisData?.data?.sweet_spot?.lat !== undefined ? areaAnalysisData.data.sweet_spot.lat.toFixed(4) : '—'},
                        {areaAnalysisData?.data?.sweet_spot?.lon !== undefined ? areaAnalysisData.data.sweet_spot.lon.toFixed(4) : '—'} <br />
                        <span className="text-orange-600 font-bold">☀️ {areaAnalysisData?.data?.sweet_spot?.solar ?? '—'}</span> ·
                        <span className="text-blue-600 font-bold ml-1">💨 {areaAnalysisData?.data?.sweet_spot?.wind ?? '—'}</span>
                      </span>
                    </div>
                  </div>

                  <div className="flex justify-between border-t border-slate-200 pt-3 bg-slate-50/50 rounded-b-lg -mx-2 -mb-2 p-3">
                    <div className="text-sm">
                      <b className="text-slate-600 text-xs">☀️ Ort. Güneş</b> <br />
                      <span className="text-orange-600 font-bold text-lg">{areaAnalysisData?.data?.area_summary?.avg_solar ?? '—'}</span>
                      <span className="text-xs text-slate-400 ml-1">W/m²</span>
                    </div>
                    <div className="text-sm text-right">
                      <b className="text-slate-600 text-xs">💨 Ort. Rüzgar</b> <br />
                      <span className="text-blue-600 font-bold text-lg">{areaAnalysisData?.data?.area_summary?.avg_wind ?? '—'}</span>
                      <span className="text-xs text-slate-400 ml-1">m/s</span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-4 text-center">
                  <span className="text-red-500 font-medium">Veri alınamadı.</span>
                </div>
              )}
            </Popup>
          </Marker>
        )}

        {/* Tek nokta modu markeri */}
        {selectionMode === 'single' && clickedPos && (
          <Marker position={clickedPos} icon={OrangeBoltIcon}>
            <Popup className="custom-popup" autoPan={false} offset={[300, 150]} onClose={handlePopupClose}>
              {loading ? (
                <div className="p-4 flex flex-col items-center justify-center min-w-[200px]">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mb-2"></div>
                  <span className="text-sm text-slate-600">Ajanlar veri topluyor...</span>
                </div>
              ) : forecastData?.data ? (
                <div className="min-w-[300px]">
                  <div className="border-b-2 border-blue-500 pb-2 mb-3">
                    <h4 className="text-lg font-bold text-slate-800 m-0">📍 Konum Analizi</h4>
                    <span className="text-xs text-slate-500">Tekil Nokta Verisi</span>
                  </div>

                  <div className="mb-3 text-sm text-slate-600">
                    <div className="grid grid-cols-2 gap-2">
                      <div><b>Enlem:</b> {forecastData?.data?.latitude !== undefined ? forecastData.data.latitude.toFixed(4) : '—'}</div>
                      <div><b>Boylam:</b> {forecastData?.data?.longitude !== undefined ? forecastData.data.longitude.toFixed(4) : '—'}</div>
                    </div>
                  </div>

                  <div className="bg-slate-50 p-3 rounded-lg border-l-4 border-blue-500 mb-4 shadow-sm">
                    <b className="text-blue-600 block text-[10px] uppercase tracking-wider mb-1">Tavsiye Edilen Sistem</b>
                    <span className="text-base font-bold text-slate-800 block">{forecastData.data.recommendation}</span>
                    <p className="text-xs text-slate-500 mt-1 mb-0 leading-relaxed">{forecastData.data.reason}</p>
                  </div>

                  <div className="flex justify-between border-t border-slate-200 pt-3 bg-slate-50/50 rounded-b-lg -mx-2 -mb-2 p-3 flex-wrap gap-y-3">
                    <div className="text-sm">
                      <b className="text-slate-600 text-xs">☀️ Güneş</b> <br />
                      <span className="text-orange-600 font-bold text-lg">{forecastData?.data?.solar_ghi ?? '—'}</span>
                      <span className="text-xs text-slate-400 ml-1">W/m²</span>
                    </div>
                    <div className="text-sm text-right">
                      <b className="text-slate-600 text-xs">💨 Rüzgar</b> <br />
                      <span className="text-blue-600 font-bold text-lg">{forecastData?.data?.wind_speed ?? '—'}</span>
                      <span className="text-xs text-slate-400 ml-1">m/s</span>
                    </div>
                    
                    <button
                      onClick={() => onAnalysisReady(forecastData, [[forecastData.data.latitude, forecastData.data.longitude]], 0)}
                      className="w-full mt-2 py-2 bg-blue-600 hover:bg-blue-700 text-white text-[11px] font-bold rounded-lg transition-all shadow-md flex items-center justify-center gap-2 group"
                    >
                      <TrendingUp size={14} className="group-hover:scale-110 transition-transform" /> 
                      Detaylı Analiz Raporunu Aç
                    </button>
                  </div>
                </div>
              ) : (
                <div className="p-4 text-center">
                  <span className="text-red-500 font-medium">Veri alınamadı.</span>
                </div>
              )}
            </Popup>
          </Marker>
        )}
        {/* Izgara (Grid) Noktaları */}
        {gridPoints.map((pt, idx) => (
          <CircleMarker
            key={`grid-${idx}`}
            center={[pt.lat, pt.lon]}
            radius={4}
            pathOptions={{
              color: '#94a3b8',
              fillColor: '#94a3b8',
              fillOpacity: 0.4,
              weight: 1
            }}
            eventHandlers={{
              mouseover: (e) => {
                const layer = e.target;
                layer.setStyle({
                  fillColor: '#fbbf24',
                  color: '#fbbf24',
                  fillOpacity: 1,
                  radius: 7
                });
              },
              mouseout: (e) => {
                const layer = e.target;
                layer.setStyle({
                  fillColor: '#94a3b8',
                  color: '#94a3b8',
                  fillOpacity: 0.4,
                  radius: 4
                });
              }
            }}
          >
            <Tooltip direction="top" offset={[0, -5]} opacity={0.9}>
              <div className="p-1 font-sans">
                <div className="text-[10px] font-bold text-slate-500 uppercase">Noktasal Veri</div>
                <div className="flex gap-3 mt-1">
                  <span className="text-orange-600 font-bold">☀️ {pt.solar} <small>W/m²</small></span>
                  <span className="text-blue-600 font-bold">💨 {pt.wind} <small>m/s</small></span>
                </div>
              </div>
            </Tooltip>
          </CircleMarker>
        ))}

      </MapContainer>

      {/* Yüzen Kontrol Paneli */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-[2000] flex flex-col items-center gap-3 opacity-40 hover:opacity-100 transition-opacity duration-300">

        {/* Alan modu aktifken: nokta sayısı ve alan bilgisi badge'i */}
        {selectionMode === 'area' && areaPoints.length > 0 && (
          <div className="bg-orange-600/90 backdrop-blur-sm text-white text-xs font-bold px-4 py-2 rounded-full flex items-center gap-3 shadow-lg">
            <span>🔴 {areaPoints.length} nokta seçildi</span>
            {areaKm2 > 0 && <span>≈ {areaKm2} km²</span>}
            <button
              onClick={() => setAreaPoints(prev => prev.slice(0, -1))}
              className="bg-white/20 hover:bg-white/40 rounded-full px-2 py-0.5 transition-colors"
            >
              ↩ Geri Al
            </button>
            <button
              onClick={handleClearArea}
              className="bg-red-500 hover:bg-red-400 rounded-full px-3 py-0.5 transition-colors shadow-lg flex items-center gap-1"
            >
              <span className="font-bold">✕</span> Temizle
            </button>
          </div>
        )}

        <div className="bg-slate-900/80 backdrop-blur-md p-2 rounded-2xl shadow-[0_4px_30px_rgba(0,0,0,0.5)] border border-slate-700/50 flex gap-2">
          <button
            onClick={() => { setSelectionMode('single'); setAreaPoints([]); setCentroid(null); setAreaAnalysisData(null); }}
            className={`px-5 py-2.5 rounded-xl text-sm font-bold transition-all ${selectionMode === 'single' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-400 hover:bg-slate-800 hover:text-white'}`}
          >
            📍 Tek Konum
          </button>
          <button
            onClick={() => { setSelectionMode('area'); setClickedPos(null); setForecastData(null); setCentroid(null); setAreaAnalysisData(null); }}
            className={`px-5 py-2.5 rounded-xl text-sm font-bold transition-all ${selectionMode === 'area' ? 'bg-orange-600 text-white shadow-lg' : 'text-slate-400 hover:bg-slate-800 hover:text-white'}`}
          >
            📐 Alan Seç
          </button>
        </div>

        {/* 3+ nokta seçildiğinde alan analiz butonu */}
        {selectionMode === 'area' && areaPoints.length >= 3 && !centroid && (
          <button
            onClick={handleAnalyzeArea}
            className="bg-green-600 hover:bg-green-500 text-white px-8 py-3 rounded-full font-bold shadow-[0_0_20px_rgba(34,197,94,0.5)] hover:shadow-[0_0_30px_rgba(34,197,94,0.7)] transition-all animate-pulse"
          >
            🚀 Alanı Analiz Et
          </button>
        )}

        {/* Tek konum seçildiğinde analiz butonu */}
        {selectionMode === 'single' && clickedPos && forecastData && (
          <button
            onClick={() => onAnalysisReady(forecastData, [clickedPos], 0)}
            className="bg-blue-600 hover:bg-blue-500 text-white px-8 py-3 rounded-full font-bold shadow-[0_0_20px_rgba(59,130,246,0.5)] hover:shadow-[0_0_30px_rgba(59,130,246,0.7)] transition-all"
          >
            📊 Konumu Analiz Et
          </button>
        )}
      </div>

      {/* Sol alt — Koordinat Giriş Paneli */}
      <div className="absolute bottom-6 left-4 z-[2000] flex flex-col gap-2 opacity-50 hover:opacity-100 transition-opacity duration-300">
        <div className="bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-700/50 shadow-[0_4px_24px_rgba(0,0,0,0.5)] overflow-hidden">

          {/* Alan Modu: Her nokta için ayrı satır */}
          {showCoordinates && selectionMode === 'area' && areaPoints.length > 0 && (
            <div className="flex flex-col divide-y divide-slate-700/40 max-h-52 overflow-y-auto">
              {areaPoints.map((pt, idx) => (
                <div key={idx} className="flex items-center gap-1.5 px-3 py-2">
                  <span className="text-[10px] font-bold text-orange-400 w-5 shrink-0">{idx + 1}</span>
                  <input
                    type="number"
                    defaultValue={pt[0].toFixed(5)}
                    onBlur={e => handleAreaPointEdit(idx, 'lat', e.target.value)}
                    className="w-24 bg-slate-800/70 border border-slate-700/50 text-white text-xs rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-orange-500"
                    placeholder="Enlem"
                  />
                  <input
                    type="number"
                    defaultValue={pt[1].toFixed(5)}
                    onBlur={e => handleAreaPointEdit(idx, 'lon', e.target.value)}
                    className="w-24 bg-slate-800/70 border border-slate-700/50 text-white text-xs rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-orange-500"
                    placeholder="Boylam"
                  />
                  <button
                    onClick={() => setAreaPoints(prev => prev.filter((_, i) => i !== idx))}
                    className="text-slate-500 hover:text-red-400 transition-colors text-xs px-1"
                  >✕</button>
                </div>
              ))}
            </div>
          )}

          {/* Tek Konum Modu: Seçili konumun mevcut koordinatlarını göster */}
          {showCoordinates && selectionMode === 'single' && clickedPos && (
            <div className="flex items-center gap-2 px-3 py-2 border-b border-slate-700/40 bg-slate-800/40">
              <span className="text-[10px] font-bold text-blue-400 shrink-0">📍</span>
              <div className="flex gap-2 text-xs font-mono text-slate-200">
                <span className="bg-slate-700/60 rounded px-2 py-1">{clickedPos[0].toFixed(5)}</span>
                <span className="bg-slate-700/60 rounded px-2 py-1">{clickedPos[1].toFixed(5)}</span>
              </div>
              <button
                onClick={() => { setClickedPos(null); setForecastData(null); }}
                className="text-slate-500 hover:text-red-400 transition-colors text-xs px-1 ml-auto"
              >✕</button>
            </div>
          )}

          {/* Tek Konum veya Alan'da yeni nokta ekleme satırı */}
          <div className="flex items-center gap-2 px-3 py-2.5">
            <span className="text-[10px] font-bold text-slate-400 shrink-0">
              {selectionMode === 'single' ? '🔍' : '➕'}
            </span>
            <input
              type="number"
              value={coordInput.lat}
              onChange={e => setCoordInput(p => ({ ...p, lat: e.target.value }))}
              onKeyDown={e => e.key === 'Enter' && handleGoToCoord()}
              className="w-24 bg-slate-800/70 border border-slate-700/50 text-white text-xs rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="Enlem"
            />
            <input
              type="number"
              value={coordInput.lon}
              onChange={e => setCoordInput(p => ({ ...p, lon: e.target.value }))}
              onKeyDown={e => e.key === 'Enter' && handleGoToCoord()}
              className="w-24 bg-slate-800/70 border border-slate-700/50 text-white text-xs rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="Boylam"
            />
            <button
              onClick={handleGoToCoord}
              className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold px-3 py-1.5 rounded-lg transition-colors"
            >
              {selectionMode === 'single' ? '→ Git' : '+ Ekle'}
            </button>

            <div className="ml-auto pl-4 flex items-center gap-3 border-l border-slate-700/50">
              <button 
                onClick={() => setShowCoordinates(!showCoordinates)}
                className={`text-[10px] p-1 rounded transition-all duration-300 flex items-center justify-center w-6 h-6 ${showCoordinates ? 'text-blue-400 bg-blue-500/10' : 'text-slate-500 bg-slate-800'}`}
                title={showCoordinates ? "Gizle" : "Göster"}
              >
                <span className={`transition-transform duration-300 font-bold ${showCoordinates ? 'rotate-90' : ''}`}>
                  {'>'}
                </span>
              </button>
              <span className="text-[10px] font-bold text-slate-400 flex items-center gap-1">
                🔍 Zoom: <span className="text-white">{currentZoom}</span>
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
