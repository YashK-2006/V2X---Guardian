import { useEffect, useRef, useState } from 'react';

import { useStore } from '../stores/useStore';

import { api } from '../api';



async function seedFeeds() {

  try {

    const [alerts, blocks] = await Promise.all([api.get('/alerts?limit=200'), api.get('/blockchain/blocks?limit=50')]);

    useStore.getState().seedFeeds(alerts, blocks.map((b: any) => ({

      index: b.index, hash: b.hash, prev_hash: b.prev_hash, validator: b.validator, time: b.timestamp,

      tx_count: b.tx_count, tx_types: {},

    })));

  } catch {

    /* backend not ready yet */

  }

}



export type WebSocketStatus = 'CONNECTING' | 'CONNECTED' | 'DISCONNECTED';



function wsUrl(path: string) {

  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';

  return `${proto}://${window.location.host}${path}`;

}



/** Single telemetry connection (opened once in App). Goes through the Vite /ws proxy. */

export function useWebSocket(path = '/ws/telemetry') {

  const [status, setStatus] = useState<WebSocketStatus>('CONNECTING');

  const attemptRef = useRef(0);



  useEffect(() => {

    let ws: WebSocket | null = null;

    let timer: number | undefined;

    let disposed = false;



    const connect = () => {

      if (disposed) return;

      setStatus('CONNECTING');

      ws = new WebSocket(wsUrl(path));



      ws.onopen = () => {

        attemptRef.current = 0;

        setStatus('CONNECTED');

        useStore.getState().setConnected(true);

        seedFeeds();

      };



      ws.onmessage = (event) => {

        try {

          const msg = JSON.parse(event.data);

          const store = useStore.getState();

          switch (msg.type) {

            case 'telemetry':

              store.applyTelemetry(msg.data);

              break;

            case 'alert':

              store.pushAlert(msg.data);

              break;

            case 'block':

              store.pushBlock(msg.data);

              break;

            case 'trust_change':

              store.pushTrustChange(msg.data);

              break;

          }

        } catch (error) {

          console.error('Failed to parse WebSocket message', error);

        }

      };



      ws.onclose = () => {

        useStore.getState().setConnected(false);

        if (disposed) return;

        setStatus('DISCONNECTED');

        attemptRef.current += 1;

        const timeout = Math.min(1000 * 2 ** attemptRef.current, 10000);

        timer = window.setTimeout(connect, timeout);

      };



      ws.onerror = () => ws?.close();

    };



    connect();

    return () => {

      disposed = true;

      if (timer) clearTimeout(timer);

      ws?.close();

    };

  }, [path]);



  return status;

}
