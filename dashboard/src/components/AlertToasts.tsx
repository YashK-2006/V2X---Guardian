import React, { useEffect } from 'react';

import { useNavigate } from 'react-router-dom';

import { X } from 'lucide-react';

import { useStore, type Toast, ATTACK_LABELS } from '../stores/useStore';

import { StatusBadge } from './ui';

import { pct } from '../api';



const ToastCard: React.FC<{ t: Toast }> = ({ t }) => {

  const dismiss = useStore((s) => s.dismissToast);

  const navigate = useNavigate();

  useEffect(() => {

    const timer = setTimeout(() => dismiss(t.toastId), t.severity === 'critical' ? 9000 : 6000);

    return () => clearTimeout(timer);

  }, [t.toastId, t.severity, dismiss]);



  const d = t.details ?? {};

  const color = t.severity === 'critical' ? '#f43f5e' : t.severity === 'warning' ? '#f59e0b' : '#06b6d4';

  const isSpoof = t.kind === 'emergency_spoofing';



  return (

    <div

      className={`security-toast w-80 rounded-lg shadow-2xl p-3 text-sm cursor-pointer backdrop-blur bg-[#0b1220]/95 animate-[fadeIn_0.2s] ${t.severity === "critical" ? "security-toast--critical" : t.severity === "warning" ? "security-toast--warning" : "security-toast--info"}`}

      style={{ border: `1px solid ${color}88`, boxShadow: `0 0 24px ${color}33` }}

      onClick={() => navigate(`/vehicle/${t.vehicle_id}`)}

    >

      <div className="flex justify-between items-start">

        <div className="font-bold tracking-wide" style={{ color }}>

          {t.severity === 'critical' ? '🚨' : t.severity === 'warning' ? '⚠' : 'ℹ'} {t.title}

        </div>

        <button onClick={(e) => { e.stopPropagation(); dismiss(t.toastId); }} className="text-gray-500 hover:text-white">

          <X size={14} />

        </button>

      </div>

      {isSpoof ? (

        <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">

          <span className="text-gray-400">Vehicle</span><span className="font-mono text-gray-100">{t.vehicle_id}</span>

          <span className="text-gray-400">Actual</span><span className="text-gray-100">{d.actual_type}</span>

          <span className="text-gray-400">Claimed</span><span className="text-rose-300 font-semibold">{d.claimed_type}</span>

          <span className="text-gray-400">Probability</span><span className="text-gray-100">{pct(d.probability)}</span>

          <span className="text-gray-400">Trust</span><span className="text-gray-100">{(d.trust_after * 100).toFixed(1)}</span>

          <span className="text-gray-400">Status</span><span><StatusBadge status={d.status} /></span>

        </div>

      ) : (

        <div className="mt-1 text-xs text-gray-300">

          {t.message}

          {d.attack_type && d.probability !== undefined && (

            <div className="mt-1 text-gray-400">

              {ATTACK_LABELS[d.attack_type] ?? d.attack_type} · p={pct(d.probability)} · trust {(d.trust_after * 100).toFixed(1)}

            </div>

          )}

        </div>

      )}

      {d.tx_id && <div className="mt-1 text-[10px] font-mono text-gray-500">tx {d.tx_id}{d.attack_id ? ` · ${d.attack_id}` : ''}</div>}

    </div>

  );

};



export const AlertToasts: React.FC = () => {

  const toasts = useStore((s) => s.toasts);

  return (

    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 security-toast-stack">

      {toasts.map((t) => <ToastCard key={t.toastId} t={t} />)}

    </div>

  );

};
