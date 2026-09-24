import React, { useState } from 'react';
import { X, Sun, Wind, Map, Layers, TrendingUp, Zap, Target, Calendar } from 'lucide-react';
import { 
  ResponsiveContainer, 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip as RechartsTooltip, 
  Legend
} from 'recharts';

interface AnalysisPanelProps {
  forecastData: any;
  areaPoints: [number, number][];
  areaKm2: number;
  onClose: () => void;
}

export const AnalysisPanel: React.FC<AnalysisPanelProps> = ({
  forecastData,
  areaPoints,
  areaKm2,
  onClose,
}) => {
  const [forecastPeriod, setForecastPeriod] = useState<'24h' | '48h'>('24h');
  const data = forecastData?.data;

  // Bölgesel analiz verilerini eşle
  const recommendation = data?.general_recommendation ?? 'Analiz Ediliyor...';
  const avgSolar = data?.area_summary?.avg_solar ?? data?.solar_ghi ?? '—';
  const avgWind = data?.area_summary?.avg_wind ?? data?.wind_speed ?? '—';
  const pointCount = data?.area_summary?.point_count ?? 0;
  
  const sweetSpot = data?.sweet_spot;
  const ssLat = sweetSpot?.lat !== undefined ? sweetSpot.lat.toFixed(5) : '—';
  const ssLon = sweetSpot?.lon !== undefined ? sweetSpot.lon.toFixed(5) : '—';

  const isWind = recommendation?.toLowerCase().includes('rüzgar') ?? false;
  const isSolar = (recommendation?.toLowerCase().includes('güneş') || recommendation?.toLowerCase().includes('ges')) ?? false;
  const isHybrid = (recommendation?.toLowerCase().includes('hibrit') || recommendation?.toLowerCase().includes('karma')) ?? false;

  const isSinglePoint = areaPoints.length === 1;
  const chartData = forecastPeriod === '24h' ? data?.forecast_24h : data?.forecast_48h;

  return (
    <div className="h-full flex flex-col bg-slate-950 text-slate-100 overflow-y-auto font-sans">
      {/* Header */}
      <div className="flex items-center justify-between px-8 py-6 border-b border-slate-800 bg-slate-900/70 sticky top-0 z-10 backdrop-blur-sm">
        <div>
          <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            {isSinglePoint ? (
              <Target size={22} className="text-blue-400" />
            ) : (
              <Layers size={22} className="text-orange-400" />
            )}
            {isSinglePoint ? 'Konum Analiz Raporu' : 'Bölgesel Analiz Raporu'}
          </h2>
          <p className="text-slate-400 text-sm mt-0.5">
            {isSinglePoint ? (
              `📍 ${data?.latitude?.toFixed(5)}, ${data?.longitude?.toFixed(5)}`
            ) : (
              `${areaKm2} km² Alan · ${pointCount} Veri Noktası`
            )}
          </p>
        </div>
        <button
          onClick={onClose}
          className="bg-slate-800 hover:bg-red-600/30 border border-slate-700 hover:border-red-500 text-slate-400 hover:text-red-400 p-2 rounded-lg transition-all"
        >
          <X size={20} />
        </button>
      </div>

      <div className="p-8 flex flex-col gap-6">
        {/* Ana Tavsiye */}
        <div className="rounded-2xl p-8 bg-gradient-to-br from-indigo-900/40 to-slate-900/40 border border-indigo-500/30 shadow-[0_0_30px_rgba(99,102,241,0.15)] relative overflow-hidden">
          <div className="absolute top-0 right-0 p-4 opacity-10">
            <Zap size={120} />
          </div>
          <span className="text-xs font-bold uppercase tracking-[0.2em] text-indigo-400">Yatırım Tavsiyesi</span>
          <p className="text-3xl font-black mt-3 mb-4 leading-tight">{recommendation}</p>
          <div className="flex items-center gap-2 text-sm text-slate-300 bg-slate-950/50 p-3 rounded-xl border border-slate-800">
            <Target size={16} className="text-orange-400" />
            <span>{isSinglePoint ? 'Seçilen noktanın verileri üzerinden hesaplanmıştır.' : 'Alan geneli ortalama potansiyel üzerinden hesaplanmıştır.'}</span>
          </div>
        </div>

        {/* Veriler */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 relative group hover:border-orange-500/50 transition-all">
            <div className="flex items-center gap-2 text-orange-400 mb-4">
              <Sun size={20} />
              <span className="text-xs font-bold uppercase tracking-widest">{isSinglePoint ? 'Güneş (GHI)' : 'Ort. Güneş (GHI)'}</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-5xl font-black text-white">{avgSolar}</span>
              <span className="text-slate-500 font-medium uppercase text-xs">W/m²</span>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-1.5 mt-6 overflow-hidden">
              <div 
                className="bg-orange-500 h-full rounded-full transition-all duration-1000" 
                style={{ width: `${Math.min(100, (Number(avgSolar) / 2000) * 100)}%` }}
              ></div>
            </div>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 relative group hover:border-blue-500/50 transition-all">
            <div className="flex items-center gap-2 text-blue-400 mb-4">
              <Wind size={20} />
              <span className="text-xs font-bold uppercase tracking-widest">{isSinglePoint ? 'Rüzgar Hızı' : 'Ort. Rüzgar Hızı'}</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-5xl font-black text-white">{avgWind}</span>
              <span className="text-slate-500 font-medium uppercase text-xs">m/s</span>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-1.5 mt-6 overflow-hidden">
              <div 
                className="bg-blue-500 h-full rounded-full transition-all duration-1000" 
                style={{ width: `${Math.min(100, (Number(avgWind) / 12) * 100)}%` }}
              ></div>
            </div>
          </div>
        </div>

        {/* Tahmin Grafiği */}
        <div className="bg-slate-900/80 border border-slate-700 rounded-2xl p-6 shadow-xl">
          <div className="flex items-center justify-between mb-8">
            <h4 className="text-sm font-bold text-slate-300 flex items-center gap-2 uppercase tracking-widest">
              <TrendingUp size={16} className="text-indigo-400" /> Üretim Tahmin Grafiği
            </h4>
            <div className="flex bg-slate-950 p-1 rounded-lg border border-slate-800">
              <button 
                onClick={() => setForecastPeriod('24h')}
                className={`px-3 py-1 text-[10px] font-bold rounded-md transition-all ${forecastPeriod === '24h' ? 'bg-indigo-600 text-white' : 'text-slate-500 hover:text-slate-300'}`}
              >24 Saat</button>
              <button 
                onClick={() => setForecastPeriod('48h')}
                className={`px-3 py-1 text-[10px] font-bold rounded-md transition-all ${forecastPeriod === '48h' ? 'bg-indigo-600 text-white' : 'text-slate-500 hover:text-slate-300'}`}
              >48 Saat</button>
            </div>
          </div>

          <div className="h-[280px] w-full">
            {chartData ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                  <XAxis 
                    dataKey="hour" 
                    stroke="#64748b" 
                    fontSize={10} 
                    tickLine={false} 
                    axisLine={false} 
                    interval={forecastPeriod === '24h' ? 3 : 7}
                  />
                  <YAxis 
                    yAxisId="left"
                    stroke="#f97316" 
                    fontSize={10} 
                    tickLine={false} 
                    axisLine={false}
                    tickFormatter={(val) => `${val}`}
                  />
                  <YAxis 
                    yAxisId="right"
                    orientation="right"
                    stroke="#3b82f6" 
                    fontSize={10} 
                    tickLine={false} 
                    axisLine={false}
                    tickFormatter={(val) => `${val}`}
                  />
                  <RechartsTooltip 
                    contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '8px', fontSize: '12px' }}
                    itemStyle={{ padding: '2px 0' }}
                  />
                  <Legend verticalAlign="top" align="right" height={36} iconType="circle" />
                  <Line 
                    yAxisId="left"
                    name="Güneş (W/m²)"
                    type="monotone" 
                    dataKey="solar" 
                    stroke="#f97316" 
                    strokeWidth={3} 
                    dot={false} 
                    activeDot={{ r: 6 }}
                    animationDuration={1500}
                  />
                  <Line 
                    yAxisId="right"
                    name="Rüzgar (m/s)"
                    type="monotone" 
                    dataKey="wind" 
                    stroke="#3b82f6" 
                    strokeWidth={3} 
                    dot={false} 
                    activeDot={{ r: 6 }}
                    animationDuration={1500}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-slate-500 text-sm">
                Tahmin verisi yüklenemedi.
              </div>
            )}
          </div>
        </div>

        {/* Alt Bilgi Alanı */}
        {!isSinglePoint ? (
          <>
            {/* Sweet Spot Kartı (Sadece Bölgesel Modda) */}
            <div className="bg-slate-900/80 border border-slate-700 rounded-2xl p-6 shadow-xl">
              <div className="flex items-center justify-between mb-6">
                <h4 className="text-sm font-bold text-slate-300 flex items-center gap-2 uppercase tracking-widest">
                  <Target size={16} className="text-red-500" /> En Verimli Nokta (Sweet Spot)
                </h4>
                <span className="bg-red-500/10 text-red-400 text-[10px] font-bold px-2 py-1 rounded border border-red-500/20">OPTIMUM</span>
              </div>
              
              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div className="flex flex-col">
                    <span className="text-slate-500 text-[10px] uppercase font-bold">Koordinatlar</span>
                    <span className="font-mono text-sm text-slate-200 mt-1">{ssLat}, {ssLon}</span>
                  </div>
                </div>
                <div className="bg-slate-950/50 rounded-xl p-4 border border-slate-800 space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-slate-400">☀️ Güneş</span>
                    <span className="text-sm font-bold text-orange-400">{sweetSpot?.solar ?? '—'} W/m²</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-slate-400">💨 Rüzgar</span>
                    <span className="text-sm font-bold text-blue-400">{sweetSpot?.wind ?? '—'} m/s</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Teknik Detaylar (Sadece Bölgesel Modda) */}
            <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-6">
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <p className="text-slate-500 text-[10px] uppercase font-bold mb-1">Toplam Alan</p>
                  <p className="text-lg font-bold text-white">{areaKm2} <small className="text-xs text-slate-500">km²</small></p>
                </div>
                <div>
                  <p className="text-slate-500 text-[10px] uppercase font-bold mb-1">Veri Noktası</p>
                  <p className="text-lg font-bold text-white">{pointCount} <small className="text-xs text-slate-500">adet</small></p>
                </div>
                <div>
                  <p className="text-slate-500 text-[10px] uppercase font-bold mb-1">Analiz Derinliği</p>
                  <p className="text-lg font-bold text-white">Yüksek</p>
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-6">
            <div className="flex items-center justify-between">
              <div className="flex flex-col">
                <span className="text-slate-500 text-[10px] uppercase font-bold mb-1">Analiz Edilen Konum</span>
                <p className="text-sm font-mono text-white">LAT: {data?.latitude?.toFixed(6)} · LON: {data?.longitude?.toFixed(6)}</p>
              </div>
              <div className="text-right">
                <span className="text-slate-500 text-[10px] uppercase font-bold mb-1">Hassasiyet</span>
                <p className="text-sm font-bold text-green-400">Yüksek (Noktasal)</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
