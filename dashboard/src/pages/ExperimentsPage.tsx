import React, { useEffect, useState } from 'react';

import { FlaskConical, Play } from 'lucide-react';

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

import { Section, Empty } from '../components/ui';

import { api, pct } from '../api';



const COLUMNS: { key: string; label: string; fmt: (v: any) => string }[] = [

  { key: 'detection_rate', label: 'Detection rate', fmt: (v) => pct(v) },

  { key: 'precision', label: 'Precision', fmt: (v) => pct(v) },

  { key: 'false_positive_rate', label: 'FPR', fmt: (v) => pct(v, 3) },

  { key: 'malicious_acceptance_rate', label: 'Malicious accepted', fmt: (v) => pct(v, 2) },

  { key: 'honest_rejection_rate', label: 'Honest rejected', fmt: (v) => pct(v, 3) },

  { key: 'detection_latency_s', label: 'Detect (s)', fmt: (v) => (v == null ? '—' : v.toFixed(2)) },

  { key: 'isolation_time_s', label: 'Isolate (s)', fmt: (v) => (v == null ? '—' : v.toFixed(2)) },

  { key: 'attackers_isolated', label: 'Attackers isolated', fmt: (v) => pct(v, 0) },

  { key: 'innocents_blacklisted', label: 'Innocents blacklisted', fmt: (v) => (v == null ? '—' : v.toFixed(1)) },

  { key: 'bc_tx_latency_s', label: 'Ledger latency (s)', fmt: (v) => (v == null ? '—' : v.toFixed(3)) },

  { key: 'tamper_detected', label: 'Tamper detected', fmt: (v) => (v == null ? '—' : v ? 'yes' : 'no') },

];



const CHARTS = [

  { key: 'detection_rate', label: 'Detection rate (%)', scale: 100, color: '#10b981' },

  { key: 'malicious_acceptance_rate', label: 'Malicious messages accepted (%)', scale: 100, color: '#f43f5e' },

  { key: 'isolation_time_s', label: 'Time to isolate attacker (s)', scale: 1, color: '#f59e0b' },

  { key: 'bc_tx_latency_s', label: 'Trust record latency (s)', scale: 1, color: '#6366f1' },

];



export const ExperimentsPage: React.FC = () => {

  const [configs, setConfigs] = useState<any[]>([]);

  const [jobs, setJobs] = useState<any[]>([]);

  const [results, setResults] = useState<any[]>([]);

  const [selected, setSelected] = useState<string>('');

  const [data, setData] = useState<any>(null);

  const [duration, setDuration] = useState('');

  const [reps, setReps] = useState('');

  const [error, setError] = useState('');



  const refresh = () => {

    api.get('/experiments/jobs').then(setJobs).catch(() => {});

    api.get('/experiments/results').then((r) => { setResults(r); setSelected((s) => s || r[0]?.id || ''); }).catch(() => {});

  };

  useEffect(() => {

    api.get('/experiments/configs').then((c) => setConfigs(c.configs)).catch(() => {});

    refresh();

    const t = setInterval(refresh, 2500);

    return () => clearInterval(t);

  }, []);

  useEffect(() => {

    if (selected) api.get(`/experiments/results/${selected}`).then(setData).catch(() => setData(null));

  }, [selected, results.length]);



  const start = (body: any) => {

    setError('');

    api.post('/experiment/start', { ...body, duration: duration ? +duration : undefined, repetitions: reps ? +reps : undefined })

      .then(refresh).catch((e) => setError(e.message));

  };

  const running = jobs.find((j) => j.status === 'running');

  const rows = data?.results ?? [];



  return (

    <div className="p-6 h-full overflow-y-auto page-enter space-y-4">

      <h1 className="text-2xl font-bold text-white flex items-center gap-2"><FlaskConical className="text-purple-400" /> Experiments</h1>

      <p className="text-sm text-gray-400 -mt-2">

        Each experiment runs the full live pipeline headless in a separate process (own SUMO instance) and measures results against the attack injector&apos;s ground truth.

      </p>



      <div className="grid grid-cols-3 gap-4">

        <Section title="Run an experiment" className="col-span-2">

          <div className="flex gap-2 mb-3 text-sm items-center">

            <span className="text-gray-400">Overrides:</span>

            <input className="input w-36 py-1" placeholder="sim seconds" value={duration} onChange={(e) => setDuration(e.target.value)} />

            <input className="input w-32 py-1" placeholder="repetitions" value={reps} onChange={(e) => setReps(e.target.value)} />

            <button className="btn-primary ml-auto" disabled={!!running} onClick={() => start({ suite: 'baselines' })}>Baseline comparison</button>

            <button className="btn-primary" disabled={!!running} onClick={() => start({ suite: 'ablation' })}>Trust ablation</button>

          </div>

          {error && <div className="text-rose-400 text-sm mb-2">{error}</div>}

          <div className="grid grid-cols-2 gap-2">

            {configs.map((c) => (

              <div key={c.id} className="rounded-md border border-white/10 px-3 py-2 flex gap-2 items-start">

                <div className="flex-1">

                  <div className="text-sm font-medium text-gray-100">{c.name}</div>

                  <div className="text-[11px] text-gray-500">{c.description}</div>

                  {c.variants.length > 0 && <div className="text-[11px] text-indigo-300">variants: {c.variants.join(' · ')}</div>}

                </div>

                <button className="btn-secondary px-2 py-1" disabled={!!running} title="run" onClick={() => start({ config: c.id })}><Play size={14} /></button>

              </div>

            ))}

          </div>

        </Section>

        <Section title="Jobs">

          {jobs.length === 0 ? <Empty>No experiment started from the dashboard yet.</Empty> : jobs.slice(0, 4).map((j) => (

            <div key={j.id} className="mb-3 text-xs">

              <div className="flex justify-between">

                <span className="font-mono">{j.target}</span>

                <span className={j.status === 'running' ? 'text-amber-400' : j.status === 'done' ? 'text-emerald-400' : 'text-rose-400'}>{j.status}</span>

              </div>

              <pre className="mt-1 bg-black/40 rounded p-2 text-[10px] text-gray-400 max-h-40 overflow-auto whitespace-pre-wrap">{j.log_tail.join('\n')}</pre>

            </div>

          ))}

        </Section>

      </div>



      <Section title="Results" right={

        <select className="input text-sm py-1" value={selected} onChange={(e) => setSelected(e.target.value)}>

          {results.map((r) => <option key={r.id} value={r.id}>{r.created} · {r.title} ({r.experiments.length})</option>)}

        </select>

      }>

        {rows.length === 0 ? <Empty>No results yet. Run an experiment above or from the command line.</Empty> : (

          <>

            <div className="overflow-x-auto">

              <table className="w-full text-sm">

                <thead className="text-[11px] uppercase text-gray-500 border-b border-white/10">

                  <tr><th className="text-left py-2">Experiment</th>{COLUMNS.map((c) => <th key={c.key} className="text-right px-2">{c.label}</th>)}</tr>

                </thead>

                <tbody>

                  {rows.map((r: any) => (

                    <tr key={r.spec.name} className="border-b border-white/5">

                      <td className="py-1.5">

                        <div className="text-gray-100">{r.spec.name}</div>

                        <div className="text-[10px] text-gray-500">{r.spec.scenario} · {r.spec.duration}s ×{r.spec.repetitions} · detector {r.spec.detector_mode} · trust {r.spec.trust_enabled ? 'on' : 'off'} · {r.spec.ledger}</div>

                      </td>

                      {COLUMNS.map((c) => <td key={c.key} className="text-right px-2 font-mono text-xs">{c.fmt(r.summary[c.key])}</td>)}

                    </tr>

                  ))}

                </tbody>

              </table>

            </div>

            {rows.length > 1 && (

              <div className="grid grid-cols-2 gap-4 mt-4">

                {CHARTS.map((ch) => (

                  <div key={ch.key}>

                    <div className="text-xs text-gray-400 mb-1">{ch.label}</div>

                    <div className="h-44">

                      <ResponsiveContainer width="100%" height="100%">

                        <BarChart data={rows.map((r: any) => ({ name: r.spec.name, v: r.summary[ch.key] == null ? 0 : +(r.summary[ch.key] * ch.scale).toFixed(3) }))}>

                          <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#9ca3af' }} interval={0} />

                          <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} width={40} />

                          <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151' }} />

                          <Bar dataKey="v" fill={ch.color} radius={[4, 4, 0, 0]} />

                        </BarChart>

                      </ResponsiveContainer>

                    </div>

                  </div>

                ))}

              </div>

            )}

          </>

        )}

      </Section>

    </div>

  );

};
