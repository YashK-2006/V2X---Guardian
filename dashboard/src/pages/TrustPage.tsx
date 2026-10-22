import React, { useEffect, useState } from 'react';

import { useNavigate } from 'react-router-dom';

import { Shield } from 'lucide-react';

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LineChart, Line, CartesianGrid } from 'recharts';

import { Section, Empty, StatusBadge } from '../components/ui';

import { api, fmtTime } from '../api';

import { useStore, TYPE_ICONS } from '../stores/useStore';



const WEIGHTS = [

  { key: 'alpha', label: 'α · AI detection' },

  { key: 'beta', label: 'β · Neighbour consensus' },

  { key: 'gamma', label: 'γ · Offence history' },

  { key: 'delta', label: 'δ · Blockchain record' },

] as const;



export const TrustPage: React.FC = () => {

  const navigate = useNavigate();

  const vehicles = useStore((s) => s.vehicles);

  const [overview, setOverview] = useState<any>(null);

  const [timeline, setTimeline] = useState<any[]>([]);

  const [weights, setWeights] = useState<Record<string, number> | null>(null);

  const [saved, setSaved] = useState('');



  useEffect(() => {

    const load = () => {

      api.get('/trust/overview').then((o) => { setOverview(o); setWeights((w) => w ?? o.weights); }).catch(() => {});

      api.get('/timeline').then(setTimeline).catch(() => {});

    };

    load();

    const t = setInterval(load, 3000);

    return () => clearInterval(t);

  }, []);



  const ranking = Object.values(vehicles).sort((a, b) => a.trust_score - b.trust_score);



  const apply = () => weights && api.post('/trust/weights', weights).then((w) => { setWeights(w); setSaved('applied'); setTimeout(() => setSaved(''), 2000); });



  return (

    <div className="p-6 h-full flex flex-col gap-4 page-enter overflow-y-auto">

      <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2"><Shield className="text-emerald-500" /> Trust &amp; Reputation Management</h1>



      <div className="grid grid-cols-3 gap-4">

        <Section title="Trust distribution" className="col-span-2">

          <div className="h-56">

            <ResponsiveContainer width="100%" height="100%">

              <BarChart data={overview?.distribution ?? []}>

                <XAxis dataKey="range" tick={{ fontSize: 11, fill: '#9ca3af' }} />

                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#6b7280' }} width={30} />

                <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151' }} />

                <Bar dataKey="count" radius={[4, 4, 0, 0]}>

                  {(overview?.distribution ?? []).map((_: any, i: number) => (

                    <Cell key={i} fill={i >= 6 ? '#10b981' : i >= 3 ? '#f59e0b' : '#f43f5e'} />

                  ))}

                </Bar>

              </BarChart>

            </ResponsiveContainer>

          </div>

          <p className="text-xs text-gray-500">

            Avg network trust {overview ? (overview.avg_trust * 100).toFixed(1) : '—'} · trusted ≥ {overview ? overview.thresholds.trusted * 100 : 60} ·

            malicious &lt; {overview ? overview.thresholds.malicious * 100 : 30} · blacklist &lt; {overview ? overview.thresholds.blacklist * 100 : 15}

          </p>

        </Section>



        <Section title="Trust model weights" right={saved && <span className="text-xs text-emerald-400">{saved}</span>}>

          <p className="text-xs text-gray-500 mb-3">penalty = S · (α·p_AI + β·consensus + γ·history + δ·ledger). Weights are normalised to sum to 1.</p>

          {weights && WEIGHTS.map((w) => (

            <div key={w.key} className="mb-3">

              <div className="flex justify-between text-sm mb-1"><span className="text-gray-300">{w.label}</span><span className="font-mono">{weights[w.key].toFixed(2)}</span></div>

              <input type="range" min={0} max={1} step={0.05} value={weights[w.key]} className="w-full accent-indigo-500"

                onChange={(e) => setWeights({ ...weights, [w.key]: parseFloat(e.target.value) })} />

            </div>

          ))}

          <button className="btn-primary w-full" onClick={apply}>Apply weights</button>

        </Section>

      </div>



      <div className="grid grid-cols-2 gap-4">

        <Section title="Network trust over time">

          <div className="h-56">

            <ResponsiveContainer width="100%" height="100%">

              <LineChart data={timeline.map((p) => ({ t: p.t, trusted: p.trusted, suspicious: p.suspicious, malicious: p.malicious, avg: +(p.avg_trust * 100).toFixed(1) }))}>

                <CartesianGrid stroke="#1f2937" />

                <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tickFormatter={(t) => fmtTime(t)} tick={{ fontSize: 10, fill: '#6b7280' }} />

                <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} width={30} />

                <Tooltip labelFormatter={(t) => fmtTime(t as number)} contentStyle={{ background: '#111827', border: '1px solid #374151' }} />

                <Line dataKey="trusted" stroke="#10b981" dot={false} isAnimationActive={false} />

                <Line dataKey="suspicious" stroke="#f59e0b" dot={false} isAnimationActive={false} />

                <Line dataKey="malicious" stroke="#f43f5e" dot={false} isAnimationActive={false} />

              </LineChart>

            </ResponsiveContainer>

          </div>

        </Section>



        <Section title="Recent trust decisions">

          <div className="max-h-56 overflow-y-auto space-y-1 text-sm">

            {!overview?.recent_changes?.length && <Empty>No trust changes due to misbehaviour yet.</Empty>}

            {overview?.recent_changes?.map((c: any, i: number) => (

              <button key={i} className="w-full text-left flex gap-3 hover:bg-white/[0.03] rounded px-1" onClick={() => navigate(`/vehicle/${c.vehicle_id}`)}>

                <span className="font-mono text-xs text-gray-500 w-14">{fmtTime(c.time)}</span>

                <span className="font-mono w-12">{c.vehicle_id}</span>

                <span className={`font-mono w-24 ${c.new_score < c.old_score ? 'text-rose-400' : 'text-emerald-400'}`}>

                  {(c.old_score * 100).toFixed(0)} → {(c.new_score * 100).toFixed(0)}

                </span>

                <span className="text-gray-300 truncate">{c.reason}</span>

              </button>

            ))}

          </div>

        </Section>

      </div>



      <Section title="Vehicle trust ranking (lowest first)">

        <table className="w-full text-sm">

          <thead className="text-[11px] uppercase text-gray-500 border-b border-white/10">

            <tr><th className="text-left py-1">Vehicle</th><th className="text-left">Type</th><th className="text-right">Trust</th><th className="text-right">Reputation</th><th className="text-left pl-4">Status</th><th className="text-right">Flagged msgs</th><th className="text-right">Blockchain records</th></tr>

          </thead>

          <tbody>

            {ranking.slice(0, 25).map((v) => (

              <tr key={v.id} className="border-b border-white/5 hover:bg-white/[0.03] cursor-pointer" onClick={() => navigate(`/vehicle/${v.id}`)}>

                <td className="py-1 font-mono">{v.id}</td>

                <td>{TYPE_ICONS[v.type]} {v.type}{v.claimed_type !== v.type ? <span className="text-rose-400"> (claims {v.claimed_type})</span> : ''}</td>

                <td className="text-right">{(v.trust_score * 100).toFixed(1)}</td>

                <td className="text-right">{(v.reputation * 100).toFixed(1)}</td>

                <td className="pl-4"><StatusBadge status={v.status} /></td>

                <td className="text-right">{v.suspicious_count + v.misbehavior_count}</td>

                <td className="text-right">{v.blockchain_records}</td>

              </tr>

            ))}

          </tbody>

        </table>

      </Section>

    </div>

  );

};
