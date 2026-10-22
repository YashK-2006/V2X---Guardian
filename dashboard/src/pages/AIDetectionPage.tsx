import React, { useEffect, useState } from 'react';

import { Brain, Crosshair, Filter, Activity, Zap, ShieldAlert } from 'lucide-react';

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

import { StatsCard } from '../components/StatsCard';

import { Section, Empty } from '../components/ui';

import { ATTACK_LABELS } from '../stores/useStore';

import { api, pct } from '../api';



const label = (k: string) => ATTACK_LABELS[k] ?? k;



const Matrix: React.FC<{ labels: string[]; matrix: number[][] }> = ({ labels, matrix }) => {

  const max = Math.max(1, ...matrix.flat());

  return (

    <div className="overflow-x-auto">

      <table className="text-[11px] border-collapse">

        <thead>

          <tr>

            <th className="p-1 text-gray-500 text-right">true \ pred</th>

            {labels.map((l) => <th key={l} className="p-1 text-gray-400 font-normal [writing-mode:vertical-rl] rotate-180 h-28 text-left">{label(l)}</th>)}

          </tr>

        </thead>

        <tbody>

          {labels.map((row, i) => (

            <tr key={row}>

              <td className="p-1 text-gray-400 text-right whitespace-nowrap">{label(row)}</td>

              {matrix[i].map((v, j) => {

                const a = v / max;

                const diag = i === j;

                return (

                  <td key={j} className="w-9 h-7 text-center font-mono"

                    style={{ background: v ? (diag ? `rgba(16,185,129,${0.15 + a * 0.7})` : `rgba(244,63,94,${0.2 + a * 0.7})`) : 'rgba(255,255,255,0.02)', color: v ? '#fff' : '#374151' }}>

                    {v || ''}

                  </td>

                );

              })}

            </tr>

          ))}

        </tbody>

      </table>

    </div>

  );

};



export const AIDetectionPage: React.FC = () => {

  const [data, setData] = useState<any>(null);

  useEffect(() => {

    const load = () => api.get('/ai/metrics').then(setData).catch(() => {});

    load();

    const t = setInterval(load, 3000);

    return () => clearInterval(t);

  }, []);



  const offline = data?.offline;

  const live = data?.live;

  const best = offline?.models?.find((m: any) => m.model === offline.selected_model);

  const sec = live?.security;



  // live confusion matrix -> square matrix

  const liveLabels: string[] = live ? Array.from(new Set([...Object.keys(live.confusion_matrix), ...Object.values(live.confusion_matrix).flatMap((r: any) => Object.keys(r))])).sort((a, b) => (a === 'normal' ? -1 : b === 'normal' ? 1 : a.localeCompare(b))) : [];

  const liveMatrix = liveLabels.map((t) => liveLabels.map((p) => live.confusion_matrix[t]?.[p] ?? 0));



  const importances = Object.entries(offline?.feature_importances ?? live?.feature_importances ?? {})

    .sort((a: any, b: any) => b[1] - a[1]).slice(0, 12).map(([name, value]) => ({ name, value: +(value as number).toFixed(4) }));



  const perAttack = Object.entries(live?.per_attack ?? {}).map(([k, v]: any) => ({

    attack: label(k), total: v.total ?? 0, detected: v.detected ?? 0, typed: v.correct_type ?? 0,

    rate: v.total ? v.detected / v.total : 0,

  }));



  return (

    <div className="p-6 h-full flex flex-col gap-4 page-enter overflow-y-auto">

      <div className="flex justify-between items-center">

        <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2"><Brain className="text-indigo-500" /> AI Misbehaviour Detection</h1>

        <span className="bg-emerald-500/20 text-emerald-400 px-3 py-1 rounded border border-emerald-500/30 text-sm font-medium">

          Live model: {live?.detector.model ?? '—'} + rule detectors

        </span>

      </div>



      <h2 className="text-sm uppercase tracking-wider text-gray-400">Offline evaluation (held-out test set)</h2>

      {!best ? (

        <Section title="No trained model"><Empty>Run <code className="text-indigo-300">python -m ai.train_detector</code> to train and evaluate the models. Detection currently uses rules only.</Empty></Section>

      ) : (

        <div className="grid grid-cols-6 gap-4">

          <StatsCard title="Accuracy" value={pct(best.accuracy)} icon={<Crosshair size={20} />} color="emerald" />

          <StatsCard title="Precision" value={pct(best.binary.precision)} icon={<Filter size={20} />} color="cyan" />

          <StatsCard title="Recall" value={pct(best.binary.recall)} icon={<Activity size={20} />} color="indigo" />

          <StatsCard title="F1 Score" value={pct(best.binary.f1)} icon={<Zap size={20} />} color="amber" />

          <StatsCard title="False Positive" value={pct(best.binary.false_positive_rate, 2)} icon={<ShieldAlert size={20} />} color="rose" />

          <StatsCard title="Macro F1 (attack type)" value={pct(best.macro_f1)} icon={<Brain size={20} />} color="indigo" />

        </div>

      )}



      <h2 className="text-sm uppercase tracking-wider text-gray-400">Live detection (ground truth from the attack injector)</h2>

      <div className="grid grid-cols-6 gap-4">

        <StatsCard title="Detection rate" value={pct(sec?.detection_rate)} icon={<Activity size={20} />} color="emerald" />

        <StatsCard title="Precision" value={pct(sec?.precision)} icon={<Filter size={20} />} color="cyan" />

        <StatsCard title="False positive rate" value={pct(sec?.false_positive_rate, 3)} icon={<ShieldAlert size={20} />} color="rose" />

        <StatsCard title="Accuracy" value={pct(sec?.accuracy, 2)} icon={<Crosshair size={20} />} color="indigo" />

        <StatsCard title="Messages analysed" value={(live?.detector.inferences ?? 0).toLocaleString()} icon={<Brain size={20} />} color="indigo" />

        <StatsCard title="Inference" value={`${(live?.detector.avg_inference_ms ?? 0).toFixed(3)} ms`} icon={<Zap size={20} />} color="amber" />

      </div>



      <div className="grid grid-cols-2 gap-4">

        <Section title="Live confusion matrix (per message)">

          {liveLabels.length ? <Matrix labels={liveLabels} matrix={liveMatrix} /> : <Empty>No messages yet.</Empty>}

        </Section>

        <Section title={`Offline confusion matrix (${best?.model ?? '—'})`}>

          {best ? <Matrix labels={best.confusion_matrix.labels} matrix={best.confusion_matrix.matrix} /> : <Empty>—</Empty>}

        </Section>

      </div>



      <div className="grid grid-cols-2 gap-4">

        <Section title="Attack-wise detection (live)">

          {perAttack.length === 0 ? <Empty>No attacks observed yet.</Empty> : (

            <table className="w-full text-sm">

              <thead className="text-[11px] uppercase text-gray-500 border-b border-white/10">

                <tr><th className="text-left py-1">Attack</th><th className="text-right">Malicious msgs</th><th className="text-right">Detected</th><th className="text-right">Rate</th><th className="text-right">Correct type</th></tr>

              </thead>

              <tbody>

                {perAttack.map((r) => (

                  <tr key={r.attack} className="border-b border-white/5">

                    <td className="py-1">{r.attack}</td><td className="text-right">{r.total}</td><td className="text-right">{r.detected}</td>

                    <td className={`text-right ${r.rate > 0.95 ? 'text-emerald-400' : r.rate > 0.8 ? 'text-amber-400' : 'text-rose-400'}`}>{pct(r.rate)}</td>

                    <td className="text-right">{r.total ? pct(r.typed / r.total) : '—'}</td>

                  </tr>

                ))}

              </tbody>

            </table>

          )}

        </Section>

        <Section title="Attack-wise F1 (offline)">

          {best ? (

            <div className="h-72">

              <ResponsiveContainer width="100%" height="100%">

                <BarChart layout="vertical" data={Object.entries(best.per_class).map(([k, v]: any) => ({ name: label(k), f1: +v['f1-score'].toFixed(3) }))}>

                  <XAxis type="number" domain={[0, 1]} tick={{ fontSize: 11, fill: '#6b7280' }} />

                  <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 11, fill: '#9ca3af' }} />

                  <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151' }} />

                  <Bar dataKey="f1" fill="#10b981" radius={[0, 4, 4, 0]} />

                </BarChart>

              </ResponsiveContainer>

            </div>

          ) : <Empty>—</Empty>}

        </Section>

      </div>



      <div className="grid grid-cols-2 gap-4">

        <Section title="Feature importance">

          {importances.length ? (

            <div className="h-72">

              <ResponsiveContainer width="100%" height="100%">

                <BarChart layout="vertical" data={importances}>

                  <XAxis type="number" tick={{ fontSize: 11, fill: '#6b7280' }} />

                  <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 11, fill: '#9ca3af' }} />

                  <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151' }} />

                  <Bar dataKey="value" fill="#6366f1" radius={[0, 4, 4, 0]} />

                </BarChart>

              </ResponsiveContainer>

            </div>

          ) : <Empty>—</Empty>}

        </Section>

        <Section title="Model comparison (offline)">

          {offline?.models ? (

            <table className="w-full text-sm">

              <thead className="text-[11px] uppercase text-gray-500 border-b border-white/10">

                <tr><th className="text-left py-1">Model</th><th className="text-right">Accuracy</th><th className="text-right">Macro F1</th><th className="text-right">Binary F1</th><th className="text-right">FPR</th><th className="text-right">ms / msg</th><th className="text-right">Train s</th></tr>

              </thead>

              <tbody>

                {offline.models.map((m: any) => (

                  <tr key={m.model} className={`border-b border-white/5 ${m.model === offline.selected_model ? 'text-emerald-300' : ''}`}>

                    <td className="py-1">{m.model}{m.model === offline.selected_model ? ' ✓' : ''}</td>

                    <td className="text-right">{pct(m.accuracy, 2)}</td>

                    <td className="text-right">{pct(m.macro_f1, 2)}</td>

                    <td className="text-right">{pct(m.binary.f1, 2)}</td>

                    <td className="text-right">{pct(m.binary.false_positive_rate, 2)}</td>

                    <td className="text-right">{m.inference_ms_single.toFixed(3)}</td>

                    <td className="text-right">{m.training_time_s.toFixed(1)}</td>

                  </tr>

                ))}

              </tbody>

            </table>

          ) : <Empty>—</Empty>}

          {offline && (

            <p className="text-xs text-gray-500 mt-3">

              Dataset: {offline.dataset.samples.toLocaleString()} labelled messages from {offline.dataset.runs} SUMO runs · trained {offline.trained_at}

            </p>

          )}

        </Section>

      </div>

    </div>

  );

};
