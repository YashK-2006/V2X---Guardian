import React from 'react';

import { Routes, Route, useLocation } from 'react-router-dom';

import { Sidebar } from './components/Sidebar';

import { AlertToasts } from './components/AlertToasts';

import { useWebSocket } from './hooks/useWebSocket';

import { OverviewPage } from './pages/OverviewPage';

import { ControlCenterPage } from './pages/ControlCenterPage';

import { VehiclePage } from './pages/VehiclePage';

import { CommGraphPage } from './pages/CommGraphPage';

import { AIDetectionPage } from './pages/AIDetectionPage';

import { BlockchainPage } from './pages/BlockchainPage';

import { TrustPage } from './pages/TrustPage';

import { PerformancePage } from './pages/PerformancePage';

import { ReplayPage } from './pages/ReplayPage';

import { ExperimentsPage } from './pages/ExperimentsPage';



export const App: React.FC = () => {

  const status = useWebSocket('/ws/telemetry');

  const location = useLocation();

  return (

    <div className="flex h-screen overflow-hidden bg-[#0a0e1a] text-gray-100">

      <Sidebar status={status} />

      <main className="flex-1 overflow-hidden relative">

        <div key={location.pathname} className="route-stage h-full">

        <Routes>

          <Route path="/" element={<OverviewPage />} />

          <Route path="/map" element={<OverviewPage />} />

          <Route path="/visualizer" element={<OverviewPage />} />

          <Route path="/control" element={<ControlCenterPage />} />

          <Route path="/experiments" element={<ExperimentsPage />} />

          <Route path="/performance" element={<PerformancePage />} />

          <Route path="/replay" element={<ReplayPage />} />

          <Route path="/vehicle/:id" element={<VehiclePage />} />

          <Route path="/graph" element={<CommGraphPage />} />

          <Route path="/ai" element={<AIDetectionPage />} />

          <Route path="/blockchain" element={<BlockchainPage />} />

          <Route path="/trust" element={<TrustPage />} />

        </Routes>

        </div>

      </main>

      <AlertToasts />

    </div>

  );

};
