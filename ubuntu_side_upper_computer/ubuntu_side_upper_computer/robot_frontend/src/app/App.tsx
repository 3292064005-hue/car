import { Navigate, Route, Routes } from 'react-router-dom';
import { MainLayout } from '@/layouts/MainLayout';
import BridgeInspectorPage from '@/pages/BridgeInspectorPage';
import DashboardPage from '@/pages/DashboardPage';
import PerceptionPage from '@/pages/PerceptionPage';
import PatrolPage from '@/pages/PatrolPage';
import ReplayPage from '@/pages/ReplayPage';
import SafetyPage from '@/pages/SafetyPage';
import TeleopPage from '@/pages/TeleopPage';
import ReportsPage from '@/pages/ReportsPage';

export default function App() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/teleop" element={<TeleopPage />} />
        <Route path="/patrol" element={<PatrolPage />} />
        <Route path="/perception" element={<PerceptionPage />} />
        <Route path="/safety" element={<SafetyPage />} />
        <Route path="/replay" element={<ReplayPage />} />
        <Route path="/inspector" element={<BridgeInspectorPage />} />
        <Route path="/reports" element={<ReportsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
