import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/layout/Layout';
import AuthGuard from './components/features/AuthGuard';
import LoadingState from './components/common/LoadingState';

const LoginPage = lazy(() => import('./pages/LoginPage'));
const OverviewPage = lazy(() => import('./pages/OverviewPage'));
const JobsPage = lazy(() => import('./pages/JobsPage'));
const PipelinesPage = lazy(() => import('./pages/PipelinesPage'));
const AgentsPage = lazy(() => import('./pages/AgentsPage'));
const SkillsPage = lazy(() => import('./pages/SkillsPage'));
const ConfigPage = lazy(() => import('./pages/ConfigPage'));
const NodesPage = lazy(() => import('./pages/NodesPage'));
const MetricsPage = lazy(() => import('./pages/MetricsPage'));
const SystemPage = lazy(() => import('./pages/SystemPage'));
const LogsPage = lazy(() => import('./pages/LogsPage'));
const DebugPage = lazy(() => import('./pages/DebugPage'));
const DocsPage = lazy(() => import('./pages/DocsPage'));
const ChatPage = lazy(() => import('./pages/ChatPage'));
const SessionsPage = lazy(() => import('./pages/SessionsPage'));
const ActivityPage = lazy(() => import('./pages/ActivityPage'));
const CalendarPage = lazy(() => import('./pages/CalendarPage'));
const ChannelsPage = lazy(() => import('./pages/ChannelsPage'));

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<LoadingState message="Loading..." />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<AuthGuard><Layout /></AuthGuard>}>
            <Route index element={<OverviewPage />} />
            <Route path="jobs" element={<JobsPage />} />
            <Route path="pipelines" element={<PipelinesPage />} />
            <Route path="agents" element={<AgentsPage />} />
            <Route path="skills" element={<SkillsPage />} />
            <Route path="config" element={<ConfigPage />} />
            <Route path="nodes" element={<NodesPage />} />
            <Route path="metrics" element={<MetricsPage />} />
            <Route path="system" element={<SystemPage />} />
            <Route path="logs" element={<LogsPage />} />
            <Route path="debug" element={<DebugPage />} />
            <Route path="docs" element={<DocsPage />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="sessions" element={<SessionsPage />} />
            <Route path="settings" element={<Navigate to="/config" replace />} />
            <Route path="activity" element={<ActivityPage />} />
            <Route path="calendar" element={<CalendarPage />} />
            <Route path="channels" element={<ChannelsPage />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
