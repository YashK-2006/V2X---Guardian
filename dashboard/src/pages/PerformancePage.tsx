import React, { useEffect, useState } from 'react';

import { Gauge, Radio, Blocks, Brain, Cpu, ShieldCheck } from 'lucide-react';

import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, BarChart, Bar, Legend } from 'recharts';

import { Section, KV, Empty } from '../components/ui';

import { api, fmtTime, pct } from '../api';

import { ATTACK_LABELS } from '../stores/useStore';



const ms = (v?: number | null, d = 2) => (v === null || v === undefined ? '—' : `${v.toFixed(d)} ms`);

const sec = (v?: number | null, d = 2) => (v === null || v === undefined ? '—' : `${v.toFixed(d)} s`);

const TT = { background: '#111827', border: '1px solid #374151' };



const Chart: React.FC<{ data: any[]; lines: { key: string; color: string; name: string }[]; unit?: string; domain?: [number, number] }> = ({ data, lines, unit, domain }) => (

  <div className="h-48">

    <ResponsiveContainer width="100%" height="100%">

      <LineChart data={data}>

        <CartesianGrid stroke="#1f2937" />

        <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tickFormatter={(t) => fmtTime(t)} tick={{ fontSize: 10, fill: '#6b7280' }} />

        <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} width={40} unit={unit} domain={domain ?? ['auto', 'auto']} />

        <Tooltip labelFormatter={(t) => fmtTime(t as number)} contentStyle={TT} />

        {lines.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}

        {lines.map((l) => <Line key={l.key} dataKey={l.key} name={l.name} stroke={l.color} dot={false} isAnimationActive={false} />)}

      </LineChart>

    </ResponsiveContainer>

  </div>

);



export const PerformancePage: React.FC = () => {

  const [p, setP] = useState<any>(null);

  useEffect(() => {

    const load = () => api.get('/performance').then(setP).catch(() => {});

    load();

    const t = setInterval(load, 2000);

    return () => clearInterval(t);

  }, []);



  if (!p) return <div className="p-6 text-gray-500">Loading…</div>;

  const v = p.v2x, b = p.blockchain, a = p.ai, s = p.system, imp = p.security_impact;

  const tl = (p.timeline ?? []).map((x: any) => ({

    ...x, latency: +(x.latency_ms ?? 0).toFixed(3), pdrp: +((x.pdr ?? 0) * 100).toFixed(2),

    txl: +(x.tx_latency_s ?? 0).toFixed(3), infer: +(x.infer_ms ?? 0).toFixed(3),

  }));

  const perAttack = Object.entries(a.per_attack_detection_latency_s ?? {}).map(([k, val]) => ({ attack: ATTACK_LABELS[k] ?? k, latency: +(val as number).toFixed(2) }));



  return (

    <div className="p-6 h-full overflow-y-auto page-enter space-y-4">

      <h1 className="text-2xl font-bold text-white flex items-center gap-2"><Gauge className="text-amber-400" /> Performance</h1>



      <div className="grid grid-cols-3 gap-4">

        <Section title="V2X communication" right={<Radio size={16} className="text-cyan-400" />}>

          <KV label="End-to-end latency (avg / p95)" value={`${ms(v.e2e_avg_ms)} / ${ms(v.e2e_p95_ms)}`} />

          <KV label="Radio latency (p50 / p95)" value={`${ms(v.latency_p50_ms)} / ${ms(v.latency_p95_ms)}`} />

          <KV label="Packet delivery ratio" value={pct(v.pdr, 2)} />

          <KV label="Packet loss" value={pct(v.packet_loss, 2)} />

          <KV label="Throughput" value={`${v.throughput_kbps.toFixed(0)} kbps`} />

          <KV label="Receivers per broadcast" value={v.avg_receivers_per_msg.toFixed(1)} />

          <KV label="Avg message size" value={`${v.avg_message_bytes.toFixed(0)} B`} />

          <KV label="Security overhead (sig + cert)" value={`${v.security_overhead_bytes} B (${pct(v.security_overhead_ratio)})`} />

          <KV label="V2V / V2I / V2P" value={`${v.v2v.toLocaleString()} / ${v.v2i.toLocaleString()} / ${v.v2p.toLocaleString()}`} />

          <KV label="RSU warnings (I2V)" value={v.i2v_notifications} />

        </Section>

        <Section title="Blockchain" right={<Blocks size={16} className="text-indigo-400" />}>

          <KV label="Consensus" value={b.consensus} />

          <KV label="Transaction latency (avg / p95)" value={`${sec(b.avg_tx_latency_s)} / ${sec(b.tx_latency_p95_s)}`} />

          <KV label="Consensus / sealing time" value={`${ms(b.consensus_time_ms)} (p95 ${ms(b.consensus_time_p95_ms)})`} />

          <KV label="Throughput" value={`${b.tps.toFixed(2)} TPS`} />

          <KV label="Block interval" value={sec(b.block_interval_s, 1)} />

          <KV label="Blocks / transactions" value={`${b.blocks} / ${b.transactions}`} />

          <KV label="Storage" value={`${(b.storage_bytes / 1024).toFixed(1)} KB`} />

          <KV label="Avg transaction size" value={`${b.avg_tx_bytes.toFixed(0)} B`} />

          <KV label="Replication overhead" value={`${(b.comm_overhead_bytes / 1024).toFixed(1)} KB (${b.validators} validators)`} />

        </Section>

        <Section title="AI & system" right={<Brain size={16} className="text-emerald-400" />}>

          <KV label="Model / mode" value={`${a.model} / ${a.mode}`} />

          <KV label="Inference per message (avg / p95)" value={`${ms(a.inference_avg_ms, 3)} / ${ms(a.inference_p95_ms, 3)}`} />

          <KV label="Detection latency (avg / max)" value={`${sec(a.detection_latency_avg_s)} / ${sec(a.detection_latency_max_s)}`} />

          <KV label="Attack → blacklist (avg)" value={sec(a.isolation_time_avg_s)} />

          <KV label="CPU (now / avg)" value={`${s.cpu_percent?.toFixed(0) ?? '—'}% / ${s.cpu_avg_percent?.toFixed(0) ?? '—'}%`} />

          <KV label="Memory" value={s.memory_mb ? `${s.memory_mb.toFixed(0)} MB` : '—'} />

          <KV label="Pipeline step (avg / p95)" value={`${ms(s.step_avg_ms)} / ${ms(s.step_p95_ms)}`} />

          <KV label="Real-time capacity" value={`${s.real_time_factor.toFixed(1)}× faster than real time`} />

          <KV label="GPU" value={s.gpu} />

        </Section>

      </div>



      <Section title="Security impact on receivers" right={<ShieldCheck size={16} className="text-emerald-400" />}>

        <div className="grid grid-cols-4 gap-4 text-sm">

          <KV label="Malicious deliveries" value={imp.malicious_delivered.toLocaleString()} />

          <KV label="… accepted by receivers" value={`${imp.malicious_accepted.toLocaleString()} (${pct(imp.malicious_acceptance_rate, 2)})`} />

          <KV label="Honest deliveries" value={imp.honest_delivered.toLocaleString()} />

          <KV label="… wrongly rejected" value={`${imp.honest_rejected.toLocaleString()} (${pct(imp.honest_rejection_rate, 3)})`} />

        </div>

        <p className="text-[11px] text-gray-500 mt-2">A message is accepted when its signature is valid, it is not flagged and its sender is trusted.</p>

      </Section>



      <div className="grid grid-cols-2 gap-4">

        <Section title="Radio latency (ms)"><Chart data={tl} lines={[{ key: 'latency', color: '#06b6d4', name: 'latency' }]} /></Section>

        <Section title="Packet delivery ratio (%)"><Chart data={tl} lines={[{ key: 'pdrp', color: '#10b981', name: 'PDR' }]} /></Section>

        <Section title="Blockchain tx latency (s) and TPS">

          <Chart data={tl} lines={[{ key: 'txl', color: '#6366f1', name: 'tx latency (s)' }, { key: 'tps', color: '#f59e0b', name: 'TPS' }]} />

        </Section>

        <Section title="AI inference per message (ms) and CPU (%)" right={<Cpu size={16} className="text-gray-400" />}>

          <Chart data={tl} lines={[{ key: 'infer', color: '#f43f5e', name: 'inference (ms)' }, { key: 'cpu', color: '#a855f7', name: 'CPU (%)' }]} />

        </Section>

      </div>



      <Section title="Detection latency per attack type (attack launch → first flagged message)">

        {perAttack.length === 0 ? <Empty>Launch attacks to measure detection latency.</Empty> : (

          <div className="h-56">

            <ResponsiveContainer width="100%" height="100%">

              <BarChart data={perAttack}>

                <XAxis dataKey="attack" tick={{ fontSize: 11, fill: '#9ca3af' }} />

                <YAxis unit=" s" tick={{ fontSize: 11, fill: '#6b7280' }} width={40} />

                <Tooltip contentStyle={TT} />

                <Bar dataKey="latency" fill="#f59e0b" radius={[4, 4, 0, 0]} />

              </BarChart>

            </ResponsiveContainer>

          </div>

        )}

      </Section>

    </div>

  );

};
