import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { DashboardPage } from './pages/DashboardPage';
import { UploadPage } from './pages/UploadPage';
import { ProcessingStatusPage } from './pages/ProcessingStatusPage';
import { FinalAuditFilePage } from './pages/FinalAuditFilePage';
import { HistoryPage } from './pages/HistoryPage';
import { AuditorSuitePage } from './pages/AuditorSuitePage';
import { ReconciliationPage } from './pages/ReconciliationPage';
import { ExceptionsPage } from './pages/ExceptionsPage';
import { WorkpapersPage } from './pages/WorkpapersPage';
import { ClientsPage } from './pages/ClientsPage';
import { EngagementsPage } from './pages/EngagementsPage';
import { ReviewQueuePage } from './pages/ReviewQueuePage';
import { SettingsPage } from './pages/SettingsPage';
import { NotFoundPage } from './pages/NotFoundPage';

export function App() {
  return (
    <BrowserRouter>
      <div className="flex min-h-screen bg-slate-50 font-sans">
        <Sidebar />
        <div className="flex-1 min-w-0 pt-14 md:pt-0">
          <Routes>
            {/* The 12 Primary Statutory Auditor Navigation Sections */}
            <Route path="/" element={<DashboardPage />} />
            <Route path="/clients" element={<ClientsPage />} />
            <Route path="/engagements" element={<EngagementsPage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/processing" element={<ProcessingStatusPage />} />
            <Route path="/processing/:runId" element={<ProcessingStatusPage />} />
            <Route path="/reconciliation" element={<ReconciliationPage />} />
            <Route path="/auditor-suite" element={<AuditorSuitePage />} />
            <Route path="/exceptions" element={<ExceptionsPage />} />
            <Route path="/workpapers" element={<WorkpapersPage />} />
            <Route path="/review-queue" element={<ReviewQueuePage />} />
            <Route path="/final-audit-file" element={<FinalAuditFilePage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/settings" element={<SettingsPage />} />

            {/* Seamless Redirects for Legacy URLs */}
            <Route path="/reports" element={<Navigate to="/final-audit-file" replace />} />
            <Route path="/financial-statements" element={<Navigate to="/final-audit-file" replace />} />
            <Route path="/ratio-analysis" element={<Navigate to="/final-audit-file" replace />} />
            <Route path="/corporate-finance" element={<Navigate to="/auditor-suite" replace />} />
            <Route path="/analysis-results" element={<Navigate to="/auditor-suite" replace />} />
            <Route path="/chat-assistant" element={<Navigate to="/" replace />} />
            <Route path="/ai-insights" element={<Navigate to="/" replace />} />

            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}

export default App;
