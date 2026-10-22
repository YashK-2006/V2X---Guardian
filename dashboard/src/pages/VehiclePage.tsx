import React, { useCallback, useEffect, useMemo, useState } from 'react';

import { useNavigate, useParams } from 'react-router-dom';

import { ArrowLeft, RefreshCw, ShieldCheck, ShieldX } from 'lucide-react';

import {

  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, CartesianGrid, BarChart, Bar, Scatter,

  ComposedChart,

} from 'recharts';

import { api, qs, fmtTime, pct } from '../api';

import { TYPE_ICONS, ATTACK_LABELS, useStore } from '../stores/useStore';

import { TrustGauge } from '../components/TrustGauge';

import { ClassBadge, Empty, KV, Section, StatusBadge } from '../components/ui';



const TABS = ['Overview', 'Messages Sent', 'Messages Received', 'Behavior', 'AI Analysis', 'Trust History', 'Attacks', 'Blockchain'] as const;

type Tab = (typeof TABS)[number];



/** Polls an endpoint while mounted. */

function usePoll<T>(path: string | null, intervalMs = 2000): [T | null, () => void, string | null] {

  const [data, setData] = useState<T | null>(null);

  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {

    if (!path) return;

    api.get<T>(path).then((d) => { setData(d); setError(null); }).catch((e) => setError(String(e.message ?? e)));

  }, [path]);

  useEffect(() => {

    load();

    if (!path || intervalMs <= 0) return;

    const t = setInterval(load, intervalMs);

    return () => clearInterval(t);

  }, [path, intervalMs, load]);

  return [data, load, error];

}



export const VehiclePage: React.FC = () => {

  const { id = '' } = useParams();

  const navigate = useNavigate();

  const [tab, setTab] = useState<Tab>('Overview');

  const [detail, , error] = usePoll<any>(`/vehicles/${id}`, 1500);



  if (error && !detail) {

    return (

      <div className="p-6">

        <button className="btn-secondary mb-4 flex items-center gap-2" onClick={() => navigate('/')}><ArrowLeft size={16} /> Back</button>

        <Empty>Vehicle {id} not found ({error}). It may have left the simulation.</Empty>

      </div>

    );

  }

  if (!detail) return <div className="p-6 text-gray-500">Loading {id}…</div>;

  const spoofing = detail.claimed_type !== detail.type;



  return (

    <div className="p-6 h-full overflow-y-auto page-enter">

      <div className="flex items-center gap-4 mb-4">

        <button className="btn-secondary flex items-center gap-2 px-3 py-1.5 text-sm" onClick={() => navigate(-1)}>

          <ArrowLeft size={16} /> Back

        </button>

        <h1 className="text-2xl font-bold text-white flex items-center gap-3">

          <span>{TYPE_ICONS[detail.type] ?? '🚗'}</span> {detail.id}

        </h1>

        <StatusBadge status={detail.status} />

        {!detail.active && <span className="text-xs text-gray-500">(left the simulation)</span>}

        {detail.gt_attack && (

          <span className="text-xs px-2 py-0.5 rounded bg-rose-500/15 text-rose-300 border border-rose-500/40">

            ground truth: {ATTACK_LABELS[detail.gt_attack] ?? detail.gt_attack} active

          </span>

        )}

        <span className="ml-auto text-xs font-mono text-gray-500">on-chain id {detail.hash}</span>

      </div>



      {spoofing && (

        <div className="mb-4 rounded-lg border border-rose-500/50 bg-rose-500/10 px-4 py-3 text-rose-200">

          <div className="font-bold tracking-wide">🚨 EMERGENCY VEHICLE SPOOFING</div>

          <div className="text-sm">

            Actual: <b>{detail.type}</b> · Claimed: <b>{detail.claimed_type}</b> · Trust: <b>{(detail.trust_score * 100).toFixed(1)}</b> · Status:{' '}

            <b className="uppercase">{detail.status}</b>

          </div>

        </div>

      )}



      <div className="tab-nav flex gap-1 mb-4 border-b border-white/10 pb-2 flex-wrap">

        {TABS.map((t) => (

          <button key={t} className={`tab-btn ${tab === t ? 'tab-btn--active' : ''}`} onClick={() => setTab(t)}>{t}</button>

        ))}

      </div>



      {tab === 'Overview' && <OverviewTab d={detail} />}

      {tab === 'Messages Sent' && <SentTab id={id} />}

      {tab === 'Messages Received' && <ReceivedTab id={id} />}

      {tab === 'Behavior' && <BehaviorTab id={id} d={detail} />}

      {tab === 'AI Analysis' && <AITab id={id} d={detail} />}

      {tab === 'Trust History' && <TrustTab id={id} />}

      {tab === 'Attacks' && <AttacksTab id={id} />}

      {tab === 'Blockchain' && <BlockchainTab id={id} />}

    </div>

  );

};



// ------------------------------------------------------------------ Overview

const OverviewTab: React.FC<{ d: any }> = ({ d }) => {

  const comps = d.trust_components ?? {};

  const w = d.trust_weights ?? {};

  return (

    <div className="grid grid-cols-3 gap-4">

      <Section title="Trust">

        <div className="flex justify-center py-2"><TrustGauge score={d.trust_score} size={150} label="Trust score (0-100)" /></div>

        <KV label="Status" value={<StatusBadge status={d.status} />} />

        <KV label="Reputation (neighbour view)" value={(d.reputation * 100).toFixed(1)} />

        <KV label="Neighbour reports (5 s)" value={`${d.consensus.flagging}/${d.consensus.reporters} flagging`} />

        <KV label="Previous offences" value={d.offences} />

        <KV label="On-chain misbehaviour reports" value={d.on_chain_reports} />

      </Section>

      <Section title="Identity">

        <KV label="Vehicle ID" value={d.id} mono />

        <KV label="Registered type" value={d.type} />

        <KV label="Claimed type" value={<span className={d.claimed_type !== d.type ? 'text-rose-400 font-bold' : ''}>{d.claimed_type}</span>} />

        <KV label="Emergency flag" value={d.emergency_flag ? 'SET' : 'no'} />

        <KV label="Certificate" value={d.certificate?.cert_id ?? '—'} mono />

        <KV label="Certificate status" value={d.certificate?.revoked ? <span className="text-rose-400">REVOKED ({d.certificate.revocation_reason})</span> : <span className="text-emerald-400">valid</span>} />

        <KV label="Current pseudonym" value={d.certificate?.pseudonym ?? '—'} mono />

        <KV label="Pseudonym changes" value={d.certificate?.pseudonym_changes ?? 0} />

        <KV label="First seen / last seen" value={`${fmtTime(d.first_seen)} / ${fmtTime(d.last_seen)}`} />

      </Section>

      <Section title="Kinematics">

        <KV label="Position" value={`${d.x.toFixed(1)}, ${d.y.toFixed(1)}`} mono />

        <KV label="Speed" value={`${(d.speed * 3.6).toFixed(1)} km/h`} />

        <KV label="Acceleration" value={`${d.acceleration.toFixed(2)} m/s²`} />

        <KV label="Heading" value={`${d.heading.toFixed(0)}°`} />

        <KV label="Lane / road" value={`${d.lane || '—'} / ${d.road || '—'}`} mono />

        <KV label="Route" value={(d.route ?? []).join(' → ') || '—'} mono />

      </Section>

      <Section title="Communication">

        <KV label="Messages sent" value={d.message_count} />

        <KV label="Messages received" value={d.messages_received} />

        <KV label="Suspicious messages" value={d.suspicious_count} />

        <KV label="Malicious messages" value={d.misbehavior_count} />

        <KV label="Detected attacks" value={d.detected_attacks} />

        <KV label="Blockchain records" value={d.blockchain_records} />

      </Section>

      <Section title="Trust components" className="col-span-2">

        <p className="text-xs text-gray-500 mb-2">

          penalty = S · (α·AI + β·consensus + γ·history + δ·ledger) — weights α={w.alpha?.toFixed(2)} β={w.beta?.toFixed(2)} γ={w.gamma?.toFixed(2)} δ={w.delta?.toFixed(2)}

        </p>

        <div className="h-40">

          <ResponsiveContainer width="100%" height="100%">

            <BarChart data={[

              { k: 'AI behaviour', v: +(comps.ai ?? 1).toFixed(3) },

              { k: 'Neighbour consensus', v: +(comps.consensus ?? 1).toFixed(3) },

              { k: 'History', v: +(comps.history ?? 1).toFixed(3) },

              { k: 'Ledger', v: +(comps.ledger ?? 1).toFixed(3) },

            ]}>

              <XAxis dataKey="k" tick={{ fontSize: 11, fill: '#9ca3af' }} />

              <YAxis domain={[0, 1]} tick={{ fontSize: 11, fill: '#6b7280' }} width={30} />

              <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151' }} />

              <Bar dataKey="v" fill="#6366f1" radius={[4, 4, 0, 0]} />

            </BarChart>

          </ResponsiveContainer>

        </div>

      </Section>

    </div>

  );

};



// ------------------------------------------------------------ message tables

const FILTERS = ['all', 'valid', 'suspicious', 'malicious', 'emergency'] as const;



const MessageRowDetails: React.FC<{ m: any }> = ({ m }) => (

  <tr className="bg-black/20">

    <td colSpan={11} className="px-3 py-2 text-xs text-gray-400">

      <div className="grid grid-cols-4 gap-2">

        <div>Msg ID: <span className="font-mono text-gray-200">{m.msg_id}</span></div>

        <div>Pseudonym: <span className="font-mono text-gray-200">{m.pseudonym || '—'}</span></div>

        <div>Sender location: <span className="font-mono text-gray-200">{m.sender_pos?.map((c: number) => c.toFixed(0)).join(', ')}</span></div>

        {m.receiver_pos && <div>Receiver location: <span className="font-mono text-gray-200">{m.receiver_pos.map((c: number) => c.toFixed(0)).join(', ')}</span></div>}

        {m.latency_ms !== undefined && <div>Latency: <span className="text-gray-200">{m.latency_ms} ms</span></div>}

        <div>Signature: <span className={m.sig_status === 'valid' ? 'text-emerald-400' : 'text-rose-400'}>{m.sig_status}</span></div>

        <div>Misbehaviour probability: <span className="text-gray-200">{pct(m.probability)}</span></div>

        <div>Accountable vehicle: <span className="font-mono text-gray-200">{m.accused ?? 'unattributed'}</span></div>

        {m.event && <div className="col-span-2">Event: <span className="text-gray-200">{m.event.event_type} — {m.event.description} (severity {m.event.severity})</span></div>}

        {m.reasons?.length > 0 && <div className="col-span-2">Triggered checks: <span className="text-amber-300">{m.reasons.join(', ')}</span></div>}

      </div>

    </td>

  </tr>

);



const TYPE_BADGE: Record<string, string> = {

  DENM: 'bg-purple-500/20 text-purple-300',

  VAM: 'bg-emerald-500/15 text-emerald-300',

  MBR: 'bg-cyan-500/20 text-cyan-300',

};



const MessageTable: React.FC<{ rows: any[]; showReceiver?: boolean }> = ({ rows, showReceiver }) => {

  const [open, setOpen] = useState<string | null>(null);

  const navigate = useNavigate();

  if (!rows.length) return <Empty>No messages match the current filters.</Empty>;

  return (

    <div className="overflow-x-auto">

      <table className="w-full text-sm">

        <thead className="text-[11px] uppercase text-gray-500 border-b border-white/10">

          <tr>

            <th className="text-left py-2 px-2">Time</th>

            <th className="text-left px-2">Sender</th>

            {showReceiver && <th className="text-left px-2">Receiver</th>}

            <th className="text-left px-2">Type</th>

            <th className="text-left px-2">Message</th>

            <th className="text-left px-2">Status</th>

            {showReceiver && <th className="text-right px-2">Distance</th>}

            <th className="text-right px-2">Sender trust</th>

            <th className="text-right px-2">AI conf.</th>

            <th className="text-left px-2">Classification</th>

            <th className="text-left px-2">Blockchain TX</th>

          </tr>

        </thead>

        <tbody>

          {rows.map((m) => {

            const key = m.msg_id + (m.receiver ?? '');

            return (

              <React.Fragment key={key}>

                <tr

                  onClick={() => setOpen(open === key ? null : key)}

                  className={`border-b border-white/5 cursor-pointer hover:bg-white/[0.03] ${m.classification === 'Malicious' ? 'bg-rose-500/[0.06]' : m.classification === 'Suspicious' ? 'bg-amber-500/[0.05]' : ''}`}

                >

                  <td className="py-1.5 px-2 font-mono text-xs text-gray-400">{fmtTime(m.time)}</td>

                  <td className="px-2 font-mono">

                    {m.privacy_masked || m.type === 'MBR' || m.type === 'VAM' ? <span>{m.sender}</span> : (

                      <button className="hover:underline" onClick={(e) => { e.stopPropagation(); navigate(`/vehicle/${m.accused ?? m.sender}`); }}>{m.sender}</button>

                    )}

                  </td>

                  {showReceiver && <td className="px-2 font-mono text-gray-300">{m.receiver}</td>}

                  <td className="px-2"><span className={`text-xs px-1.5 py-0.5 rounded ${TYPE_BADGE[m.type] ?? 'bg-indigo-500/15 text-indigo-300'}`}>{m.type}</span></td>

                  <td className="px-2 text-gray-200">{m.emergency ? '🚨 ' : ''}{m.content}</td>

                  <td className="px-2"><ClassBadge value={m.classification} /></td>

                  {showReceiver && <td className="px-2 text-right text-gray-300">{m.distance?.toFixed(0)} m</td>}

                  <td className="px-2 text-right">{(m.sender_trust * 100).toFixed(1)}</td>

                  <td className="px-2 text-right">{pct(m.ai_confidence)}</td>

                  <td className="px-2 text-xs">{m.classification === 'Normal' ? <span className="text-gray-500">normal</span> : <span className="text-rose-300">{ATTACK_LABELS[m.attack_type] ?? m.attack_type}</span>}</td>

                  <td className="px-2 font-mono text-xs text-cyan-400">{m.tx_id ?? '—'}</td>

                </tr>

                {open === key && <MessageRowDetails m={m} />}

              </React.Fragment>

            );

          })}

        </tbody>

      </table>

    </div>

  );

};



const ReceivedTab: React.FC<{ id: string }> = ({ id }) => {

  const [filter, setFilter] = useState<(typeof FILTERS)[number]>('all');

  const [sender, setSender] = useState('');

  const [type, setType] = useState('');

  const [from, setFrom] = useState('');

  const [to, setTo] = useState('');

  const [live, setLive] = useState(true);

  const privacy = useStore((s) => s.privacyMode);

  const path = `/vehicles/${id}/messages/received${qs({ filter, sender, type, from, to, limit: 300, privacy: privacy ? 'true' : undefined })}`;

  const [data, reload] = usePoll<any>(path, live ? 2000 : 0);

  return (

    <Section

      title="Received message history"

      right={<span className="text-xs text-gray-500">{data ? `${data.messages.length} shown · ${data.total_buffered} buffered` : ''}</span>}

    >

      <div className="flex flex-wrap items-center gap-2 mb-3 text-sm">

        {FILTERS.map((f) => (

          <button key={f} className={`tab-btn capitalize ${filter === f ? 'tab-btn--active' : ''}`} onClick={() => setFilter(f)}>{f}</button>

        ))}

        <select className="input text-sm py-1" value={sender} onChange={(e) => setSender(e.target.value)}>

          <option value="">All senders</option>

          {(data?.senders ?? []).map((s: string) => <option key={s} value={s}>{s}</option>)}

        </select>

        <select className="input text-sm py-1" value={type} onChange={(e) => setType(e.target.value)}>

          <option value="">All types</option>

          <option value="CAM">CAM</option>

          <option value="DENM">DENM</option>

          <option value="VAM">VAM (pedestrian)</option>

          <option value="MBR">MBR (RSU warning)</option>

        </select>

        <input className="input text-sm py-1 w-24" placeholder="from (s)" value={from} onChange={(e) => setFrom(e.target.value)} />

        <input className="input text-sm py-1 w-24" placeholder="to (s)" value={to} onChange={(e) => setTo(e.target.value)} />

        <label className="flex items-center gap-1 text-xs text-gray-400 ml-auto">

          <input type="checkbox" checked={live} onChange={(e) => setLive(e.target.checked)} /> live

        </label>

        <button className="btn-secondary px-2 py-1" onClick={reload}><RefreshCw size={14} /></button>

      </div>

      {data ? <MessageTable rows={data.messages} showReceiver /> : <Empty>Loading…</Empty>}

    </Section>

  );

};



const SentTab: React.FC<{ id: string }> = ({ id }) => {

  const [filter, setFilter] = useState<(typeof FILTERS)[number]>('all');

  const privacy = useStore((s) => s.privacyMode);

  const [data] = usePoll<any>(`/vehicles/${id}/messages/sent${qs({ filter, limit: 300, privacy: privacy ? 'true' : undefined })}`, 2000);

  return (

    <Section title="Messages sent" right={<span className="text-xs text-gray-500">{data?.messages.length ?? 0} shown</span>}>

      <div className="flex gap-2 mb-3">

        {FILTERS.map((f) => (

          <button key={f} className={`tab-btn capitalize ${filter === f ? 'tab-btn--active' : ''}`} onClick={() => setFilter(f)}>{f}</button>

        ))}

      </div>

      {data ? <MessageTable rows={data.messages} /> : <Empty>Loading…</Empty>}

    </Section>

  );

};



// ------------------------------------------------------------------ Behavior

const BehaviorTab: React.FC<{ id: string; d: any }> = ({ id, d }) => {

  const [data] = usePoll<any>(`/vehicles/${id}/messages/sent${qs({ type: 'CAM', limit: 300 })}`, 2000);

  const rows = useMemo(() => (data?.messages ?? []).slice().reverse().map((m: any) => ({

    t: m.time, speed: +(m.speed * 3.6).toFixed(1), heading: m.heading,

    flagged: m.classification !== 'Normal' ? +(m.speed * 3.6).toFixed(1) : null,

  })), [data]);

  return (

    <div className="grid grid-cols-2 gap-4">

      <Section title="Claimed speed over time (km/h) — red = flagged">

        <div className="h-64">

          <ResponsiveContainer width="100%" height="100%">

            <ComposedChart data={rows}>

              <CartesianGrid stroke="#1f2937" />

              <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tick={{ fontSize: 11, fill: '#6b7280' }} />

              <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} width={35} />

              <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151' }} />

              <Line dataKey="speed" stroke="#06b6d4" dot={false} isAnimationActive={false} />

              <Scatter dataKey="flagged" fill="#f43f5e" />

            </ComposedChart>

          </ResponsiveContainer>

        </div>

      </Section>

      <Section title="Claimed heading over time (°)">

        <div className="h-64">

          <ResponsiveContainer width="100%" height="100%">

            <LineChart data={rows}>

              <CartesianGrid stroke="#1f2937" />

              <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tick={{ fontSize: 11, fill: '#6b7280' }} />

              <YAxis domain={[0, 360]} tick={{ fontSize: 11, fill: '#6b7280' }} width={35} />

              <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151' }} />

              <Line dataKey="heading" stroke="#a855f7" dot={false} isAnimationActive={false} />

            </LineChart>

          </ResponsiveContainer>

        </div>

      </Section>

      <Section title="Current state (ground truth from SUMO)" className="col-span-2">

        <div className="grid grid-cols-4 gap-4 text-sm">

          <KV label="Real speed" value={`${(d.speed * 3.6).toFixed(1)} km/h`} />

          <KV label="Real acceleration" value={`${d.acceleration.toFixed(2)} m/s²`} />

          <KV label="Real heading" value={`${d.heading.toFixed(0)}°`} />

          <KV label="Lane" value={d.lane || '—'} mono />

        </div>

      </Section>

    </div>

  );

};



// --------------------------------------------------------------- AI Analysis

const AITab: React.FC<{ id: string; d: any }> = ({ id, d }) => {

  const [flagged] = usePoll<any>(`/vehicles/${id}/messages/sent${qs({ limit: 300 })}`, 2000);

  const [attacks] = usePoll<any>(`/vehicles/${id}/attacks`, 3000);

  const rows = useMemo(() => (flagged?.messages ?? []).slice().reverse().map((m: any) => ({ t: m.time, p: +(m.probability * 100).toFixed(1) })), [flagged]);

  const latest = attacks?.evidence?.[0];

  return (

    <div className="grid grid-cols-3 gap-4">

      <Section title="Misbehaviour probability per message (%)" className="col-span-2">

        <div className="h-60">

          <ResponsiveContainer width="100%" height="100%">

            <LineChart data={rows}>

              <CartesianGrid stroke="#1f2937" />

              <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tick={{ fontSize: 11, fill: '#6b7280' }} />

              <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#6b7280' }} width={35} />

              <ReferenceLine y={80} stroke="#f43f5e88" strokeDasharray="4 4" label={{ value: 'malicious', fill: '#f43f5e', fontSize: 10 }} />

              <ReferenceLine y={50} stroke="#f59e0b88" strokeDasharray="4 4" label={{ value: 'suspicious', fill: '#f59e0b', fontSize: 10 }} />

              <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151' }} />

              <Line dataKey="p" stroke="#f43f5e" dot={false} isAnimationActive={false} />

            </LineChart>

          </ResponsiveContainer>

        </div>

      </Section>

      <Section title="Detections by attack type">

        {Object.keys(d.attack_types).length === 0 ? <Empty>No misbehaviour detected.</Empty> :

          Object.entries(d.attack_types).map(([k, n]) => <KV key={k} label={ATTACK_LABELS[k] ?? k} value={n as number} />)}

        <KV label="Last misbehaviour probability" value={pct(d.ai_score)} />

      </Section>

      <Section title="Latest explained detection" className="col-span-3">

        {!latest ? <Empty>No evidence record yet (created when probability &gt; 0.90).</Empty> : (

          <div className="grid grid-cols-2 gap-4 text-sm">

            <div>

              <KV label="Attack" value={latest.label} />

              <KV label="Classification" value={<ClassBadge value={latest.classification} />} />

              <KV label="AI probability (fused)" value={pct(latest.ai_probability)} />

              <KV label="Model" value={`${latest.model_label} (${pct(latest.model_probability)})`} />

              <KV label="Neighbour consensus" value={`${latest.flagging}/${latest.reporters} (${pct(latest.consensus)})`} />

              <KV label="Expected" value={latest.expected} />

              <KV label="Observed" value={<span className="text-rose-300">{latest.observed}</span>} />

            </div>

            <div>

              <h4 className="text-xs uppercase text-gray-500 mb-1">Triggered checks</h4>

              {latest.rule_hits.map((h: any) => (

                <div key={h.rule} className="mb-2 rounded bg-white/[0.03] px-2 py-1">

                  <div className="flex justify-between"><span className="text-amber-300 font-mono text-xs">{h.rule}</span><span className="text-xs">{pct(h.score)}</span></div>

                  <div className="text-xs text-gray-400">expected {h.expected} · observed {h.observed}</div>

                </div>

              ))}

            </div>

          </div>

        )}

      </Section>

    </div>

  );

};



// ------------------------------------------------------------- Trust history

const TrustTab: React.FC<{ id: string }> = ({ id }) => {

  const [data] = usePoll<any>(`/vehicles/${id}/trust/history`, 2000);

  const history = data?.history ?? [];

  const chart = history.map((h: any) => ({ t: h.time, trust: +(h.new_score * 100).toFixed(1), drop: h.kind === 'penalty' ? +(h.new_score * 100).toFixed(1) : null }));

  return (

    <div className="space-y-4">

      <Section title="Trust over time">

        <div className="h-72">

          <ResponsiveContainer width="100%" height="100%">

            <ComposedChart data={chart}>

              <CartesianGrid stroke="#1f2937" />

              <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tickFormatter={(t) => fmtTime(t)} tick={{ fontSize: 11, fill: '#6b7280' }} />

              <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#6b7280' }} width={35} />

              <ReferenceLine y={60} stroke="#10b98155" strokeDasharray="4 4" label={{ value: 'trusted', fill: '#10b981', fontSize: 10 }} />

              <ReferenceLine y={30} stroke="#f43f5e55" strokeDasharray="4 4" label={{ value: 'malicious', fill: '#f43f5e', fontSize: 10 }} />

              <Tooltip labelFormatter={(t) => fmtTime(t as number)} contentStyle={{ background: '#111827', border: '1px solid #374151' }} />

              <Line type="stepAfter" dataKey="trust" stroke="#6366f1" strokeWidth={2} dot={false} isAnimationActive={false} />

              <Scatter dataKey="drop" fill="#f43f5e" />

            </ComposedChart>

          </ResponsiveContainer>

        </div>

      </Section>

      <Section title="What changed the trust score">

        <table className="w-full text-sm">

          <thead className="text-[11px] uppercase text-gray-500 border-b border-white/10">

            <tr><th className="text-left py-2">Time</th><th className="text-right">Before</th><th className="text-right">After</th><th className="text-right">Δ</th><th className="text-left pl-4">Reason</th></tr>

          </thead>

          <tbody>

            {history.slice().reverse().map((h: any, i: number) => {

              const delta = (h.new_score - h.old_score) * 100;

              return (

                <tr key={i} className="border-b border-white/5">

                  <td className="py-1.5 font-mono text-xs text-gray-400">{fmtTime(h.time)}</td>

                  <td className="text-right">{(h.old_score * 100).toFixed(1)}</td>

                  <td className="text-right">{(h.new_score * 100).toFixed(1)}</td>

                  <td className={`text-right font-mono ${delta < 0 ? 'text-rose-400' : delta > 0 ? 'text-emerald-400' : 'text-gray-500'}`}>{delta > 0 ? '+' : ''}{delta.toFixed(1)}</td>

                  <td className="pl-4 text-gray-200">{h.reason}</td>

                </tr>

              );

            })}

          </tbody>

        </table>

      </Section>

    </div>

  );

};



// ------------------------------------------------------------------- Attacks

const EvidenceCard: React.FC<{ e: any }> = ({ e: raw }) => {

  const privacy = useStore((s) => s.privacyMode);

  const e = privacy ? { ...raw, vehicle_id: raw.pseudonym ?? 'anonymous', sender: raw.pseudonym ?? 'anonymous',

    location: raw.location?.map((c: number) => Math.round(c / 50) * 50) } : raw;

  const [verify, setVerify] = useState<any>(null);

  const check = (tamper: boolean) => api.get(`/evidence/${e.attack_id}${tamper ? '?tamper=true' : ''}`).then(setVerify);

  return (

    <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3 text-sm">

      <div className="flex justify-between items-center mb-2">

        <div className="font-bold text-rose-300">{e.attack_id} · {e.label}</div>

        <div className="text-xs font-mono text-gray-500">{fmtTime(e.time)} · block {e.block ?? 'pending'}</div>

      </div>

      <div className="grid grid-cols-3 gap-x-6">

        <KV label="Vehicle" value={e.vehicle_id} mono />

        <KV label="Sender (claimed)" value={e.sender} mono />

        <KV label="Location" value={e.location?.join(', ')} mono />

        <KV label="Registered / claimed type" value={`${e.registered_type} / ${e.claimed_type}`} />

        <KV label="AI probability" value={pct(e.ai_probability)} />

        <KV label="Receivers" value={e.receivers} />

        <KV label="Expected" value={e.expected} />

        <KV label="Observed" value={<span className="text-rose-300">{e.observed}</span>} />

        <KV label="Trust before → after" value={`${(e.trust_before * 100).toFixed(1)} → ${(e.trust_after * 100).toFixed(1)}`} />

        <KV label="Evidence hash" value={e.hash.slice(0, 20) + '…'} mono />

        <KV label="Blockchain TX" value={e.tx_id ?? '—'} mono />

        <KV label="Reporting RSU" value={e.reporting_rsu} />

      </div>

      <details className="mt-2 text-xs text-gray-400">

        <summary className="cursor-pointer">Original message</summary>

        <pre className="mt-1 bg-black/40 p-2 rounded overflow-x-auto">{JSON.stringify(e.original_message, null, 2)}</pre>

      </details>

      <div className="flex gap-2 mt-2 items-center">

        <button className="btn-secondary px-2 py-1 text-xs" onClick={() => check(false)}>Verify against blockchain</button>

        <button className="btn-secondary px-2 py-1 text-xs" onClick={() => check(true)}>Simulate tampering</button>

        {verify && (

          <span className={`flex items-center gap-1 text-xs ${verify.verification.valid ? 'text-emerald-400' : 'text-rose-400'}`}>

            {verify.verification.valid ? <ShieldCheck size={14} /> : <ShieldX size={14} />}

            {verify.verification.valid ? 'hash matches on-chain record' : 'hash MISMATCH — record was modified'}

            {verify.verification.confirmed ? ` (block ${verify.verification.block})` : ' (tx pending)'}

          </span>

        )}

      </div>

    </div>

  );

};



const AttacksTab: React.FC<{ id: string }> = ({ id }) => {

  const [data] = usePoll<any>(`/vehicles/${id}/attacks`, 3000);

  if (!data) return <Empty>Loading…</Empty>;

  return (

    <div className="space-y-4">

      {data.attack_report && <BeforeAfter report={data.attack_report} />}

      <Section title={`Evidence records (${data.evidence.length})`}>

        {data.evidence.length === 0 ? <Empty>No evidence recorded for this vehicle.</Empty> :

          <div className="space-y-3">{data.evidence.map((e: any) => <EvidenceCard key={e.attack_id} e={e} />)}</div>}

      </Section>

      <Section title="Latest neighbour reports about this vehicle">

        <div className="flex flex-wrap gap-1 text-xs">

          {data.neighbour_reports.length === 0 && <span className="text-gray-500">none</span>}

          {data.neighbour_reports.slice().reverse().map((r: any, i: number) => (

            <span key={i} className={`px-1.5 py-0.5 rounded font-mono ${r.verdict === 'Normal' ? 'bg-emerald-500/10 text-emerald-300' : 'bg-rose-500/10 text-rose-300'}`}>

              {r.reporter_id}:{r.verdict[0]}

            </span>

          ))}

        </div>

      </Section>

    </div>

  );

};



export const BeforeAfter: React.FC<{ report: any }> = ({ report }) => {

  const b = report.before, a = report.after, det = report.first_detection;

  return (

    <Section title={`Before / after attack — ${report.label}`}>

      <div className="grid grid-cols-4 gap-3 text-sm">

        <div className="rounded-lg bg-emerald-500/5 border border-emerald-500/30 p-3">

          <div className="text-xs uppercase text-emerald-400 mb-1">Before attack</div>

          <div>Trust: <b>{(b.trust * 100).toFixed(1)}</b></div>

          <div>Status: <StatusBadge status={b.status} /></div>

          <div className="text-xs text-gray-400 mt-1">type {b.registered_type}</div>

        </div>

        <div className="rounded-lg bg-amber-500/5 border border-amber-500/30 p-3">

          <div className="text-xs uppercase text-amber-400 mb-1">Attack @ {fmtTime(report.launched_at)}</div>

          <div className="font-semibold">{report.label}</div>

          {report.attack_type === 'emergency_spoofing' && <div className="text-xs text-gray-300 mt-1">"I am an {a.claimed_type}"</div>}

          <div className="text-xs text-gray-400 mt-1">{a.attack_running ? 'still running' : 'stopped'}</div>

        </div>

        <div className="rounded-lg bg-indigo-500/5 border border-indigo-500/30 p-3">

          <div className="text-xs uppercase text-indigo-300 mb-1">Detection</div>

          {det ? (

            <>

              <div>AI probability: <b>{pct(det.probability)}</b></div>

              <div>Detected after <b>{det.latency_s.toFixed(1)} s</b></div>

              <div className="text-xs text-gray-400">as {ATTACK_LABELS[det.attack_type] ?? det.attack_type}</div>

            </>

          ) : <div className="text-gray-500">not detected yet</div>}

        </div>

        <div className="rounded-lg bg-rose-500/5 border border-rose-500/30 p-3">

          <div className="text-xs uppercase text-rose-400 mb-1">After</div>

          <div>Trust: <b>{(b.trust * 100).toFixed(1)} → {(a.trust * 100).toFixed(1)}</b></div>

          <div>Status: <StatusBadge status={a.status} /></div>

          <div className="text-xs text-gray-400 mt-1">Blockchain: {report.evidence_ids.length} evidence · {report.tx_ids.length} tx</div>

        </div>

      </div>

      {report.trust_timeline?.length > 1 && (

        <div className="h-40 mt-3">

          <ResponsiveContainer width="100%" height="100%">

            <LineChart data={report.trust_timeline.map((e: any) => ({ t: e.time, trust: +(e.new_score * 100).toFixed(1) }))}>

              <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tickFormatter={(t) => fmtTime(t)} tick={{ fontSize: 10, fill: '#6b7280' }} />

              <YAxis domain={[0, 100]} width={30} tick={{ fontSize: 10, fill: '#6b7280' }} />

              <ReferenceLine x={report.launched_at} stroke="#f59e0b" strokeDasharray="3 3" label={{ value: 'attack', fill: '#f59e0b', fontSize: 10 }} />

              <Tooltip labelFormatter={(t) => fmtTime(t as number)} contentStyle={{ background: '#111827', border: '1px solid #374151' }} />

              <Line type="stepAfter" dataKey="trust" stroke="#f43f5e" strokeWidth={2} dot isAnimationActive={false} />

            </LineChart>

          </ResponsiveContainer>

        </div>

      )}

    </Section>

  );

};



// ---------------------------------------------------------------- Blockchain

const BlockchainTab: React.FC<{ id: string }> = ({ id }) => {

  const [data] = usePoll<any>(`/vehicles/${id}/blockchain`, 3000);

  if (!data) return <Empty>Loading…</Empty>;

  return (

    <Section title={`Blockchain records (${data.transactions.length})`} right={<span className="text-xs font-mono text-gray-500">vehicle hash {data.vehicle_hash}</span>}>

      <table className="w-full text-sm">

        <thead className="text-[11px] uppercase text-gray-500 border-b border-white/10">

          <tr><th className="text-left py-2">TX</th><th className="text-left">Type</th><th className="text-left">Time</th><th className="text-left">Block</th><th className="text-left">RSU</th><th className="text-left">Event</th><th className="text-right">Score</th><th className="text-right">Trust</th></tr>

        </thead>

        <tbody>

          {data.transactions.map((tx: any) => (

            <tr key={tx.tx_id} className="border-b border-white/5">

              <td className="py-1.5 font-mono text-xs text-cyan-400">{tx.tx_id}</td>

              <td className="text-xs">{tx.tx_type}</td>

              <td className="font-mono text-xs text-gray-400">{fmtTime(tx.timestamp)}</td>

              <td>{tx.confirmed ? `#${tx.block}` : <span className="text-amber-400 text-xs">pending</span>}</td>

              <td className="text-xs">{tx.reporting_rsu}</td>

              <td className="text-xs">{tx.event_type ? (ATTACK_LABELS[tx.event_type] ?? tx.event_type) : tx.data?.registered_type ?? '—'}</td>

              <td className="text-right">{tx.misbehavior_score !== null ? pct(tx.misbehavior_score) : '—'}</td>

              <td className="text-right font-mono text-xs">

                {tx.trust_before !== null && tx.trust_before !== undefined ? `${(tx.trust_before * 100).toFixed(1)} → ` : ''}

                {tx.trust_after !== null && tx.trust_after !== undefined ? (tx.trust_after * 100).toFixed(1) : '—'}

              </td>

            </tr>

          ))}

        </tbody>

      </table>

    </Section>

  );

};
