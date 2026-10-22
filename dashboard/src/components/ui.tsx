import React from 'react';

import { STATUS_COLORS, type VehicleStatus } from '../stores/useStore';



export const StatusBadge: React.FC<{ status: VehicleStatus | string }> = ({ status }) => {

  const color = STATUS_COLORS[status as VehicleStatus] ?? '#9ca3af';

  return (

    <span

      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold uppercase tracking-wide"

      style={{ color, background: color + '22', border: `1px solid ${color}55` }}

    >

      <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />

      {status}

    </span>

  );

};



const CLASS_STYLE: Record<string, { icon: string; color: string }> = {

  Normal: { icon: '✓', color: '#10b981' },

  valid: { icon: '✓', color: '#10b981' },

  Suspicious: { icon: '⚠', color: '#f59e0b' },

  suspicious: { icon: '⚠', color: '#f59e0b' },

  Malicious: { icon: '🚨', color: '#f43f5e' },

  malicious: { icon: '🚨', color: '#f43f5e' },

};



export const ClassBadge: React.FC<{ value: string }> = ({ value }) => {

  const s = CLASS_STYLE[value] ?? { icon: '•', color: '#9ca3af' };

  return (

    <span className="inline-flex items-center gap-1 text-xs font-semibold" style={{ color: s.color }}>

      <span>{s.icon}</span>

      {value === 'Normal' ? 'Valid' : value}

    </span>

  );

};



export const KV: React.FC<{ label: string; value: React.ReactNode; mono?: boolean }> = ({ label, value, mono }) => (

  <div className="flex justify-between items-center py-1.5 border-b border-white/5 text-sm gap-3">

    <span className="text-gray-400 shrink-0">{label}</span>

    <span className={`text-gray-100 text-right truncate ${mono ? 'font-mono text-xs' : ''}`}>{value}</span>

  </div>

);



export const Section: React.FC<{ title: string; right?: React.ReactNode; children: React.ReactNode; className?: string }> = ({

  title, right, children, className = '',

}) => (

  <div className={`glass-card p-4 ${className}`}>

    <div className="flex items-center justify-between mb-3">

      <h3 className="text-sm font-semibold text-gray-200 uppercase tracking-wider">{title}</h3>

      {right}

    </div>

    {children}

  </div>

);



export const Metric: React.FC<{ label: string; value: React.ReactNode; sub?: React.ReactNode; color?: string }> = ({

  label, value, sub, color = 'text-gray-100',

}) => (

  <div className="flex flex-col">

    <span className="text-[11px] uppercase tracking-wider text-gray-500">{label}</span>

    <span className={`text-lg font-bold ${color}`}>{value}</span>

    {sub && <span className="text-[11px] text-gray-500">{sub}</span>}

  </div>

);



export const Empty: React.FC<{ children: React.ReactNode }> = ({ children }) => (

  <div className="text-center text-sm text-gray-500 py-8">{children}</div>

);
