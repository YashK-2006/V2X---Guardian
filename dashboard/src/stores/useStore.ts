import { create } from 'zustand';



export type VehicleStatus = 'trusted' | 'suspicious' | 'malicious' | 'blacklisted';



export interface Vehicle {

  id: string;

  hash: string;

  type: string;

  claimed_type: string;

  emergency_flag: boolean;

  x: number;

  y: number;

  speed: number;

  acceleration: number;

  heading: number; // degrees, SUMO convention (0 = north, clockwise)

  lane: string;

  road: string;

  trust_score: number;

  status: VehicleStatus;

  reputation: number;

  ai_score: number;

  message_count: number;

  messages_received: number;

  suspicious_count: number;

  misbehavior_count: number;

  detected_attacks: number;

  attack_types: Record<string, number>;

  blockchain_records: number;

  gt_attack: string | null;

  active: boolean;

}



export interface RSU {

  id: string;

  x: number;

  y: number;

  status: string;

  type: string;

  reputation: number;

  received: number;

  flagged: number;

  blocks_sealed: number;

}



export interface Alert {

  id: string;

  time: number;

  wall_time: number;

  severity: 'critical' | 'warning' | 'info';

  kind: string;

  vehicle_id: string;

  title: string;

  message: string;

  details: Record<string, any>;

}



export interface BlockEvent {

  index: number;

  hash: string;

  prev_hash: string;

  validator: string;

  time: number;

  tx_count: number;

  tx_types: Record<string, number>;

}



export interface TrustChange {

  vehicle_id: string;

  old_score: number;

  new_score: number;

  reason: string;

  timestamp: number;

  kind: string;

  attack_type?: string;

}



export interface ActiveAttack {

  vehicle_id: string;

  attack_type: string;

  label: string;

  started_at: number;

  params: Record<string, any>;

  messages_sent: number;

}



export interface Stats {

  vehicles: {

    total_registered: number; active: number; trusted: number; suspicious: number; malicious: number;

    blacklisted: number; emergency: number; by_type: Record<string, number>; avg_trust: number;

  };

  communication: {

    messages_sent: number; cam: number; denm: number; messages_received: number; messages_per_sec: number;

    v2v: number; v2i: number; v2n: number; v2p: number; vam: number; i2v_notifications: number; pedestrians: number;

    failed: number; pdr: number; avg_latency_ms: number;

    throughput_kbps: number; overhead_bytes: number;

  };

  security: {

    alerts: number; active_attacks: number; attacks_launched: number; evidence_records: number; blacklisted: number;

    flagged_suspicious: number; flagged_malicious: number; true_positives: number; false_positives: number;

    false_negatives: number; true_negatives: number; detection_rate: number; precision: number;

    false_positive_rate: number; accuracy: number;

    attack_distribution: Record<string, { total?: number; detected?: number; correct_type?: number }>;

  };

  blockchain: {

    blocks: number; transactions: number; pending: number; validators: number; consensus: string;

    avg_tx_latency_s: number; tps: number; avg_seal_ms: number; block_interval_s: number; storage_bytes: number;

    latest_hash: string; next_validator: string;

  };

  ai: { model: string; classes: string[]; inferences: number; avg_inference_ms: number; avg_batch_ms: number };

}



export interface Pedestrian {

  id: string;

  x: number;

  y: number;

  heading: number;

}



export interface Toast extends Alert {

  toastId: number;

}



interface SimulationState {

  connected: boolean;

  isRunning: boolean;

  paused: boolean;

  speed: number;

  simTime: number;

  mockMode: boolean;

  scenario: { id: string; name: string } | null;

  vehicles: Record<string, Vehicle>;

  pedestrians: Pedestrian[];

  rsus: RSU[];

  privacyMode: boolean;

  setPrivacyMode: (on: boolean) => void;

  stats: Stats | null;

  activeAttacks: ActiveAttack[];

  alerts: Alert[];

  toasts: Toast[];

  blocks: BlockEvent[];

  trustChanges: TrustChange[];

  selectedVehicleId: string | null;

  selectedRsuId: string | null;

  applyTelemetry: (data: any) => void;

  pushAlert: (alert: Alert) => void;

  dismissToast: (toastId: number) => void;

  pushBlock: (block: BlockEvent) => void;

  pushTrustChange: (change: TrustChange) => void;

  setConnected: (connected: boolean) => void;

  setSelectedVehicle: (id: string | null) => void;

  setSelectedRsu: (id: string | null) => void;

  resetFeeds: () => void;

  seedFeeds: (alerts: Alert[], blocks: BlockEvent[]) => void;

}



let toastSeq = 0;



export const useStore = create<SimulationState>((set) => ({

  connected: false,

  isRunning: false,

  paused: false,

  speed: 1,

  simTime: 0,

  mockMode: false,

  scenario: null,

  vehicles: {},

  pedestrians: [],

  rsus: [],

  privacyMode: (() => {

    try { return localStorage.getItem('privacyMode') === '1'; } catch { return false; }

  })(),

  setPrivacyMode: (on) => {

    try { localStorage.setItem('privacyMode', on ? '1' : '0'); } catch { /* ignore */ }

    set({ privacyMode: on });

  },

  stats: null,

  activeAttacks: [],

  alerts: [],

  toasts: [],

  blocks: [],

  trustChanges: [],

  selectedVehicleId: null,

  selectedRsuId: null,

  applyTelemetry: (d) => set((state) => {

    // Replace the vehicle set on every frame so departed vehicles disappear from the map.

    const vehicles: Record<string, Vehicle> = {};

    for (const v of d.vehicles as Vehicle[]) vehicles[v.id] = v;

    const restarted = state.scenario && d.sim_time < state.simTime - 1;

    return {

      vehicles,

      pedestrians: d.pedestrians ?? [],

      rsus: d.rsus ?? state.rsus,

      stats: d.stats ?? state.stats,

      isRunning: d.simulation_running,

      paused: d.paused,

      speed: d.speed,

      simTime: d.sim_time,

      mockMode: d.mock_mode,

      scenario: d.scenario,

      activeAttacks: d.active_attacks ?? [],

      ...(restarted ? { alerts: [], blocks: [], trustChanges: [], toasts: [] } : {}),

    };

  }),

  pushAlert: (alert) => set((state) => {

    const toasts = alert.severity === 'info' && alert.kind !== 'attack_launched'

      ? state.toasts

      : [{ ...alert, toastId: ++toastSeq }, ...state.toasts].slice(0, 4);

    return { alerts: [alert, ...state.alerts].slice(0, 300), toasts };

  }),

  dismissToast: (toastId) => set((state) => ({ toasts: state.toasts.filter((t) => t.toastId !== toastId) })),

  pushBlock: (block) => set((state) => ({ blocks: [block, ...state.blocks].slice(0, 50) })),

  pushTrustChange: (change) => set((state) => ({ trustChanges: [change, ...state.trustChanges].slice(0, 200) })),

  setConnected: (connected) => set({ connected }),

  setSelectedVehicle: (id) => set({ selectedVehicleId: id, selectedRsuId: null }),

  setSelectedRsu: (id) => set({ selectedRsuId: id, selectedVehicleId: null }),

  resetFeeds: () => set({ alerts: [], blocks: [], trustChanges: [], toasts: [] }),

  // initial state after (re)connecting: events that happened before the page was opened

  seedFeeds: (alerts, blocks) => set({ alerts, blocks }),

}));



export const STATUS_COLORS: Record<VehicleStatus, string> = {

  trusted: '#10b981',

  suspicious: '#f59e0b',

  malicious: '#f43f5e',

  blacklisted: '#dc2626',

};



export const TYPE_ICONS: Record<string, string> = {

  car: '🚗', suv: '🚙', taxi: '🚕', bus: '🚌', truck: '🚚', motorcycle: '🏍️',

  ambulance: '🚑', firetruck: '🚒', police: '🚓', unknown: '👻', pedestrian: '🚶', rsu: '📡',

};



export const ATTACK_LABELS: Record<string, string> = {

  emergency_spoofing: 'Emergency Vehicle Spoofing',

  false_position: 'False Position',

  gps_spoofing: 'GPS Spoofing',

  false_speed: 'False Speed',

  false_acceleration: 'False Acceleration',

  false_heading: 'False Heading',

  fake_accident: 'Fake Accident',

  message_flooding: 'Message Flooding',

  replay: 'Replay Attack',

  sybil: 'Sybil Attack',

  message_injection: 'Message Injection',

  revoked_identity: 'Revoked Identity',

  collusion: 'Collusion',

  normal: 'Normal',

};



export const trustPct = (t: number) => (t * 100).toFixed(1);
