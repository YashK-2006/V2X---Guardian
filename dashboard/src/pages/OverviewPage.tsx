import { pct } from '../api';

import React from 'react';

import { Car, ShieldAlert, ShieldCheck, Activity, Siren, Ban } from 'lucide-react';

import { StatsCard } from '../components/StatsCard';

import { VehicleMap } from '../components/VehicleMap';

import { VehicleDetail } from '../components/VehicleDetail';

import { RsuDetail } from '../components/RsuDetail';

import { EventTimeline } from '../components/EventTimeline';

import { useStore } from '../stores/useStore';





export const OverviewPage: React.FC = () => {

  const stats = useStore((s) => s.stats);

  const selectedVehicleId = useStore((s) => s.selectedVehicleId);

  const selectedRsuId = useStore((s) => s.selectedRsuId);

  const activeAttacks = useStore((s) => s.activeAttacks);



  const v = stats?.vehicles;

  const c = stats?.communication;

  const sec = stats?.security;

  const bc = stats?.blockchain;



  return (

    <div className="p-6 h-full flex flex-col gap-4 page-enter overflow-y-auto">

      <div className="grid grid-cols-6 gap-4">

        <StatsCard title="Active Vehicles" value={v?.active ?? 0} icon={<Car size={22} />} color="indigo" />

        <StatsCard title="Trusted" value={v?.trusted ?? 0} icon={<ShieldCheck size={22} />} color="emerald" />

        <StatsCard title="Suspicious" value={v?.suspicious ?? 0} icon={<Activity size={22} />} color="amber" />

        <StatsCard title="Malicious" value={v?.malicious ?? 0} icon={<ShieldAlert size={22} />} color="rose" />

        <StatsCard title="Blacklisted" value={v?.blacklisted ?? 0} icon={<Ban size={22} />} color="rose" />

        <StatsCard title="Emergency Vehicles" value={v?.emergency ?? 0} icon={<Siren size={22} />} color="cyan" />

      </div>



      {activeAttacks.length > 0 && (

        <div className="attack-banner rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-2 text-sm text-rose-200 flex flex-wrap gap-x-4 gap-y-1">

          <span className="font-semibold">⚔ Active attacks (ground truth):</span>

          {activeAttacks.map((a) => (

            <button key={a.vehicle_id} className="underline-offset-2 hover:underline" onClick={() => useStore.getState().setSelectedVehicle(a.vehicle_id)}>

              {a.vehicle_id}: {a.label}

            </button>

          ))}

        </div>

      )}



      <div className="flex-1 flex gap-4 min-h-[520px]">

        <div className="flex-[2] glass-card p-2 flex flex-col">

          <div className="flex items-center justify-between pb-2 mb-1 border-b border-white/5 px-2">

            <span className="text-sm font-semibold text-gray-200 tracking-wide flex items-center gap-2">

              <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />

              Live Traffic & Simulation Visualizer

            </span>

            <span className="text-xs text-gray-400 font-mono">

              Click vehicle for detail · Pan & Zoom enabled

            </span>

          </div>

          <div className="flex-1 min-h-[460px] relative">

            <VehicleMap />

          </div>

        </div>

        <div className="flex-1 min-w-[320px] max-w-[420px]">

          {selectedVehicleId ? <VehicleDetail /> : selectedRsuId ? <RsuDetail /> : <EventTimeline />}

        </div>

      </div>



      <div className="grid grid-cols-4 gap-4 text-sm">

        <div className="glass-card p-4">

          <h4 className="text-xs uppercase tracking-wider text-gray-500 mb-2">Communication</h4>

          <Row k="Messages sent" v={c?.messages_sent.toLocaleString()} />

          <Row k="Messages received" v={c?.messages_received.toLocaleString()} />

          <Row k="Messages / sec" v={c?.messages_per_sec} />

          <Row k="V2V / V2I" v={c ? `${c.v2v.toLocaleString()} / ${c.v2i.toLocaleString()}` : undefined} />

          <Row k="V2P / V2N / RSU warnings" v={c ? `${c.v2p.toLocaleString()} / ${c.v2n} / ${c.i2v_notifications}` : undefined} />

          <Row k="Failed (lost)" v={c?.failed.toLocaleString()} />

        </div>

        <div className="glass-card p-4">

          <h4 className="text-xs uppercase tracking-wider text-gray-500 mb-2">Security</h4>

          <Row k="Attacks launched" v={sec?.attacks_launched} />

          <Row k="Detection rate" v={pct(sec?.detection_rate)} />

          <Row k="False positives" v={sec ? `${sec.false_positives} (${pct(sec.false_positive_rate, 2)})` : undefined} />

          <Row k="False negatives" v={sec?.false_negatives} />

          <Row k="Evidence records" v={sec?.evidence_records} />

        </div>

        <div className="glass-card p-4">

          <h4 className="text-xs uppercase tracking-wider text-gray-500 mb-2">Blockchain</h4>

          <Row k="Blocks" v={bc?.blocks} />

          <Row k="Transactions" v={bc?.transactions} />

          <Row k="Tx latency" v={bc ? `${bc.avg_tx_latency_s.toFixed(2)} s` : undefined} />

          <Row k="TPS" v={bc?.tps.toFixed(2)} />

          <Row k="Consensus" v="PoA · 5 RSUs" />

        </div>

        <div className="glass-card p-4">

          <h4 className="text-xs uppercase tracking-wider text-gray-500 mb-2">Network Quality</h4>

          <Row k="Avg trust" v={v ? (v.avg_trust * 100).toFixed(1) : undefined} />

          <Row k="Packet delivery ratio" v={pct(c?.pdr)} />

          <Row k="Avg latency" v={c ? `${c.avg_latency_ms.toFixed(2)} ms` : undefined} />

          <Row k="Throughput" v={c ? `${c.throughput_kbps.toFixed(0)} kbps` : undefined} />

          <Row k="AI inference" v={stats ? `${stats.ai.avg_inference_ms.toFixed(3)} ms/msg` : undefined} />

        </div>

      </div>

    </div>

  );

};



const Row: React.FC<{ k: string; v: React.ReactNode }> = ({ k, v }) => (

  <div className="flex justify-between py-0.5">

    <span className="text-gray-400">{k}</span>

    <span className="text-gray-100 font-mono">{v ?? '—'}</span>

  </div>

);
