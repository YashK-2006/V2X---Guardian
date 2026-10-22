import React, { useEffect, useState } from 'react';

import { useSearchParams, useNavigate } from 'react-router-dom';

import { Blocks, Database, Server, ShieldCheck, ShieldX, Timer, Gauge, Search } from 'lucide-react';

import { StatsCard } from '../components/StatsCard';

import { Section, Empty, KV } from '../components/ui';

import { api, fmtTime, shortHash, pct } from '../api';

import { useStore, ATTACK_LABELS } from '../stores/useStore';



const TX_COLORS: Record<string, string> = {

  REGISTER_VEHICLE: 'text-gray-400', MISBEHAVIOR_REPORT: 'text-rose-300', TRUST_UPDATE: 'text-amber-300',

  EVIDENCE_RECORD: 'text-purple-300', BLACKLIST: 'text-red-400', REHABILITATE: 'text-emerald-300',

  REPUTATION_UPDATE: 'text-cyan-300', VALIDATION_RECORD: 'text-gray-400',

};



export const BlockchainPage: React.FC = () => {

  const [params, setParams] = useSearchParams();

  const navigate = useNavigate();

  const liveBlocks = useStore((s) => s.blocks);

  const privacy = useStore((s) => s.privacyMode);

  const [status, setStatus] = useState<any>(null);

  const [blocks, setBlocks] = useState<any[]>([]);

  const [block, setBlock] = useState<any>(null);

  const [txs, setTxs] = useState<any[]>([]);

  const [txType, setTxType] = useState('');

  const [evidence, setEvidence] = useState<any[]>([]);

  const [search, setSearch] = useState(params.get('evidence') ?? '');

  const [found, setFound] = useState<any>(null);

  const [validation, setValidation] = useState<any>(null);



  useEffect(() => {

    const load = () => {

      api.get('/blockchain/status').then(setStatus).catch(() => {});

      api.get('/blockchain/blocks?limit=15').then(setBlocks).catch(() => {});

      api.get(`/blockchain/transactions?limit=40${txType ? `&tx_type=${txType}` : ''}`).then(setTxs).catch(() => {});

      api.get(`/evidence?limit=30${privacy ? '&privacy=true' : ''}`).then(setEvidence).catch(() => {});

    };

    load();

    const t = setInterval(load, 3000);

    return () => clearInterval(t);

  }, [txType, liveBlocks.length, privacy]);



  const lookup = async (q: string, tamper = false) => {

    setFound(null);

    q = q.trim();

    if (!q) return;

    try {

      if (q.startsWith('ATT-')) setFound({ kind: 'evidence', ...(await api.get(`/evidence/${q}?tamper=${tamper}&privacy=${privacy}`)) });

      else if (q.startsWith('0x')) setFound({ kind: 'tx', tx: await api.get(`/blockchain/transactions/${q}`) });

      else if (/^\d+$/.test(q)) setBlock(await api.get(`/blockchain/blocks/${q}`));

      else setFound({ kind: 'error', text: 'Enter an evidence id (ATT-…), transaction id (0x…) or block number' });

    } catch (e: any) {

      setFound({ kind: 'error', text: e.message });

    }

  };



  useEffect(() => {

    const ev = params.get('evidence');

    if (ev) lookup(ev);

  // eslint-disable-next-line react-hooks/exhaustive-deps

  }, []);



  return (

    <div className="p-6 h-full flex flex-col gap-4 page-enter overflow-y-auto">

      <div className="flex justify-between items-center">

        <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2"><Blocks className="text-cyan-500" /> Permissioned Blockchain</h1>

        <div className="flex gap-2 items-center">

          <span className="text-sm bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 px-3 py-1 rounded">{status?.consensus ?? '—'}</span>

          <button className="btn-secondary text-sm" onClick={() => api.get('/blockchain/validate').then(setValidation)}>Validate chain</button>

          {validation && (

            <span className={`text-sm flex items-center gap-1 ${validation.chain_valid && !validation.invalid_signatures.length ? 'text-emerald-400' : 'text-rose-400'}`}>

              {validation.chain_valid ? <ShieldCheck size={16} /> : <ShieldX size={16} />}

              {validation.blocks} blocks · hashes {validation.chain_valid ? 'valid' : 'INVALID'} · {validation.invalid_signatures.length} bad signatures

            </span>

          )}

        </div>

      </div>



      <div className="grid grid-cols-6 gap-4">

        <StatsCard title="Blocks" value={status?.blocks ?? 0} icon={<Blocks size={20} />} color="indigo" />

        <StatsCard title="Transactions" value={status?.transactions ?? 0} icon={<Database size={20} />} color="cyan" />

        <StatsCard title="Validators (RSUs)" value={status?.validators ?? 0} icon={<Server size={20} />} color="emerald" />

        <StatsCard title="Tx latency" value={status ? `${status.avg_tx_latency_s.toFixed(2)} s` : '—'} icon={<Timer size={20} />} color="amber" />

        <StatsCard title="TPS" value={status ? status.tps.toFixed(2) : '—'} icon={<Gauge size={20} />} color="indigo" />

        <StatsCard title="Storage · CRL" value={status ? `${(status.storage_bytes / 1024).toFixed(1)} KB · ${status.crl_size}` : '—'} icon={<Database size={20} />} color="cyan" />

      </div>



      <Section title="Explorer">

        <div className="flex gap-2 mb-3">

          <input className="input flex-1" placeholder="Evidence id (ATT-1001), transaction id (0x…) or block number" value={search}

            onChange={(e) => setSearch(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && lookup(search)} />

          <button className="btn-primary flex items-center gap-1" onClick={() => lookup(search)}><Search size={16} /> Search</button>

        </div>

        {found?.kind === 'error' && <div className="text-rose-400 text-sm">{found.text}</div>}

        {found?.kind === 'tx' && (

          <div className="grid grid-cols-2 gap-x-6 text-sm">

            <KV label="TX" value={found.tx.tx_id} mono />

            <KV label="Type" value={found.tx.tx_type} />

            <KV label="Block" value={found.tx.confirmed ? `#${found.tx.block}` : 'pending'} />

            <KV label="Reporting RSU" value={found.tx.reporting_rsu} />

            <KV label="Vehicle hash" value={found.tx.vehicle_hash} mono />

            <KV label="Signature" value={shortHash(found.tx.signature, 24)} mono />

            <pre className="col-span-2 mt-2 text-xs bg-black/40 rounded p-2 overflow-x-auto">{JSON.stringify(found.tx.data, null, 2)}</pre>

          </div>

        )}

        {found?.kind === 'evidence' && (

          <div className="text-sm">

            <div className={`mb-2 flex items-center gap-2 ${found.verification.valid ? 'text-emerald-400' : 'text-rose-400'}`}>

              {found.verification.valid ? <ShieldCheck size={18} /> : <ShieldX size={18} />}

              {found.verification.valid ? 'Evidence hash matches the on-chain record' : 'Evidence hash does NOT match the on-chain record (tampered)'}

              {found.verification.confirmed ? ` · block #${found.verification.block}` : ' · tx pending'}

              <button className="btn-secondary text-xs ml-auto" onClick={() => lookup(found.record.attack_id, !found.tampered)}>

                {found.tampered ? 'Show original record' : 'Simulate tampering'}

              </button>

            </div>

            <div className="grid grid-cols-3 gap-x-6">

              <KV label="Attack ID" value={found.record.attack_id} mono />

              <KV label="Vehicle" value={<button className="hover:underline" onClick={() => navigate(`/vehicle/${found.record.vehicle_id}`)}>{found.record.vehicle_id}</button>} />

              <KV label="Attack type" value={found.record.label} />

              <KV label="Time" value={fmtTime(found.record.time)} />

              <KV label="Location" value={found.record.location?.join(', ')} mono />

              <KV label="AI probability" value={pct(found.record.ai_probability)} />

              <KV label="Expected" value={found.record.expected} />

              <KV label="Observed" value={found.record.observed} />

              <KV label="Trust before → after" value={`${(found.record.trust_before * 100).toFixed(1)} → ${(found.record.trust_after * 100).toFixed(1)}`} />

              <KV label="Stored hash (on-chain)" value={shortHash(found.verification.stored_hash, 20)} mono />

              <KV label="Blockchain TX" value={found.verification.tx_id ?? '—'} mono />

              <KV label="Consensus" value={`${found.record.flagging}/${found.record.reporters} neighbours`} />

            </div>

          </div>

        )}

        {block && (

          <div className="mt-3 text-sm">

            <div className="flex justify-between mb-1">

              <b>Block #{block.index}</b>

              <span className={block.hash_valid && block.signature_valid ? 'text-emerald-400' : 'text-rose-400'}>

                hash {block.hash_valid ? '✓' : '✗'} · validator signature {block.signature_valid ? '✓' : '✗'}

              </span>

            </div>

            <KV label="Hash" value={block.hash} mono />

            <KV label="Previous" value={block.prev_hash} mono />

            <KV label="Merkle root" value={block.merkle_root} mono />

            <KV label="Validator" value={block.validator} />

            <div className="mt-2 space-y-1">

              {block.transactions.map((tx: any) => (

                <div key={tx.tx_id} className="flex gap-3 text-xs font-mono">

                  <span className="text-cyan-400">{tx.tx_id}</span><span className={TX_COLORS[tx.tx_type]}>{tx.tx_type}</span>

                  <span className="text-gray-500">{tx.vehicle_hash.slice(0, 12)}…</span><span>{tx.event_type ?? ''}</span>

                </div>

              ))}

            </div>

            <button className="btn-secondary text-xs mt-2" onClick={() => setBlock(null)}>close</button>

          </div>

        )}

      </Section>



      <div className="grid grid-cols-3 gap-4">

        <Section title="Latest blocks">

          <div className="space-y-2">

            {blocks.length === 0 && <Empty>No blocks sealed yet.</Empty>}

            {blocks.map((b) => (

              <button key={b.index} className="w-full text-left block-item rounded-md px-3 py-2 bg-white/[0.02] hover:bg-white/[0.05]"

                onClick={() => lookup(String(b.index))}>

                <div className="flex justify-between text-sm"><b>#{b.index}</b><span className="text-xs text-gray-500">{fmtTime(b.timestamp)}</span></div>

                <div className="text-[11px] font-mono text-gray-500">{shortHash(b.hash, 20)}</div>

                <div className="text-[11px] text-gray-400">{b.tx_count} tx · sealed by {b.validator}</div>

              </button>

            ))}

          </div>

        </Section>



        <Section title="Transactions" right={

          <select className="input text-xs py-1" value={txType} onChange={(e) => setTxType(e.target.value)}>

            <option value="">all types</option>

            {Object.keys(TX_COLORS).map((t) => <option key={t} value={t}>{t}</option>)}

          </select>

        }>

          <div className="space-y-1 max-h-[520px] overflow-y-auto">

            {txs.length === 0 && <Empty>No transactions.</Empty>}

            {txs.map((tx) => (

              <button key={tx.tx_id} className="transaction-row w-full text-left text-xs rounded px-2 py-1 hover:bg-white/[0.04]" onClick={() => { setSearch(tx.tx_id); lookup(tx.tx_id); }}>

                <div className="flex justify-between"><span className="font-mono text-cyan-400">{tx.tx_id}</span><span className="text-gray-500">{tx.confirmed ? `#${tx.block}` : 'pending'}</span></div>

                <div className="flex justify-between">

                  <span className={TX_COLORS[tx.tx_type]}>{tx.tx_type}</span>

                  <span className="text-gray-400">{tx.event_type ? ATTACK_LABELS[tx.event_type] ?? tx.event_type : ''} {tx.trust_after !== null && tx.trust_after !== undefined ? `trust ${(tx.trust_after * 100).toFixed(0)}` : ''}</span>

                </div>

              </button>

            ))}

          </div>

        </Section>



        <Section title="Evidence records">

          <div className="space-y-1 max-h-[520px] overflow-y-auto">

            {evidence.length === 0 && <Empty>No evidence yet.</Empty>}

            {evidence.map((e) => (

              <button key={e.attack_id} className="evidence-row w-full text-left text-xs rounded px-2 py-1.5 hover:bg-white/[0.04]" onClick={() => { setSearch(e.attack_id); setParams({ evidence: e.attack_id }); lookup(e.attack_id); }}>

                <div className="flex justify-between"><span className="font-mono text-purple-300">{e.attack_id}</span><span className="text-gray-500">{fmtTime(e.time)}</span></div>

                <div className="flex justify-between"><span className="text-rose-300">{e.label}</span><span className="font-mono">{e.vehicle_id}</span></div>

                <div className="text-gray-500">p={pct(e.ai_probability)} · trust {(e.trust_before * 100).toFixed(0)}→{(e.trust_after * 100).toFixed(0)} · block {e.block ?? 'pending'}</div>

              </button>

            ))}

          </div>

        </Section>

      </div>

    </div>

  );

};
