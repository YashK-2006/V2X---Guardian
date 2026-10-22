import React, { useEffect, useState } from 'react';

import { useNavigate } from 'react-router-dom';

import { X, ExternalLink } from 'lucide-react';

import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

import { useStore, TYPE_ICONS, ATTACK_LABELS } from '../stores/useStore';

import { TrustGauge } from './TrustGauge';

import { KV, StatusBadge } from './ui';

import { api } from '../api';



interface TrustEvent { time: number; new_score: number; reason: string; kind: string }



/** Compact side panel for the vehicle selected on the map. */

export const VehicleDetail: React.FC = () => {

  const id = useStore((s) => s.selectedVehicleId);

  const v = useStore((s) => (s.selectedVehicleId ? s.vehicles[s.selectedVehicleId] : undefined));

  const setSelectedVehicle = useStore((s) => s.setSelectedVehicle);

  const navigate = useNavigate();

  const [history, setHistory] = useState<TrustEvent[]>([]);



  useEffect(() => {

    if (!id) return;

    let alive = true;

    const load = () => api.get(`/vehicles/${id}/trust/history`).then((r) => alive && setHistory(r.history)).catch(() => {});

    load();

    const timer = setInterval(load, 2000);

    return () => { alive = false; clearInterval(timer); };

  }, [id]);



  if (!id || !v) return null;

  const spoofing = v.claimed_type !== v.type;

  const chart = history.map((h) => ({ t: h.time, trust: +(h.new_score * 100).toFixed(1) }));



  return (

    <div className="glass-card p-5 h-full flex flex-col relative overflow-y-auto">

      <button onClick={() => setSelectedVehicle(null)} className="absolute top-4 right-4 text-gray-400 hover:text-white">

        <X size={20} />

      </button>

      <div className="mb-4">

        <h2 className="text-xl font-bold text-white mb-1 flex items-center gap-2">

          <span>{TYPE_ICONS[v.type] ?? '🚗'}</span> {v.id}

        </h2>

        <div className="flex gap-2 items-center">

          <StatusBadge status={v.status} />

          <span className="text-[10px] font-mono text-gray-500">{v.hash}</span>

        </div>

      </div>



      {spoofing && (

        <div className="mb-3 rounded-md border border-rose-500/50 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">

          🚨 Claims <b>{v.claimed_type}</b> but registered as <b>{v.type}</b>

        </div>

      )}



      <div className="flex justify-center mb-3">

        <TrustGauge score={v.trust_score} size={120} label="Trust Score" />

      </div>



      <div className="mb-3">

        <KV label="Vehicle type" value={`${v.type}`} />

        <KV label="Claimed type" value={<span className={spoofing ? 'text-rose-400 font-semibold' : ''}>{v.claimed_type}</span>} />

        <KV label="Speed" value={`${(v.speed * 3.6).toFixed(1)} km/h`} />

        <KV label="Acceleration" value={`${v.acceleration.toFixed(2)} m/s²`} />

        <KV label="Heading" value={`${v.heading.toFixed(0)}°`} />

        <KV label="Position" value={`${v.x.toFixed(0)}, ${v.y.toFixed(0)}`} mono />

        <KV label="Messages sent / received" value={`${v.message_count} / ${v.messages_received}`} />

        <KV label="Suspicious / malicious msgs" value={`${v.suspicious_count} / ${v.misbehavior_count}`} />

        <KV label="Reputation" value={(v.reputation * 100).toFixed(1)} />

        <KV label="Blockchain records" value={v.blockchain_records} />

        {Object.keys(v.attack_types).length > 0 && (

          <KV label="Detected" value={Object.entries(v.attack_types).map(([k, n]) => `${ATTACK_LABELS[k] ?? k} ×${n}`).join(', ')} />

        )}

      </div>



      <div className="h-32 mb-3">

        <ResponsiveContainer width="100%" height="100%">

          <LineChart data={chart}>

            <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} hide />

            <YAxis domain={[0, 100]} width={28} tick={{ fontSize: 10, fill: '#6b7280' }} />

            <ReferenceLine y={60} stroke="#10b98155" strokeDasharray="3 3" />

            <ReferenceLine y={30} stroke="#f43f5e55" strokeDasharray="3 3" />

            <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151', fontSize: 12 }} />

            <Line type="stepAfter" dataKey="trust" stroke="#6366f1" strokeWidth={2} dot={false} isAnimationActive={false} />

          </LineChart>

        </ResponsiveContainer>

      </div>



      <button className="btn-primary flex items-center justify-center gap-2" onClick={() => navigate(`/vehicle/${v.id}`)}>

        <ExternalLink size={16} /> Open full vehicle details

      </button>

    </div>

  );

};
