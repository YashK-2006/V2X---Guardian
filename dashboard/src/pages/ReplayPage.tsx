import React, { useEffect, useMemo, useState } from 'react';

import { History, Play, Pause, SkipBack, RefreshCw } from 'lucide-react';

import { VehicleMap, type ReplayFrame } from '../components/VehicleMap';

import { Section, Empty, StatusBadge } from '../components/ui';

import { api, fmtTime } from '../api';

import { ATTACK_LABELS, type VehicleStatus } from '../stores/useStore';



interface RunMeta { run_id: string; scenario_name: string; started_at: number; sim_time: number; frames: number; current: boolean; mock_mode: boolean; attacks: number }

interface RawFrame { t: number; v: any[][]; p: any[][]; a: number }



export const ReplayPage: React.FC = () => {

  const [runs, setRuns] = useState<RunMeta[]>([]);

  const [runId, setRunId] = useState<string>('');

  const [frames, setFrames] = useState<RawFrame[]>([]);

  const [alerts, setAlerts] = useState<any[]>([]);

  const [idx, setIdx] = useState(0);

  const [playing, setPlaying] = useState(false);

  const [speed, setSpeed] = useState(4);

  const [loadedRun, setLoadedRun] = useState('');

  const loading = !!runId && loadedRun !== runId;



  const loadRuns = () => api.get<RunMeta[]>('/runs').then((r) => {

    setRuns(r);

    setRunId((cur) => cur || (r[0]?.run_id ?? ''));

  }).catch(() => {});

  useEffect(() => { loadRuns(); }, []);



  useEffect(() => {

    if (!runId) return;

    let alive = true;

    Promise.all([api.get(`/runs/${runId}/frames?max_frames=3000`), api.get(`/runs/${runId}/alerts`)])

      .then(([f, a]) => {

        if (!alive) return;

        setFrames(f.frames);

        setAlerts(a);

        setIdx(0);

        setPlaying(false);

        setLoadedRun(runId);

      })

      .catch(() => alive && setLoadedRun(runId));

    return () => { alive = false; };

  }, [runId]);



  useEffect(() => {

    if (!playing || frames.length < 2) return;

    const dt = (frames[1].t - frames[0].t) * 1000 / speed;

    const timer = setInterval(() => setIdx((i) => {

      if (i >= frames.length - 1) { setPlaying(false); return i; }

      return i + 1;

    }), Math.max(16, dt));

    return () => clearInterval(timer);

  }, [playing, speed, frames]);



  const frame = frames[idx];

  const replay: ReplayFrame | null = useMemo(() => frame ? {

    time: frame.t,

    vehicles: frame.v.map(([id, type, claimed, x, y, heading, status]) => ({ id, type, claimed_type: claimed, x, y, heading, status: status as VehicleStatus })),

    pedestrians: frame.p.map(([id, x, y]) => ({ id, x, y, heading: 0 })),

  } : null, [frame]);



  const counts = useMemo(() => {

    const c: Record<string, number> = { trusted: 0, suspicious: 0, malicious: 0, blacklisted: 0 };

    frame?.v.forEach((v) => { c[v[6]] = (c[v[6]] ?? 0) + 1; });

    return c;

  }, [frame]);

  const attackers = frame ? frame.v.filter((v) => v[8]) : [];

  const pastAlerts = frame ? alerts.filter((a) => a.time <= frame.t).sort((a, b) => b.time - a.time) : [];

  const meta = runs.find((r) => r.run_id === runId);



  return (

    <div className="p-6 h-full flex flex-col gap-4 page-enter overflow-y-auto">

      <div className="flex items-center gap-3">

        <h1 className="text-2xl font-bold text-white flex items-center gap-2"><History className="text-cyan-400" /> Simulation Replay</h1>

        <select className="input ml-4 min-w-[420px]" value={runId} onChange={(e) => setRunId(e.target.value)}>

          {runs.map((r) => (

            <option key={r.run_id} value={r.run_id}>

              {new Date(r.started_at * 1000).toLocaleString()} · {r.scenario_name} · {fmtTime(r.sim_time)}{r.current ? ' (live run)' : ''}

            </option>

          ))}

        </select>

        <button className="btn-secondary px-2 py-2" title="refresh" onClick={loadRuns}><RefreshCw size={14} /></button>

        {meta && <span className="text-xs text-gray-500">{meta.frames} frames · {meta.attacks} attacks · {meta.mock_mode ? 'mock traffic' : 'SUMO'}</span>}

      </div>



      {runs.length === 0 ? <Section title="No recorded runs"><Empty>Runs are recorded automatically while the simulation is running.</Empty></Section> : (

        <>

          <div className="glass-card p-3 flex items-center gap-3">

            <button className="btn-secondary px-2 py-1" onClick={() => { setIdx(0); setPlaying(false); }}><SkipBack size={16} /></button>

            <button className="btn-primary px-3 py-1 flex items-center gap-1" disabled={frames.length < 2} onClick={() => setPlaying(!playing)}>

              {playing ? <Pause size={16} /> : <Play size={16} />} {playing ? 'Pause' : 'Play'}

            </button>

            <input type="range" className="flex-1 accent-cyan-500" min={0} max={Math.max(0, frames.length - 1)} value={idx}

              onChange={(e) => { setIdx(+e.target.value); setPlaying(false); }} />

            <span className="font-mono text-sm text-gray-300 w-36 text-right">{frame ? fmtTime(frame.t) : '—'} / {frames.length ? fmtTime(frames[frames.length - 1].t) : '—'}</span>

            <select className="input text-sm py-1" value={speed} onChange={(e) => setSpeed(+e.target.value)}>

              {[1, 2, 4, 8, 16].map((s) => <option key={s} value={s}>×{s}</option>)}

            </select>

          </div>



          <div className="flex gap-4 min-h-[560px] flex-1">

            <div className="flex-[2] glass-card p-1">{loading ? <Empty>Loading frames…</Empty> : <VehicleMap replay={replay} />}</div>

            <div className="flex-1 min-w-[320px] max-w-[420px] flex flex-col gap-4">

              <Section title="Network state at this moment">

                <div className="flex flex-wrap gap-2">

                  {Object.entries(counts).map(([k, n]) => <span key={k} className="flex items-center gap-1 text-sm"><StatusBadge status={k} /> {n}</span>)}

                </div>

                <div className="mt-3 text-sm">

                  <div className="text-xs uppercase text-gray-500 mb-1">Active attackers (ground truth)</div>

                  {attackers.length === 0 ? <div className="text-gray-500 text-xs">none</div> : attackers.map((v) => (

                    <div key={v[0]} className="flex justify-between font-mono text-xs py-0.5">

                      <span>{v[0]} · {ATTACK_LABELS[v[8]] ?? v[8]}</span><span>trust {(v[7] * 100).toFixed(1)} · {v[6]}</span>

                    </div>

                  ))}

                </div>

              </Section>

              <Section title={`Alerts up to ${frame ? fmtTime(frame.t) : '—'}`} className="flex-1 overflow-hidden">

                <div className="space-y-1 max-h-[360px] overflow-y-auto text-xs">

                  {pastAlerts.length === 0 && <Empty>No alerts yet at this point.</Empty>}

                  {pastAlerts.slice(0, 80).map((a) => (

                    <button key={a.id} className="w-full text-left rounded px-2 py-1 bg-white/[0.02] hover:bg-white/[0.05]"

                      onClick={() => { const i = frames.findIndex((f) => f.t >= a.time); if (i >= 0) { setIdx(i); setPlaying(false); } }}>

                      <div className="flex justify-between"><span className={a.severity === 'critical' ? 'text-rose-300' : a.severity === 'warning' ? 'text-amber-300' : 'text-cyan-300'}>{a.title}</span><span className="font-mono text-gray-500">{fmtTime(a.time)}</span></div>

                      <div className="text-gray-400">{a.message}</div>

                    </button>

                  ))}

                </div>

              </Section>

            </div>

          </div>

        </>

      )}

    </div>

  );

};
