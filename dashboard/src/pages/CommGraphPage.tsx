import React, { useEffect, useMemo, useRef, useState } from 'react';

import { useNavigate } from 'react-router-dom';

import { Network, RefreshCw } from 'lucide-react';

import { api } from '../api';

import { STATUS_COLORS, TYPE_ICONS } from '../stores/useStore';

import { Section, KV, Empty } from '../components/ui';



interface GNode { id: string; type: string; trust: number; status: string; attacker: boolean }

interface GEdge { source: string; target: string; messages: number; valid: number; suspicious: number; malicious: number }

interface Pos { x: number; y: number; vx: number; vy: number }



const W = 900, H = 640;



/** Simple force-directed layout (repulsion + spring on edges + centering), warm-started between updates. */

function layout(nodes: GNode[], edges: GEdge[], prev: Map<string, Pos>): Map<string, Pos> {

  const pos = new Map<string, Pos>();

  nodes.forEach((n, i) => {

    const p = prev.get(n.id);

    pos.set(n.id, p ? { ...p } : { x: W / 2 + Math.cos(i) * 200 * Math.random(), y: H / 2 + Math.sin(i) * 200 * Math.random(), vx: 0, vy: 0 });

  });

  const arr = nodes.map((n) => pos.get(n.id)!);

  const links = edges.map((e) => [pos.get(e.source), pos.get(e.target), Math.log2(1 + e.messages)] as const).filter(([a, b]) => a && b);

  for (let it = 0; it < 120; it++) {

    const alpha = 1 - it / 120;

    for (let i = 0; i < arr.length; i++) {

      for (let j = i + 1; j < arr.length; j++) {

        const a = arr[i], b = arr[j];

        let dx = a.x - b.x, dy = a.y - b.y;

        let d2 = dx * dx + dy * dy;

        if (d2 < 1) { dx = Math.random(); dy = Math.random(); d2 = 1; }

        const f = (1800 / d2) * alpha;

        a.vx += dx * f; a.vy += dy * f; b.vx -= dx * f; b.vy -= dy * f;

      }

    }

    for (const [a, b, w] of links) {

      const dx = b!.x - a!.x, dy = b!.y - a!.y;

      const d = Math.sqrt(dx * dx + dy * dy) || 1;

      const f = ((d - 90) / d) * 0.004 * w * alpha;

      a!.vx += dx * f; a!.vy += dy * f; b!.vx -= dx * f; b!.vy -= dy * f;

    }

    for (const p of arr) {

      p.vx += (W / 2 - p.x) * 0.002; p.vy += (H / 2 - p.y) * 0.002;

      p.x = Math.max(20, Math.min(W - 20, p.x + p.vx)); p.y = Math.max(20, Math.min(H - 20, p.y + p.vy));

      p.vx *= 0.6; p.vy *= 0.6;

    }

  }

  return pos;

}



export const CommGraphPage: React.FC = () => {

  const navigate = useNavigate();

  const [graph, setGraph] = useState<{ nodes: GNode[]; edges: GEdge[] }>({ nodes: [], edges: [] });

  const [minMessages, setMinMessages] = useState(3);

  const [flaggedOnly, setFlaggedOnly] = useState(false);

  const [focus, setFocus] = useState<string | null>(null);

  const [edgeSel, setEdgeSel] = useState<GEdge | null>(null);

  const posRef = useRef(new Map<string, Pos>());

  const [pos, setPos] = useState(new Map<string, Pos>());



  useEffect(() => {

    const load = () => api.get(`/graph?min_messages=${minMessages}`).then((g) => {

      posRef.current = layout(g.nodes, g.edges.filter((e: GEdge) => e.messages >= minMessages * 3), posRef.current);

      setGraph(g);

      setPos(posRef.current);

    }).catch(() => {});

    load();

    const t = setInterval(load, 4000);

    return () => clearInterval(t);

  }, [minMessages]);



  const edges = useMemo(() => graph.edges.filter((e) => {

    if (focus && e.source !== focus && e.target !== focus) return false;

    if (flaggedOnly && !(e.suspicious + e.malicious)) return false;

    return true;

  }), [graph, focus, flaggedOnly]);



  const flaggedBy = useMemo(() => {

    const m = new Map<string, number>();

    for (const e of graph.edges) if (e.malicious + e.suspicious) m.set(e.source, (m.get(e.source) ?? 0) + 1);

    return m;

  }, [graph]);



  const pair = edgeSel ? graph.edges.find((e) => e.source === edgeSel.target && e.target === edgeSel.source) : null;



  return (

    <div className="p-6 h-full overflow-y-auto page-enter">

      <div className="flex items-center justify-between mb-4">

        <h1 className="text-2xl font-bold text-white flex items-center gap-2"><Network className="text-indigo-400" /> Communication Graph</h1>

        <div className="flex items-center gap-3 text-sm">

          <label className="flex items-center gap-1 text-gray-400">min msgs

            <input type="number" min={1} className="input w-16 py-1" value={minMessages} onChange={(e) => setMinMessages(Math.max(1, +e.target.value))} />

          </label>

          <label className="flex items-center gap-1 text-gray-400"><input type="checkbox" checked={flaggedOnly} onChange={(e) => setFlaggedOnly(e.target.checked)} /> flagged links only</label>

          {focus && <button className="btn-secondary text-xs" onClick={() => setFocus(null)}>clear focus ({focus})</button>}

          <button className="btn-secondary text-xs flex items-center gap-1" onClick={() => api.post('/graph/reset').then(() => { posRef.current.clear(); })}><RefreshCw size={12} /> reset counters</button>

        </div>

      </div>

      <div className="grid grid-cols-4 gap-4">

        <div className="col-span-3 glass-card p-1">

          {graph.nodes.length === 0 ? <Empty>No communication yet.</Empty> : (

            <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto">

              <defs>

                <marker id="arrow" viewBox="0 0 10 10" refX="16" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">

                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#f43f5e" />

                </marker>

              </defs>

              {edges.map((e) => {

                const a = pos.get(e.source), b = pos.get(e.target);

                if (!a || !b) return null;

                const bad = e.malicious + e.suspicious;

                const selected = edgeSel && edgeSel.source === e.source && edgeSel.target === e.target;

                return (

                  <line key={e.source + '>' + e.target} x1={a.x} y1={a.y} x2={b.x} y2={b.y}

                    stroke={selected ? '#fff' : e.malicious ? '#f43f5e' : e.suspicious ? '#f59e0b' : '#6366f1'}

                    strokeOpacity={selected ? 1 : bad ? 0.75 : focus ? 0.5 : 0.12}

                    strokeWidth={selected ? 3 : Math.min(4, 0.5 + Math.log2(1 + e.messages) / 3)}

                    markerEnd={bad ? 'url(#arrow)' : undefined}

                    className="cursor-pointer" onClick={() => setEdgeSel(e)} />

                );

              })}

              {graph.nodes.map((n) => {

                const p = pos.get(n.id);

                if (!p) return null;

                const color = n.status === 'forged' ? '#a855f7' : STATUS_COLORS[n.status as keyof typeof STATUS_COLORS] ?? '#10b981';

                const dim = focus && focus !== n.id && !edges.some((e) => e.source === n.id || e.target === n.id);

                return (

                  <g key={n.id} transform={`translate(${p.x},${p.y})`} opacity={dim ? 0.25 : 1} className="cursor-pointer"

                    onClick={() => setFocus(focus === n.id ? null : n.id)} onDoubleClick={() => n.status !== 'forged' && navigate(`/vehicle/${n.id}`)}>

                    <circle r={n.attacker || n.status !== 'trusted' ? 11 : 8} fill={color + '33'} stroke={color} strokeWidth={2}

                      strokeDasharray={n.status === 'forged' ? '3 2' : undefined} />

                    <text textAnchor="middle" dy="4" fontSize="9">{TYPE_ICONS[n.type] ?? '•'}</text>

                    {(n.status !== 'trusted' || focus === n.id) && <text textAnchor="middle" dy="-14" fontSize="10" fill={color} fontFamily="monospace">{n.id}</text>}

                  </g>

                );

              })}

            </svg>

          )}

        </div>

        <div className="space-y-4">

          <Section title="Link details">

            {!edgeSel ? <Empty>Click a link to see its message statistics.</Empty> : (

              <>

                <div className="font-mono text-sm mb-2">{edgeSel.source} → {edgeSel.target}</div>

                <KV label="Messages" value={edgeSel.messages} />

                <KV label="Valid" value={<span className="text-emerald-400">{edgeSel.valid}</span>} />

                <KV label="Suspicious" value={<span className="text-amber-400">{edgeSel.suspicious}</span>} />

                <KV label="Malicious" value={<span className="text-rose-400">{edgeSel.malicious}</span>} />

                {pair && <div className="text-xs text-gray-500 mt-2">reverse link {pair.source} → {pair.target}: {pair.messages} msgs ({pair.suspicious + pair.malicious} flagged)</div>}

              </>

            )}

          </Section>

          <Section title="Most-flagged senders">

            {[...flaggedBy.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10).map(([id, n]) => (

              <button key={id} className="w-full flex justify-between text-sm hover:bg-white/[0.03] px-1 rounded" onClick={() => setFocus(id)}>

                <span className="font-mono">{id}</span><span className="text-rose-300">{n} receivers flagged</span>

              </button>

            ))}

            {flaggedBy.size === 0 && <Empty>No flagged links.</Empty>}

            <p className="text-[11px] text-gray-500 mt-2">Purple dashed nodes are forged identities (e.g. Sybil ghosts) with no registered certificate.</p>

          </Section>

          <Section title="Legend">

            <div className="text-xs text-gray-400 space-y-1">

              <div>Click a node to focus its links · double-click to open the vehicle</div>

              <div><span className="text-indigo-400">—</span> valid traffic · <span className="text-amber-400">—</span> suspicious · <span className="text-rose-400">→</span> malicious</div>

            </div>

          </Section>

        </div>

      </div>

    </div>

  );

};
