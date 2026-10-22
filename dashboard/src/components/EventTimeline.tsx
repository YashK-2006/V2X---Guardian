import React from 'react';

import { useStore, type Alert } from '../stores/useStore';

import { fmtTime } from '../api';



const SEVERITY: Record<Alert['severity'], { color: string; icon: string }> = {

  critical: { color: '#f43f5e', icon: '🚨' },

  warning: { color: '#f59e0b', icon: '⚠' },

  info: { color: '#06b6d4', icon: 'ℹ' },

};



/** Live security alert feed (fed by `alert` websocket events). */

export const EventTimeline: React.FC<{ limit?: number }> = ({ limit = 60 }) => {

  const alerts = useStore((s) => s.alerts);

  const blocks = useStore((s) => s.blocks);

  const select = useStore((s) => s.setSelectedVehicle);



  return (

    <div className="glass-card p-4 h-full flex flex-col">

      <div className="flex items-center justify-between mb-3">

        <h3 className="text-sm font-semibold text-gray-200 uppercase tracking-wider">Live Alerts</h3>

        <span className="text-[11px] text-gray-500">{alerts.length} alerts · {blocks.length ? `block #${blocks[0].index}` : 'no blocks yet'}</span>

      </div>

      <div className="flex-1 overflow-y-auto space-y-2 pr-1">

        {alerts.length === 0 && (

          <div className="text-center text-sm text-gray-500 py-10">

            No alerts yet. Launch an attack from the <b>Control Center</b> or load an attack scenario.

          </div>

        )}

        {alerts.slice(0, limit).map((a) => {

          const s = SEVERITY[a.severity];

          return (

            <button

              key={a.id}

              onClick={() => select(a.vehicle_id)}

              className="w-full text-left rounded-md px-3 py-2 bg-white/[0.02] hover:bg-white/[0.05] border-l-2"

              style={{ borderColor: s.color }}

            >

              <div className="flex justify-between text-xs">

                <span className="font-semibold" style={{ color: s.color }}>{s.icon} {a.title}</span>

                <span className="font-mono text-gray-500">{fmtTime(a.time)}</span>

              </div>

              <div className="text-xs text-gray-300 mt-0.5">{a.message}</div>

              {a.details?.trust_after !== undefined && a.details?.trust_before !== undefined && (

                <div className="text-[11px] text-gray-500 mt-0.5 font-mono">

                  trust {(a.details.trust_before * 100).toFixed(1)} → {(a.details.trust_after * 100).toFixed(1)}

                  {a.details.tx_id ? ` · tx ${a.details.tx_id}` : ''}

                </div>

              )}

            </button>

          );

        })}

      </div>

    </div>

  );

};
