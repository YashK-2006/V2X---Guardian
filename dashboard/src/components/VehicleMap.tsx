import React, { useEffect, useRef, useState } from 'react';

import { useNavigate } from 'react-router-dom';

import { useStore, STATUS_COLORS, TYPE_ICONS, type Pedestrian, type VehicleStatus } from '../stores/useStore';

import { api, fmtTime } from '../api';



interface Geometry {

  bounds: { min_x: number; min_y: number; max_x: number; max_y: number };

  edges: { id: string; shape: [number, number][]; lanes?: number }[];

  junctions: { id: string; coord: [number, number]; type?: string }[];

}



const PAD = 40;



export interface MapVehicle {

  id: string;

  type: string;

  claimed_type: string;

  x: number;

  y: number;

  heading: number;

  status: VehicleStatus;

}



export interface ReplayFrame {

  vehicles: MapVehicle[];

  pedestrians: Pedestrian[];

  time: number;

}



/** Live map (default) or replay of recorded frames when `replay` is given. */

export const VehicleMap: React.FC<{ replay?: ReplayFrame | null }> = ({ replay }) => {

  const replayRef = useRef<ReplayFrame | null | undefined>(replay);

  useEffect(() => { replayRef.current = replay; }, [replay]);

  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [geometry, setGeometry] = useState<Geometry | null>(null);

  const [zoom, setZoom] = useState(1);

  const [pan, setPan] = useState({ x: 0, y: 0 });

  const drag = useRef({ active: false, moved: false, x: 0, y: 0 });

  const navigate = useNavigate();

  const vehicleCount = useStore((s) => Object.keys(s.vehicles).length);

  const simTime = useStore((s) => s.simTime);

  const scenario = useStore((s) => s.scenario);

  const paused = useStore((s) => s.paused);

  const pedCount = useStore((s) => s.pedestrians.length);



  useEffect(() => {

    let cancelled = false;

    const load = () =>

      api.get<Geometry>('/network/geometry').then((g) => {

        if (!cancelled && g.edges?.length) setGeometry(g);

        else if (!cancelled) setTimeout(load, 2000);

      }).catch(() => !cancelled && setTimeout(load, 2000));

    load();

    return () => { cancelled = true; };

  }, [scenario?.id]);



  // world -> canvas transform based on the network bounds

  const transform = (canvas: HTMLCanvasElement) => {

    const b = geometry?.bounds ?? { min_x: 0, min_y: 0, max_x: 600, max_y: 600 };

    const w = canvas.width, h = canvas.height;

    const scale = Math.min((w - PAD * 2) / (b.max_x - b.min_x || 1), (h - PAD * 2) / (b.max_y - b.min_y || 1)) * zoom;

    const cx = w / 2 + pan.x, cy = h / 2 + pan.y;

    const mx = (b.min_x + b.max_x) / 2, my = (b.min_y + b.max_y) / 2;

    return {

      scale,

      toCanvas: (x: number, y: number) => [cx + (x - mx) * scale, cy - (y - my) * scale] as [number, number],

    };

  };



  useEffect(() => {

    let frame = 0;

    const draw = () => {

      const canvas = canvasRef.current;

      if (!canvas) return;

      const ctx = canvas.getContext('2d');

      if (!ctx) return;

      const rect = canvas.parentElement!.getBoundingClientRect();

      if (canvas.width !== rect.width || canvas.height !== rect.height) {

        canvas.width = rect.width;

        canvas.height = rect.height;

      }

      const { scale, toCanvas } = transform(canvas);

      const state = useStore.getState();

      ctx.fillStyle = '#0a0e1a';

      ctx.fillRect(0, 0, canvas.width, canvas.height);



      // roads

      if (geometry) {

        ctx.lineCap = 'round';

        for (const edge of geometry.edges) {

          ctx.beginPath();

          edge.shape.forEach(([x, y], i) => {

            const [px, py] = toCanvas(x, y);

            if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);

          });

          ctx.strokeStyle = '#1f2937';

          ctx.lineWidth = Math.max(4, 3.2 * (edge.lanes ?? 2) * scale);

          ctx.stroke();

        }

        ctx.setLineDash([6, 8]);

        ctx.strokeStyle = 'rgba(255,255,255,0.12)';

        ctx.lineWidth = 1;

        for (const edge of geometry.edges) {

          ctx.beginPath();

          edge.shape.forEach(([x, y], i) => {

            const [px, py] = toCanvas(x, y);

            if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);

          });

          ctx.stroke();

        }

        ctx.setLineDash([]);

        for (const j of geometry.junctions) {

          if (j.type !== 'traffic_light') continue;

          const [px, py] = toCanvas(j.coord[0], j.coord[1]);

          ctx.fillStyle = 'rgba(250,204,21,0.35)';

          ctx.beginPath();

          ctx.arc(px, py, 3, 0, Math.PI * 2);

          ctx.fill();

        }

      }



      // RSUs with coverage

      const t = Date.now() / 1000;

      for (const rsu of state.rsus) {

        const [px, py] = toCanvas(rsu.x, rsu.y);

        const selected = state.selectedRsuId === rsu.id;

        ctx.strokeStyle = selected ? 'rgba(6,182,212,0.4)' : 'rgba(6,182,212,0.08)';

        ctx.lineWidth = 1;

        ctx.beginPath();

        ctx.arc(px, py, 500 * scale, 0, Math.PI * 2);

        ctx.stroke();

        const pulse = 10 + ((t * 12) % 14);

        ctx.strokeStyle = `rgba(6,182,212,${0.6 - (pulse - 10) / 28})`;

        ctx.beginPath();

        ctx.arc(px, py, pulse, 0, Math.PI * 2);

        ctx.stroke();

        ctx.fillStyle = selected ? '#22d3ee' : '#0891b2';

        ctx.fillRect(px - 6, py - 6, 12, 12);

        ctx.fillStyle = '#9ca3af';

        ctx.font = '10px monospace';

        ctx.fillText(rsu.id, px + 9, py - 8);

      }



      // pedestrians (V2P)

      const src = replayRef.current;

      const vehicles: MapVehicle[] = src ? src.vehicles : Object.values(state.vehicles);

      const pedestrians = src ? src.pedestrians : state.pedestrians;

      ctx.textAlign = 'center';

      ctx.textBaseline = 'middle';

      for (const p of pedestrians) {

        const [px, py] = toCanvas(p.x, p.y);

        ctx.fillStyle = 'rgba(168,85,247,0.25)';

        ctx.beginPath();

        ctx.arc(px, py, 6, 0, Math.PI * 2);

        ctx.fill();

        ctx.font = '10px serif';

        ctx.fillText('🚶', px, py);

      }



      // vehicles

      const iconSize = Math.max(12, Math.min(22, 8 * scale + 8));

      for (const v of vehicles) {

        const [px, py] = toCanvas(v.x, v.y);

        const color = STATUS_COLORS[v.status] ?? '#10b981';

        const selected = state.selectedVehicleId === v.id;

        if (v.status !== 'trusted' || selected) {

          ctx.fillStyle = color + (selected ? '66' : '33');

          ctx.beginPath();

          ctx.arc(px, py, iconSize * 0.9, 0, Math.PI * 2);

          ctx.fill();

        }

        ctx.strokeStyle = color;

        ctx.lineWidth = selected ? 3 : 2;

        ctx.beginPath();

        ctx.arc(px, py, iconSize * 0.65, 0, Math.PI * 2);

        ctx.stroke();

        // heading tick (SUMO: 0 = north, clockwise)

        const rad = (v.heading * Math.PI) / 180;

        ctx.beginPath();

        ctx.moveTo(px + Math.sin(rad) * iconSize * 0.65, py - Math.cos(rad) * iconSize * 0.65);

        ctx.lineTo(px + Math.sin(rad) * iconSize * 1.05, py - Math.cos(rad) * iconSize * 1.05);

        ctx.stroke();

        ctx.font = `${iconSize * 0.8}px serif`;

        ctx.fillText(TYPE_ICONS[v.claimed_type !== v.type ? v.claimed_type : v.type] ?? '🚗', px, py + 1);

        if (v.claimed_type !== v.type || v.status === 'malicious' || v.status === 'blacklisted' || selected) {

          ctx.font = 'bold 10px monospace';

          ctx.fillStyle = color;

          ctx.fillText(v.id, px, py - iconSize - 2);

        }

      }

      ctx.textAlign = 'start';

      ctx.textBaseline = 'alphabetic';

      frame = requestAnimationFrame(draw);

    };

    frame = requestAnimationFrame(draw);

    return () => cancelAnimationFrame(frame);

    // eslint-disable-next-line react-hooks/exhaustive-deps

  }, [geometry, zoom, pan]);



  const hitTest = (e: React.MouseEvent<HTMLCanvasElement>) => {

    const canvas = canvasRef.current!;

    const rect = canvas.getBoundingClientRect();

    const mx = e.clientX - rect.left, my = e.clientY - rect.top;

    const { toCanvas } = transform(canvas);

    const state = useStore.getState();

    let best: { kind: 'rsu' | 'vehicle'; id: string; d: number } | null = null;

    for (const r of state.rsus) {

      const [px, py] = toCanvas(r.x, r.y);

      const d = Math.hypot(px - mx, py - my);

      if (d < 14 && (!best || d < best.d)) best = { kind: 'rsu', id: r.id, d };

    }

    for (const v of Object.values(state.vehicles)) {

      const [px, py] = toCanvas(v.x, v.y);

      const d = Math.hypot(px - mx, py - my);

      if (d < 16 && (!best || d < best.d)) best = { kind: 'vehicle', id: v.id, d };

    }

    return best;

  };



  const onClick = (e: React.MouseEvent<HTMLCanvasElement>) => {

    if (drag.current.moved || replayRef.current) return;

    const hit = hitTest(e);

    const store = useStore.getState();

    if (!hit) store.setSelectedVehicle(null);

    else if (hit.kind === 'rsu') store.setSelectedRsu(hit.id);

    else store.setSelectedVehicle(hit.id);

  };



  const onDoubleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {

    if (replayRef.current) return;

    const hit = hitTest(e);

    if (hit?.kind === 'vehicle') navigate(`/vehicle/${hit.id}`);

  };



  return (

    <div className="relative w-full h-full overflow-hidden rounded-xl border border-[rgba(99,102,241,0.15)] bg-[#0a0e1a]">

      <canvas

        ref={canvasRef}

        className="block w-full h-full cursor-crosshair"

        onClick={onClick}

        onDoubleClick={onDoubleClick}

        onWheel={(e) => setZoom((z) => Math.max(0.4, Math.min(8, z * (e.deltaY > 0 ? 0.9 : 1.1))))}

        onMouseDown={(e) => { drag.current = { active: true, moved: false, x: e.clientX, y: e.clientY }; }}

        onMouseMove={(e) => {

          if (!drag.current.active) return;

          const dx = e.clientX - drag.current.x, dy = e.clientY - drag.current.y;

          if (Math.abs(dx) + Math.abs(dy) > 2) drag.current.moved = true;

          drag.current.x = e.clientX;

          drag.current.y = e.clientY;

          setPan((p) => ({ x: p.x + dx, y: p.y + dy }));

        }}

        onMouseUp={() => { drag.current.active = false; }}

        onMouseLeave={() => { drag.current.active = false; }}

      />

      <div className="absolute top-3 left-3 glass-card px-3 py-2 text-xs font-mono text-gray-300 flex gap-4 pointer-events-none">

        {replay ? (

          <>

            <span>⏮ replay {fmtTime(replay.time)}</span>

            <span>🚗 {replay.vehicles.length}</span>

            <span>🚶 {replay.pedestrians.length}</span>

          </>

        ) : (

          <>

            <span>⏱ {fmtTime(simTime)}{paused ? ' (paused)' : ''}</span>

            <span>🚗 {vehicleCount}</span>

            <span>🚶 {pedCount}</span>

            <span className="text-gray-500">{scenario?.name ?? '—'}</span>

          </>

        )}

      </div>

      <div className="absolute bottom-3 left-3 glass-card px-3 py-2 text-[11px] text-gray-400 flex gap-3 pointer-events-none">

        {(['trusted', 'suspicious', 'malicious', 'blacklisted'] as const).map((s) => (

          <span key={s} className="flex items-center gap-1">

            <span className="w-2.5 h-2.5 rounded-full" style={{ background: STATUS_COLORS[s] }} /> {s}

          </span>

        ))}

        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 bg-cyan-600" /> RSU</span>

        <span>🚶 pedestrian (V2P)</span>

      </div>

      <div className="absolute bottom-3 right-3 flex gap-1">

        <button className="btn-secondary px-2 py-1 text-xs" onClick={() => setZoom((z) => Math.min(8, z * 1.25))}>+</button>

        <button className="btn-secondary px-2 py-1 text-xs" onClick={() => setZoom((z) => Math.max(0.4, z / 1.25))}>−</button>

        <button className="btn-secondary px-2 py-1 text-xs" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}>reset</button>

      </div>

      {!replay && <div className="absolute top-3 right-3 text-[11px] text-gray-500 pointer-events-none">click: select · double-click: details</div>}

      {!geometry && !replay && (

        <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-400 text-xs gap-3 pointer-events-none bg-[#0a0e1a]/85 backdrop-blur-sm z-10">

          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />

          <p className="font-mono text-gray-200">Waiting for simulation telemetry & road geometry...</p>

          <p className="text-gray-500 text-[11px]">Start the backend server (`uvicorn backend.api:app`) to view live vehicles.</p>

        </div>

      )}

    </div>

  );

};
