import { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { MapArea } from './components/MapArea';
import { AnalysisPanel } from './components/AnalysisPanel';
import { Sun, Wind, Map as MapIcon } from 'lucide-react';

interface AnalysisResult {
  forecastData: any;
  areaPoints: [number, number][];
  areaKm2: number;
}

function App() {
  const [mapCenter, setMapCenter] = useState<[number, number]>([39.9208, 32.8541]);
  const [provinceName, setProvinceName] = useState<string>('Ankara');
  const [showAnalysis, setShowAnalysis] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [activeLayer, setActiveLayer] = useState<'normal' | 'solar' | 'wind'>('normal');

  const handleLocationSelect = (lat: number, lon: number, name: string) => {
    setMapCenter([lat, lon]);
    setProvinceName(name);
    setShowAnalysis(false);
    setAnalysisResult(null);
  };

  const handleAnalysisReady = (forecastData: any, areaPoints: [number, number][], areaKm2: number) => {
    setAnalysisResult({ forecastData, areaPoints, areaKm2 });
    setShowAnalysis(true);
  };

  const handleCloseAnalysis = () => {
    setShowAnalysis(false);
    setAnalysisResult(null);
  };

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-slate-950 font-sans">
      {/* Üst Orta Katman Seçici Butonlar */}
      <div className="absolute top-6 left-1/2 -translate-x-1/2 z-[4000] flex items-center gap-1 bg-slate-900/80 backdrop-blur-md p-1 rounded-2xl border border-slate-700/50 shadow-2xl">
        <button
          onClick={() => setActiveLayer('normal')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all ${
            activeLayer === 'normal' 
              ? 'bg-slate-700 text-white shadow-inner' 
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
          }`}
        >
          <MapIcon size={16} /> Normal
        </button>
        <button
          onClick={() => setActiveLayer('solar')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all ${
            activeLayer === 'solar' 
              ? 'bg-orange-600 text-white shadow-[0_0_15px_rgba(234,88,12,0.4)]' 
              : 'text-slate-400 hover:text-orange-400 hover:bg-orange-950/20'
          }`}
        >
          <Sun size={16} /> Güneş
        </button>
        <button
          onClick={() => setActiveLayer('wind')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all ${
            activeLayer === 'wind' 
              ? 'bg-blue-600 text-white shadow-[0_0_15px_rgba(37,99,235,0.4)]' 
              : 'text-slate-400 hover:text-blue-400 hover:bg-blue-950/20'
          }`}
        >
          <Wind size={16} /> Rüzgar
        </button>
      </div>

      {/* Harita her zaman tam ekran */}
      <MapArea
        center={mapCenter}
        provinceName={provinceName}
        showAnalysis={showAnalysis}
        activeLayer={activeLayer}
        onAnalysisReady={handleAnalysisReady}
        onCloseAnalysis={handleCloseAnalysis}
      />

      {/* Sol sidebar haritanın üzerinde yüzer */}
      <Sidebar onLocationSelect={handleLocationSelect} />

      {/* Analiz Paneli — sol tarafta havada asılı yüzen kart */}
      <div
        className={`absolute top-4 right-4 bottom-4 w-[calc(50%-1rem)] z-[3000]
          transition-all duration-500 ease-in-out
          ${showAnalysis
            ? 'opacity-100 translate-x-0'
            : 'opacity-0 translate-x-8 pointer-events-none'
          }`}
      >
        <div className="h-full rounded-3xl overflow-hidden shadow-[0_8px_40px_rgba(0,0,0,0.7)] border border-slate-700/50 bg-slate-950/95 backdrop-blur-xl">
          {showAnalysis && analysisResult && (
            <AnalysisPanel
              forecastData={analysisResult.forecastData}
              areaPoints={analysisResult.areaPoints}
              areaKm2={analysisResult.areaKm2}
              onClose={handleCloseAnalysis}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
