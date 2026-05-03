import React, { useState } from 'react';
import { Zap, ChevronRight, Menu } from 'lucide-react';

interface SidebarProps {
  onLocationSelect: (lat: number, lon: number) => void;
}

const PROVINCES = [
  { name: 'Ankara', lat: 39.9208, lon: 32.8541 },
  { name: 'İstanbul', lat: 41.0082, lon: 28.9784 },
  { name: 'İzmir', lat: 38.4192, lon: 27.1287 },
  { name: 'Antalya', lat: 36.8969, lon: 30.7133 },
  { name: 'Konya', lat: 37.8746, lon: 32.4932 },
  { name: 'Kayseri', lat: 38.7312, lon: 35.4787 },
];

export const Sidebar: React.FC<SidebarProps> = ({ onLocationSelect }) => {
  const [selectedProvince, setSelectedProvince] = useState(PROVINCES[0].name);
  const [isOpen, setIsOpen] = useState(false);

  const handleProvinceChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const p = PROVINCES.find(prov => prov.name === e.target.value);
    if (p) {
      setSelectedProvince(p.name);
      onLocationSelect(p.lat, p.lon);
    }
  };

  return (
    <>
      {/* Kapalıyken görünen açma butonu */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="absolute top-6 left-6 z-[2000] bg-slate-900/60 backdrop-blur-md text-white p-3 rounded-xl shadow-[0_0_15px_rgba(0,0,0,0.5)] border border-slate-700/50 hover:bg-slate-800 transition-all duration-300"
        >
          <Menu size={24} />
        </button>
      )}

      {/* Sol tarafta yüzen, saydam (glassmorphism) ve açılıp kapanabilen panel */}
      <div
        className={`absolute top-0 left-0 h-full w-80 bg-slate-900/50 backdrop-blur-xl text-slate-100 p-6 shadow-2xl flex flex-col gap-8 z-[2000] border-r border-slate-700/30 transition-transform duration-300 ease-in-out ${isOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
      >
        <button
          onClick={() => setIsOpen(false)}
          className="absolute top-6 right-6 text-slate-400 hover:text-white transition-colors bg-slate-800/40 hover:bg-slate-800/80 p-1.5 rounded-lg border border-slate-700/50"
        >
          <ChevronRight size={20} />
        </button>

        <div className="flex items-center gap-3 pr-8">
          <div className="bg-yellow-500/20 p-2 rounded-lg">
            <Zap className="text-yellow-500" size={28} />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">RE-Atlas</h1>
            <p className="text-slate-300 text-[11px] mt-0.5 opacity-80">Yenilenebilir Enerji Karar Destek</p>
          </div>
        </div>

        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">İl Seçimi</label>
            <select
              value={selectedProvince}
              onChange={handleProvinceChange}
              className="bg-slate-800/60 border border-slate-600/50 text-white rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-shadow appearance-none backdrop-blur-sm"
            >
              {PROVINCES.map(prov => (
                <option key={prov.name} value={prov.name} className="bg-slate-900">{prov.name}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">İlçe Seçimi</label>
            <select
              disabled
              className="bg-slate-800/30 border border-slate-700/30 text-slate-500 rounded-lg p-3 cursor-not-allowed appearance-none"
            >
              <option>Merkez (Demo)</option>
            </select>
            <span className="text-[10px] text-slate-400/80 mt-1">İlçe modülü yakında eklenecektir.</span>
          </div>
        </div>

        <div className="mt-auto">
          <div className="bg-slate-800/40 p-4 rounded-xl border border-slate-600/30 backdrop-blur-sm">
            <h4 className="text-sm font-bold text-slate-100 mb-2">Nasıl Çalışır?</h4>
            <p className="text-[11px] text-slate-300 leading-relaxed">
              Harita üzerinde analiz etmek istediğiniz noktaya tıklayın. Ajanlarımız koordinatın meteorolojik verilerini çekerek anında yatırım tavsiyesi sunacaktır.
            </p>
          </div>
        </div>
      </div>
    </>
  );
};
