import React from 'react';

import { X, Radio } from 'lucide-react';

import { useStore } from '../stores/useStore';

import { KV } from './ui';



export const RsuDetail: React.FC = () => {

  const rsu = useStore((s) => s.rsus.find((r) => r.id === s.selectedRsuId));

  const vehicles = useStore((s) => s.vehicles);

  const nextValidator = useStore((s) => s.stats?.blockchain.next_validator);

  const setSelectedRsu = useStore((s) => s.setSelectedRsu);

  if (!rsu) return null;



  const inRange = Object.values(vehicles).filter((v) => Math.hypot(v.x - rsu.x, v.y - rsu.y) <= 500);

  const flaggedInRange = inRange.filter((v) => v.status !== 'trusted');



  return (

    <div className="glass-card p-5 h-full flex flex-col relative overflow-y-auto">

      <button onClick={() => setSelectedRsu(null)} className="absolute top-4 right-4 text-gray-400 hover:text-white">

        <X size={20} />

      </button>

      <h2 className="text-xl font-bold text-white mb-1 flex items-center gap-2">

        <Radio className="text-cyan-400" size={20} /> {rsu.id}

      </h2>

      <p className="text-xs text-gray-500 mb-4">Roadside unit · PoA blockchain validator</p>

      <KV label="Position" value={`${rsu.x.toFixed(0)}, ${rsu.y.toFixed(0)}`} mono />

      <KV label="Coverage radius" value="500 m" />

      <KV label="Status" value={<span className="text-emerald-400">{rsu.status}</span>} />

      <KV label="Messages received (V2I)" value={rsu.received.toLocaleString()} />

      <KV label="Flagged messages" value={rsu.flagged.toLocaleString()} />

      <KV label="Blocks sealed" value={rsu.blocks_sealed} />

      <KV label="Next block validator" value={nextValidator === rsu.id ? 'this RSU' : nextValidator ?? '—'} />

      <KV label="Vehicles in range" value={inRange.length} />



      <h3 className="text-xs uppercase tracking-wider text-gray-400 mt-5 mb-2">Non-trusted vehicles in range</h3>

      <div className="space-y-1 text-sm">

        {flaggedInRange.length === 0 && <div className="text-gray-500 text-xs">none</div>}

        {flaggedInRange.map((v) => (

          <button key={v.id} onClick={() => useStore.getState().setSelectedVehicle(v.id)}

            className="w-full flex justify-between px-2 py-1 rounded hover:bg-white/5">

            <span className="font-mono">{v.id}</span>

            <span className={v.status === 'suspicious' ? 'text-amber-400' : 'text-rose-400'}>

              {v.status} · {(v.trust_score * 100).toFixed(1)}

            </span>

          </button>

        ))}

      </div>

    </div>

  );

};
