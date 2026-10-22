import React, { useEffect, useMemo, useState } from 'react';

import { useNavigate } from 'react-router-dom';

import { Play, Pause, Square, FastForward, Rewind, RotateCcw, Crosshair, XCircle } from 'lucide-react';

import { api, fmtTime } from '../api';

import { useStore, TYPE_ICONS } from '../stores/useStore';

import { Section, KV, Empty, StatusBadge } from '../components/ui';

import { BeforeAfter } from './VehiclePage';



interface AttackType { id: string; label: string; family: string; description: string }

interface Scenario { id: string; name: string; description: string; attacks: string[]; density_period: number }



export const ControlCenterPage: React.FC = () => {

  const navigate = useNavigate();

  const { isRunning, paused, speed, simTime, scenario, activeAttacks, stats } = useStore();

  const vehicles = useStore((s) => s.vehicles);

  const [attackTypes, setAttackTypes] = useState<AttackType[]>([]);

  const [scenarios, setScenarios] = useState<Scenario[]>([]);

  const [chosenScenario, setChosenScenario] = useState('');

  const [selected, setSelected] = useState<Set<string>>(new Set(['emergency_spoofing']));

  const [target, setTarget] = useState('');

  const [tracked, setTracked] = useState<string | null>(null);

  const [comparison, setComparison] = useState<any>(null);

  const [busy, setBusy] = useState(false);

  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);



  useEffect(() => {

    api.get<AttackType[]>('/attacks/types').then(setAttackTypes).catch(() => {});

    api.get<{ current: string; scenarios: Scenario[] }>('/scenarios').then((r) => {

      setScenarios(r.scenarios);

      setChosenScenario(r.current);

    }).catch(() => {});

  }, []);



  useEffect(() => {

    if (!tracked) return;

    const load = () => api.get(`/attacks/${tracked}/comparison`).then(setComparison).catch(() => {});

    load();

    const t = setInterval(load, 1500);

    return () => clearInterval(t);

  }, [tracked]);



  const eligible = useMemo(

    () => Object.values(vehicles)

      .filter((v) => !['ambulance', 'firetruck', 'police'].includes(v.type) && v.status !== 'blacklisted' && !v.gt_attack)

      .sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true })),

    [vehicles],

  );



  const run = async (fn: () => Promise<any>, ok: string) => {

    setBusy(true);

    try {

      await fn();

      setMessage({ ok: true, text: ok });

    } catch (e: any) {

      setMessage({ ok: false, text: e.message ?? String(e) });

    } finally {

      setBusy(false);

    }

  };



  const launch = () => run(async () => {

    const types = [...selected];

    if (!types.length) throw new Error('Select at least one attack');

    const launched: string[] = [];

    for (let i = 0; i < types.length; i++) {

      // a vehicle runs one attack at a time: the chosen vehicle gets the first, others go to random vehicles

      const res = await api.post('/attacks/launch', { attack_type: types[i], vehicle_id: i === 0 && target ? target : null });

      launched.push(`${res.vehicle_id}: ${res.label}`);

      if (i === 0) setTracked(res.vehicle_id);

    }

    setMessage({ ok: true, text: `Launched ${launched.join(', ')}` });

  }, 'Attack launched');



  const speedTo = (f: number) => run(() => api.post('/simulation/speed', { factor: f }), `Speed ×${f}`);



  return (

    <div className="p-6 h-full overflow-y-auto page-enter space-y-4">

      <h1 className="text-2xl font-bold text-white">Control Center</h1>



      <div className="grid grid-cols-3 gap-4">

        <Section title="Simulation controls">

          <div className="flex flex-wrap gap-2 mb-4">

            {!isRunning || paused ? (

              <button className="btn-primary flex items-center gap-1" disabled={busy}

                onClick={() => run(() => api.post(isRunning ? '/simulation/resume' : '/simulation/start'), 'Running')}>

                <Play size={16} /> {isRunning ? 'Resume' : 'Start'}

              </button>

            ) : (

              <button className="btn-secondary flex items-center gap-1" disabled={busy} onClick={() => run(() => api.post('/simulation/pause'), 'Paused')}>

                <Pause size={16} /> Pause

              </button>

            )}

            <button className="btn-secondary flex items-center gap-1" disabled={busy} onClick={() => run(() => api.post('/simulation/stop'), 'Stopped')}>

              <Square size={16} /> Stop

            </button>

            <button className="btn-secondary flex items-center gap-1" disabled={busy || speed <= 1} onClick={() => speedTo(Math.max(1, speed / 2))}>

              <Rewind size={16} /> Speed −

            </button>

            <button className="btn-secondary flex items-center gap-1" disabled={busy || speed >= 8} onClick={() => speedTo(Math.min(8, speed * 2))}>

              <FastForward size={16} /> Speed +

            </button>

            <button className="btn-danger flex items-center gap-1" disabled={busy}

              onClick={() => run(async () => { await api.post('/simulation/restart', { scenario_id: scenario?.id }); useStore.getState().resetFeeds(); setTracked(null); setComparison(null); }, 'Restarted')}>

              <RotateCcw size={16} /> Restart

            </button>

          </div>

          <KV label="State" value={!isRunning ? 'stopped' : paused ? 'paused' : 'running'} />

          <KV label="Simulation time" value={fmtTime(simTime)} mono />

          <KV label="Speed" value={`×${speed}`} />

          <KV label="Vehicles" value={Object.keys(vehicles).length} />

          <KV label="Traffic density" value={stats ? `${(stats.vehicles.active / 0.36).toFixed(0)} veh/km² (600 m × 600 m grid)` : '—'} />

          <KV label="Current scenario" value={scenario?.name ?? '—'} />

          <KV label="Attack status" value={activeAttacks.length ? <span className="text-rose-400">{activeAttacks.length} active</span> : 'none'} />

        </Section>



        <Section title="Scenario">

          <select className="input w-full mb-2" value={chosenScenario} onChange={(e) => setChosenScenario(e.target.value)}>

            {scenarios.map((s, i) => <option key={s.id} value={s.id}>Scenario {i + 1} → {s.name}</option>)}

          </select>

          {scenarios.filter((s) => s.id === chosenScenario).map((s) => (

            <div key={s.id} className="text-sm text-gray-400 mb-3">

              <p className="mb-1">{s.description}</p>

              <p className="text-xs">Departure every {s.density_period}s · scheduled attacks: {s.attacks.length ? s.attacks.join(', ') : 'none'}</p>

            </div>

          ))}

          <button className="btn-primary w-full" disabled={busy || !chosenScenario}

            onClick={() => run(async () => { await api.post('/scenario/load', { scenario_id: chosenScenario }); useStore.getState().resetFeeds(); setTracked(null); setComparison(null); }, 'Scenario loaded')}>

            Load scenario (restarts simulation)

          </button>

        </Section>



        <Section title="Active attacks (ground truth)">

          {activeAttacks.length === 0 ? <Empty>No attacks running.</Empty> : (

            <div className="space-y-2">

              {activeAttacks.map((a) => {

                const v = vehicles[a.vehicle_id];

                return (

                  <div key={a.vehicle_id} className="flex items-center justify-between rounded bg-white/[0.03] px-2 py-1.5 text-sm">

                    <button className="text-left" onClick={() => setTracked(a.vehicle_id)}>

                      <div className="font-mono">{TYPE_ICONS[v?.type ?? 'car']} {a.vehicle_id} <span className="text-rose-300">{a.label}</span></div>

                      <div className="text-[11px] text-gray-500">since {fmtTime(a.started_at)} · {a.messages_sent} malicious msgs {v && <>· trust {(v.trust_score * 100).toFixed(1)}</>}</div>

                    </button>

                    <div className="flex items-center gap-2">

                      {v && <StatusBadge status={v.status} />}

                      <button title="stop attack" className="text-gray-400 hover:text-rose-400"

                        onClick={() => run(() => api.post('/attacks/stop', { vehicle_id: a.vehicle_id }), 'Attack stopped')}>

                        <XCircle size={16} />

                      </button>

                    </div>

                  </div>

                );

              })}

              <button className="btn-secondary w-full text-xs mt-2" onClick={() => run(() => api.post('/attacks/stop', {}), 'All attacks stopped')}>Stop all</button>

            </div>

          )}

        </Section>

      </div>



      <Section title="Attack scenarios">

        <div className="grid grid-cols-4 gap-2 mb-4">

          {attackTypes.map((a) => (

            <label key={a.id} title={a.description}

              className={`flex items-start gap-2 rounded-md px-3 py-2 cursor-pointer border text-sm ${selected.has(a.id) ? 'border-rose-500/60 bg-rose-500/10' : 'border-white/10 hover:bg-white/[0.03]'}`}>

              <input type="checkbox" className="mt-1" checked={selected.has(a.id)} onChange={(e) => {

                const next = new Set(selected);

                if (e.target.checked) next.add(a.id); else next.delete(a.id);

                setSelected(next);

              }} />

              <span>

                <span className="font-medium text-gray-100">{a.label}</span>

                <span className="block text-[11px] text-gray-500">{a.description}</span>

              </span>

            </label>

          ))}

        </div>

        <div className="flex items-center gap-3">

          <span className="text-sm text-gray-400">Vehicle:</span>

          <select className="input" value={target} onChange={(e) => setTarget(e.target.value)}>

            <option value="">random eligible vehicle</option>

            {eligible.map((v) => <option key={v.id} value={v.id}>{TYPE_ICONS[v.type]} {v.id} ({v.type}, trust {(v.trust_score * 100).toFixed(0)})</option>)}

          </select>

          <button className="btn-danger flex items-center gap-2 px-6" disabled={busy || !selected.size} onClick={launch}>

            <Crosshair size={16} /> LAUNCH ATTACK

          </button>

          {message && <span className={`text-sm ${message.ok ? 'text-emerald-400' : 'text-rose-400'}`}>{message.text}</span>}

        </div>

        <p className="text-xs text-gray-500 mt-2">

          With several attacks selected, the chosen vehicle runs the first one and the others go to random vehicles (one attack per vehicle).

        </p>

      </Section>



      {comparison ? (

        <div>

          <BeforeAfter report={comparison} />

          <div className="mt-2 flex gap-2">

            <button className="btn-secondary text-sm" onClick={() => navigate(`/vehicle/${comparison.vehicle_id}`)}>Open {comparison.vehicle_id} details</button>

            {comparison.evidence_ids?.[0] && (

              <button className="btn-secondary text-sm" onClick={() => navigate(`/blockchain?evidence=${comparison.evidence_ids[0]}`)}>

                View evidence {comparison.evidence_ids[0]}

              </button>

            )}

          </div>

        </div>

      ) : (

        <Section title="Before / after attack comparison"><Empty>Launch an attack (or click an active attack) to follow it here.</Empty></Section>

      )}

    </div>

  );

};
