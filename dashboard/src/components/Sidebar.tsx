import React from 'react';

import { NavLink } from 'react-router-dom';

import { LayoutDashboard, Brain, Blocks, Shield, SlidersHorizontal, Network, Gauge, History, FlaskConical, EyeOff, Eye } from 'lucide-react';

import type { WebSocketStatus } from '../hooks/useWebSocket';

import { useStore } from '../stores/useStore';

import { fmtTime } from '../api';



export const Sidebar: React.FC<{ status: WebSocketStatus }> = ({ status }) => {

  const simTime = useStore((s) => s.simTime);

  const scenario = useStore((s) => s.scenario);

  const paused = useStore((s) => s.paused);

  const running = useStore((s) => s.isRunning);

  const alerts = useStore((s) => s.alerts.filter((a) => a.severity === 'critical').length);

  const privacy = useStore((s) => s.privacyMode);

  const setPrivacy = useStore((s) => s.setPrivacyMode);



  const links = [

    { to: '/', icon: <LayoutDashboard size={20} />, label: 'Live Map Visualizer' },

    { to: '/control', icon: <SlidersHorizontal size={20} />, label: 'Control Center' },

    { to: '/graph', icon: <Network size={20} />, label: 'Communication Graph' },

    { to: '/ai', icon: <Brain size={20} />, label: 'AI Detection' },

    { to: '/trust', icon: <Shield size={20} />, label: 'Trust' },

    { to: '/blockchain', icon: <Blocks size={20} />, label: 'Blockchain' },

    { to: '/performance', icon: <Gauge size={20} />, label: 'Performance' },

    { to: '/replay', icon: <History size={20} />, label: 'Replay' },

    { to: '/experiments', icon: <FlaskConical size={20} />, label: 'Experiments' },

  ];



  return (

    <div className="sidebar flex flex-col h-full bg-[#111827] border-r border-[rgba(99,102,241,0.15)] w-60 shrink-0">

      <div className="flex items-center gap-3 p-6 mb-2">

        <Shield className="text-indigo-500" size={28} />

        <div>

          <h1 className="text-xl font-bold text-gray-100 tracking-wider">V2X SOC</h1>

          <p className="text-[10px] text-gray-500">AI · Trust · Blockchain</p>

        </div>

      </div>



      <nav className="flex-1 px-3">

        {links.map((link) => (

          <NavLink

            key={link.to}

            to={link.to}

            end={link.to === '/'}

            className={({ isActive }) =>

              `sidebar-link flex items-center gap-3 px-4 py-3 my-1 rounded-md transition-colors text-sm font-medium ${

                isActive

                  ? 'sidebar-link--active bg-[rgba(99,102,241,0.15)] text-indigo-400 border-l-2 border-indigo-500'

                  : 'text-gray-400 hover:bg-[rgba(99,102,241,0.1)] hover:text-gray-200'

              }`

            }

          >

            {link.icon}

            {link.label}

            {link.to === '/' && alerts > 0 && (

              <span className="ml-auto text-[10px] bg-rose-500/20 text-rose-300 rounded-full px-1.5">{alerts}</span>

            )}

          </NavLink>

        ))}

      </nav>



      <div className="px-4 pb-3">

        <button

          onClick={() => setPrivacy(!privacy)}

          title="Privacy view: vehicle ids are replaced by pseudonyms and locations coarsened to 50 m in message and evidence tables"

          className={`w-full flex items-center gap-2 px-3 py-2 rounded-md text-xs border ${privacy ? 'border-purple-500/50 bg-purple-500/10 text-purple-300' : 'border-white/10 text-gray-400 hover:text-gray-200'}`}

        >

          {privacy ? <EyeOff size={14} /> : <Eye size={14} />} {privacy ? 'Privacy view (pseudonyms)' : 'Operator view (real ids)'}

        </button>

      </div>

      <div className="p-4 border-t border-[rgba(99,102,241,0.15)] space-y-1 text-xs font-mono text-gray-400">

        <div className="flex items-center gap-3">

          <div className={`live-indicator ${status === 'CONNECTED' ? '' : 'live-indicator--danger'}`} />

          <span>{status}</span>

        </div>

        <div>{running ? (paused ? '⏸ paused' : '▶ running') : '⏹ stopped'} · {fmtTime(simTime)}</div>

        <div className="truncate text-gray-500">{scenario?.name ?? ''}</div>

      </div>

    </div>

  );

};
