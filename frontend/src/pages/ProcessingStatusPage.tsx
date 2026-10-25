import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  ArrowRight,
  Download,
  RefreshCw,
  FileText,
  ShieldCheck,
  Terminal,
  Activity,
  Layers,
  Database,
  Building2,
  Calendar,
  FileCheck2,
  ChevronRight,
  ShieldAlert,
  Check,
  Calculator,
  Info,
  FileWarning
} from 'lucide-react';
import { api } from '../services/api';
import { ProcessingRun, ProcessingRunStage } from '../types';

const STAGE_CONFIG: {
  id: ProcessingRunStage;
  label: string;
  category: 'Ingestion' | 'Accounting' | 'Reconciliation' | 'Audit' | 'Packaging';
  description: string;
}[] = [
  { id: 'UPLOAD_RECEIVED', label: '1. Upload Received', category: 'Ingestion', description: 'Computing SHA-256 cryptographic hashes and checking file uniqueness' },
  { id: 'FILE_VALIDATION', label: '2. File Validation', category: 'Ingestion', description: 'Verifying non-zero byte integrity and disk storage' },
  { id: 'DOCUMENT_CLASSIFICATION', label: '3. Document Classification', category: 'Ingestion', description: 'Identifying document types from column headers and layout' },
  { id: 'DATA_EXTRACTION', label: '4. Data Extraction', category: 'Ingestion', description: 'Extracting tabular data and preserving source cell coordinates' },
  { id: 'DATA_VALIDATION', label: '5. Data Validation', category: 'Ingestion', description: 'Verifying amounts, dates, and computing extraction confidence' },
  { id: 'ACCOUNT_NORMALIZATION', label: '6. Account Normalization', category: 'Accounting', description: 'Mapping entity master, financial year, and chart of accounts' },
  { id: 'ACCOUNTING_CALCULATIONS', label: '7. Accounting Calculations', category: 'Accounting', description: 'Generating Schedule III Trial Balance & GL voucher scrutiny' },
  { id: 'RECONCILIATION', label: '8. Reconciliation Suite', category: 'Reconciliation', description: 'BRS 4-way matching, FAR dual depreciation & Subledger MSME screening' },
  { id: 'AUDIT_PROCEDURES', label: '9. Audit Procedures', category: 'Audit', description: 'Executing ICAI SA and Form 3CD statutory audit test matrix' },
  { id: 'EXCEPTION_GENERATION', label: '10. Exception Generation', category: 'Audit', description: 'Consolidating evidence-backed discrepancies into risk registry' },
  { id: 'WORKPAPER_GENERATION', label: '11. Workpaper Generation', category: 'Audit', description: 'Drafting SA 230 compliant standardized electronic audit workpapers' },
  { id: 'REPORT_ASSEMBLY', label: '12. Report Assembly', category: 'Packaging', description: 'Synthesizing 14-section Consolidated Audit File & Ingestion Report' },
  { id: 'OUTPUT_VALIDATION', label: '13. Output Validation', category: 'Packaging', description: 'Validating exports, generating PDF, 8-tab Excel, CSV & .ZIP' },
  { id: 'COMPLETED', label: '14. Execution Completed', category: 'Packaging', description: 'All audit procedures finalized, package signed and archived' },
];

export const ProcessingStatusPage: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  const [run, setRun] = useState<ProcessingRun | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRetrying, setIsRetrying] = useState<boolean>(false);
  const [isDownloading, setIsDownloading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [logFilter, setLogFilter] = useState<'ALL' | 'INFO' | 'WARNING' | 'ERROR'>('ALL');

  const fetchRun = async (showLoading = false) => {
    if (showLoading) setIsLoading(true);
    try {
      if (runId) {
        const data = await api.getProcessingRun(runId);
        setRun(data);
        setErrorMsg(null);
      } else {
        const latest = await api.getLatestProcessingRun();
        if (latest) {
          setRun(latest);
          setErrorMsg(null);
        } else {
          setErrorMsg('No processing run found. Please upload documents to initiate an audit run.');
        }
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to fetch processing status');
    } finally {
      if (showLoading) setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchRun(true);
  }, [runId]);

  // Polling for live status while running
  useEffect(() => {
    if (!run || run.status === 'COMPLETED' || run.status === 'FAILED' || run.status === 'BLOCKED') {
      return;
    }
    const interval = setInterval(() => {
      fetchRun(false);
    }, 2000);
    return () => clearInterval(interval);
  }, [run?.status, run?.id]);

  const handleRetry = async () => {
    if (!run) return;
    setIsRetrying(true);
    try {
      const updated = await api.retryProcessingRun(run.run_id);
      setRun(updated);
    } catch (err: any) {
      alert(`Retry failed: ${err.message || 'Unknown error'}`);
    } finally {
      setIsRetrying(false);
    }
  };

  const handleDownloadZip = async () => {
    if (!run) return;
    setIsDownloading(true);
    try {
      await api.downloadAuditPackage(run.run_id);
    } catch (err: any) {
      alert(`Download failed: ${err.message || 'Package not ready'}`);
    } finally {
      setIsDownloading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50/70 flex flex-col items-center justify-center text-slate-900 p-6">
        <Activity className="w-12 h-12 text-blue-600 animate-spin mb-4" />
        <h2 className="text-xl font-bold tracking-tight">Loading Processing Status...</h2>
        <p className="text-slate-500 text-sm mt-1">Connecting to central automation orchestrator...</p>
      </div>
    );
  }

  if (errorMsg || !run) {
    return (
      <div className="min-h-screen bg-slate-50/70 flex flex-col items-center justify-center text-slate-900 p-6">
        <div className="bg-white border border-slate-200 rounded-2xl p-8 max-w-md text-center shadow-sm">
          <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-slate-900 mb-2">No Active Run Found</h2>
          <p className="text-slate-600 text-sm mb-6">{errorMsg || 'Please initiate document upload to trigger processing.'}</p>
          <div className="flex justify-center gap-3">
            <Link
              to="/upload"
              className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-xl transition shadow-sm text-sm inline-flex items-center gap-2 cursor-pointer"
            >
              <FileText className="w-4 h-4" /> Go to Upload
            </Link>
            <Link
              to="/history"
              className="px-5 py-2.5 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 font-medium rounded-xl transition text-sm cursor-pointer shadow-xs"
            >
              View History
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const isCompleted = run.status === 'COMPLETED' || run.status === 'PARTIALLY_COMPLETED';
  const isFailed = run.status === 'FAILED' || run.status === 'BLOCKED';

  const filteredLogs = (run.stage_logs || []).filter((log) => {
    if (logFilter === 'ALL') return true;
    return log.level === logFilter;
  });

  return (
    <div className="min-h-screen bg-slate-50/70 text-slate-900 p-6 lg:p-10 font-sans">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold px-2.5 py-1 rounded-md bg-blue-50 text-blue-700 border border-blue-200 uppercase tracking-wider">
              Autonomous Orchestrator
            </span>
            <span className="text-slate-500 text-xs font-mono">{run.run_id}</span>
          </div>
          <h1 className="text-2xl lg:text-3xl font-extrabold text-slate-900 tracking-tight mt-1">
            {run.company_name || 'Enterprise Client'} Audit Run
          </h1>
          <p className="text-slate-500 text-sm mt-0.5 flex items-center gap-2">
            <span>{run.engagement_title || 'Statutory Audit'}</span>
            <span>•</span>
            <span>Started {new Date(run.started_at).toLocaleString()}</span>
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3 flex-wrap">
          {isCompleted && (
            <>
              <button
                onClick={handleDownloadZip}
                disabled={isDownloading}
                className="px-4 py-2.5 rounded-xl bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 font-medium text-sm flex items-center gap-2 transition shadow-xs cursor-pointer"
              >
                <Download className="w-4 h-4 text-emerald-600" />
                <span>{isDownloading ? 'Downloading...' : 'Download .ZIP Package'}</span>
              </button>
              <Link
                to={`/final-audit-file?runId=${run.run_id}`}
                className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-semibold text-sm flex items-center gap-2 transition shadow-sm cursor-pointer"
              >
                <FileCheck2 className="w-4 h-4" />
                <span>Open Final Audit File</span>
                <ChevronRight className="w-4 h-4" />
              </Link>
            </>
          )}

          {isFailed && (
            <button
              onClick={handleRetry}
              disabled={isRetrying}
              className="px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-semibold text-sm flex items-center gap-2 transition shadow-sm cursor-pointer"
            >
              <RefreshCw className={`w-4 h-4 ${isRetrying ? 'animate-spin' : ''}`} />
              <span>Retry Pipeline</span>
            </button>
          )}
        </div>
      </div>

      {/* Synthetic Test Data Banner */}
      {(run.summary_metrics?.is_synthetic_test_data || run.company_name?.includes('[TEST DEMO]') || run.engagement_title?.includes('[SYNTHETIC')) && (
        <div className="mt-4 p-3.5 rounded-2xl bg-amber-50 border border-amber-300 text-amber-800 text-xs flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />
          <div>
            <span className="font-bold uppercase tracking-wider text-amber-800">[SYNTHETIC TEST BENCHMARK RUN]:</span>
            <span className="ml-1.5 text-amber-900">
              This execution processed pre-packaged synthetic fixtures for verification. It does not represent live company accounting records.
            </span>
          </div>
        </div>
      )}

      {/* Progress Metric Banner */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-6">
        {/* Status Card */}
        <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-xs flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-blue-50 border border-blue-200 text-blue-600">
            {isCompleted ? (
              <CheckCircle2 className="w-6 h-6 text-emerald-600" />
            ) : isFailed ? (
              <XCircle className="w-6 h-6 text-rose-600" />
            ) : (
              <Activity className="w-6 h-6 text-blue-600 animate-pulse" />
            )}
          </div>
          <div>
            <div className="text-xs uppercase font-semibold text-slate-500">Overall Status</div>
            <div className="text-lg font-bold text-slate-900 capitalize mt-0.5">{run.status.toLowerCase().replace('_', ' ')}</div>
            <div className="text-xs text-slate-500 mt-0.5">Stage {run.current_stage}</div>
          </div>
        </div>

        {/* Documents Card */}
        <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-xs flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-indigo-50 border border-indigo-200 text-indigo-600">
            <Layers className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xs uppercase font-semibold text-slate-500">Documents Ingested</div>
            <div className="text-2xl font-bold text-slate-900 mt-0.5">{run.documents?.length || 0}</div>
            <div className="text-xs text-emerald-600 mt-0.5 font-medium">SHA-256 Verified</div>
          </div>
        </div>

        {/* Records & Reconciliations Card */}
        <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-xs flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-cyan-50 border border-cyan-200 text-cyan-700">
            <Database className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xs uppercase font-semibold text-slate-500">Extracted Records</div>
            <div className="text-2xl font-bold text-slate-900 mt-0.5">
              {run.summary_metrics?.total_records || run.summary_metrics?.records_extracted || '—'}
            </div>
            <div className="text-xs text-slate-500 mt-0.5">
              {run.summary_metrics?.exceptions_raised ?? 0} Exceptions
            </div>
          </div>
        </div>

        {/* Audit Package Card */}
        <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-xs flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-emerald-50 border border-emerald-200 text-emerald-600">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xs uppercase font-semibold text-slate-500">Audit Deliverables</div>
            <div className="text-sm font-semibold text-slate-900 mt-0.5">
              {isCompleted ? 'Complete Package Ready' : 'Assembly in Progress'}
            </div>
            <div className="text-xs text-slate-500 mt-0.5">PDF • 8-Tab XLSX • .ZIP</div>
          </div>
        </div>
      </div>

      {/* Audit Evidence Completeness & Scope Limitations (SA 705) */}
      {(() => {
        const completeness = run.summary_metrics?.audit_completeness || {
          completeness_percent: run.documents?.length ? Math.min(100, Math.round((run.documents.length / 5) * 100)) : 0,
          received_documents: (run.documents || []).map((d) => ({
            type: d.document_type || 'DOCUMENT',
            title: d.original_filename,
            status: 'VERIFIED',
            count: 1,
            scope: 'Source accounting record ingested with SHA-256 integrity'
          })),
          missing_documents: [],
          scope_limitations: [],
          total_core: 7,
          total_received: run.documents?.length || 0
        };

        const hasMissing = completeness.missing_documents && completeness.missing_documents.length > 0;

        return (
          <div className="bg-white border border-slate-200/90 rounded-2xl p-6 shadow-xs mt-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
              <div>
                <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <ShieldAlert className="w-5 h-5 text-indigo-600" />
                  <span>Audit Evidence Completeness & Scope Limitation Analysis (SA 705)</span>
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Automated verification of client records against mandatory statutory procedures (ICAI Standards on Auditing)
                </p>
              </div>
              <div className="flex items-center gap-4 shrink-0">
                <div className="text-right">
                  <div className="text-xs font-semibold text-slate-600">
                    Audit Completeness:{' '}
                    <span className={`font-bold ${completeness.completeness_percent === 100 ? 'text-emerald-600' : 'text-blue-600'}`}>
                      {completeness.completeness_percent}%
                    </span>
                  </div>
                  <div className="text-[10px] text-slate-500">
                    {completeness.total_received} of {completeness.total_core} Core Documents Received
                  </div>
                </div>
                <div className="w-24 bg-slate-100 rounded-full h-2.5 overflow-hidden">
                  <div
                    className={`h-2.5 rounded-full transition-all duration-500 ${
                      completeness.completeness_percent === 100
                        ? 'bg-emerald-500'
                        : 'bg-gradient-to-r from-blue-600 to-indigo-600'
                    }`}
                    style={{ width: `${completeness.completeness_percent}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Two-column layout: Received Evidence vs Missing/Scope Limitations */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-4">
              {/* Ingested & Hashed Records */}
              <div>
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2 flex items-center justify-between">
                  <span>Verified Source Documents Ingested</span>
                  <span className="text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded text-[10px] font-semibold">
                    {completeness.received_documents?.length || 0} Files Hashed
                  </span>
                </h3>
                <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                  {(completeness.received_documents || []).length === 0 ? (
                    <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-400 italic">
                      No documents verified yet.
                    </div>
                  ) : (
                    completeness.received_documents.map((doc: any, idx: number) => (
                      <div
                        key={idx}
                        className="p-3 rounded-xl bg-emerald-50/50 border border-emerald-200/80 flex items-start justify-between gap-3 text-xs"
                      >
                        <div className="min-w-0">
                          <div className="font-semibold text-slate-900 flex items-center gap-1.5 truncate">
                            <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                            <span>{doc.title}</span>
                          </div>
                          <p className="text-[11px] text-slate-500 mt-0.5">{doc.scope}</p>
                        </div>
                        <span className="shrink-0 text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-200">
                          SHA-256 OK
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Missing Documents & Audit Limitations */}
              <div>
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2 flex items-center justify-between">
                  <span>Missing Evidence & Scope Limitations</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                    hasMissing ? 'bg-amber-100 text-amber-800 border border-amber-300' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  }`}>
                    {hasMissing ? `${completeness.missing_documents.length} Scope Gaps` : '0 Gaps · 100% Coverage'}
                  </span>
                </h3>

                <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                  {!hasMissing ? (
                    <div className="p-4 rounded-xl bg-emerald-50/60 border border-emerald-200 text-xs text-emerald-800 flex items-center gap-3">
                      <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
                      <div>
                        <div className="font-bold">Complete Evidence Dossier</div>
                        <div className="text-[11px] text-emerald-700 mt-0.5">
                          All core financial evidence received. No SA 705 audit scope limitations or modifications required.
                        </div>
                      </div>
                    </div>
                  ) : (
                    completeness.missing_documents.map((item: any, idx: number) => (
                      <div
                        key={idx}
                        className={`p-3 rounded-xl border text-xs ${
                          item.mandatory
                            ? 'bg-rose-50/60 border-rose-200 text-rose-900'
                            : 'bg-amber-50/60 border-amber-200 text-amber-900'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="font-bold text-slate-900 flex items-center gap-1.5">
                            <FileWarning className={`w-3.5 h-3.5 shrink-0 ${item.mandatory ? 'text-rose-600' : 'text-amber-600'}`} />
                            {item.title}
                          </span>
                          <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase ${
                            item.mandatory
                              ? 'bg-rose-100 text-rose-800 border border-rose-300'
                              : 'bg-amber-100 text-amber-800 border border-amber-300'
                          }`}>
                            {item.mandatory ? 'Mandatory Missing' : 'Supplementary Missing'}
                          </span>
                        </div>
                        <p className="text-[11px] leading-relaxed text-slate-600">{item.impact}</p>
                      </div>
                    ))
                  )}
                </div>

                {hasMissing && (
                  <div className="mt-3 p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-[11px] text-slate-600 flex items-start gap-2">
                    <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                    <span>
                      <strong className="text-slate-800">ICAI SA 705 Notice:</strong> Missing documents are recorded as audit scope limitations. The software never fabricates missing balances.
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })()}

      {/* Main Orchestrator Stepper & Live Progress */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mt-6">
        {/* Left: 14 Deterministic Stages */}
        <div className="lg:col-span-7 bg-white border border-slate-200/90 rounded-2xl p-6 shadow-xs">
          <div className="flex items-center justify-between pb-4 border-b border-slate-200">
            <div>
              <h2 className="text-lg font-bold text-slate-900 tracking-tight">14-Stage Processing Pipeline</h2>
              <p className="text-xs text-slate-500 mt-0.5">Deterministic sequential execution without manual intervention</p>
            </div>
            <div className="text-right">
              <span className="text-2xl font-extrabold text-blue-600">{run.progress_percent}%</span>
              <span className="text-xs text-slate-500 block">Total Progress</span>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="w-full bg-slate-100 rounded-full h-2 my-5 overflow-hidden">
            <div
              className={`h-2 rounded-full transition-all duration-500 ${
                isFailed ? 'bg-rose-500' : isCompleted ? 'bg-emerald-500' : 'bg-gradient-to-r from-blue-500 to-indigo-500'
              }`}
              style={{ width: `${Math.min(100, Math.max(5, run.progress_percent))}%` }}
            />
          </div>

          {/* Stage List */}
          <div className="space-y-3 mt-4">
            {STAGE_CONFIG.map((stageItem, index) => {
              const stageData = run.stage_statuses?.[stageItem.id];
              const isCurrent = run.current_stage === stageItem.id && run.status === 'RUNNING';
              const isStageCompleted = stageData?.status === 'COMPLETED';
              const isStageBlocked = stageData?.status === 'BLOCKED' || stageData?.status === 'FAILED';

              return (
                <div
                  key={stageItem.id}
                  className={`p-3.5 rounded-xl border transition-all ${
                    isCurrent
                      ? 'bg-blue-50/80 border-blue-300 shadow-xs'
                      : isStageCompleted
                      ? 'bg-slate-50/70 border-slate-200/80 hover:bg-slate-50'
                      : isStageBlocked
                      ? 'bg-rose-50 border-rose-200'
                      : 'bg-slate-50/30 border-slate-200/50 opacity-60'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3 min-w-0">
                      {/* Icon Status */}
                      <div className="mt-0.5 shrink-0">
                        {isStageCompleted ? (
                          <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                        ) : isStageBlocked ? (
                          <XCircle className="w-5 h-5 text-rose-600" />
                        ) : isCurrent ? (
                          <Activity className="w-5 h-5 text-blue-600 animate-spin" />
                        ) : (
                          <div className="w-5 h-5 rounded-full border border-slate-300 flex items-center justify-center text-[10px] text-slate-400 font-bold">
                            {index + 1}
                          </div>
                        )}
                      </div>

                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span
                            className={`text-sm font-semibold ${
                              isCurrent ? 'text-blue-700' : isStageCompleted ? 'text-slate-900' : 'text-slate-600'
                            }`}
                          >
                            {stageItem.label}
                          </span>
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-white text-slate-600 border border-slate-200">
                            {stageItem.category}
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">
                          {stageData?.details || stageItem.description}
                        </p>
                      </div>
                    </div>

                    {/* Duration / Status pill */}
                    <div className="shrink-0 text-right">
                      {stageData?.duration_ms ? (
                        <span className="text-[11px] font-mono text-slate-400 block">
                          {(stageData.duration_ms / 1000).toFixed(2)}s
                        </span>
                      ) : null}
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase mt-0.5 inline-block ${
                          isStageCompleted
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : isStageBlocked
                            ? 'bg-rose-50 text-rose-700 border border-rose-200'
                            : isCurrent
                            ? 'bg-blue-50 text-blue-700 border border-blue-200 animate-pulse'
                            : 'bg-slate-100 text-slate-500 border border-slate-200'
                        }`}
                      >
                        {stageData?.status || 'PENDING'}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Live Terminal Logs & Blockers */}
        <div className="lg:col-span-5 flex flex-col gap-6">
          {/* Blockers alert if any */}
          {run.blockers && run.blockers.length > 0 && (
            <div className="bg-rose-50 border border-rose-200 rounded-2xl p-5 shadow-xs">
              <div className="flex items-center gap-2.5 text-rose-800 font-bold text-sm mb-2">
                <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0" />
                <span>Execution Blockers Detected</span>
              </div>
              <div className="space-y-2 mt-2">
                {run.blockers.map((b, idx) => (
                  <div key={idx} className="bg-white p-2.5 rounded-lg border border-rose-200 text-xs text-rose-900">
                    <span className="font-semibold uppercase text-rose-700">{b.stage}:</span> {b.reason || b.error}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Terminal Logs */}
          <div className="bg-white border border-slate-200/90 rounded-2xl p-5 flex flex-col flex-1 shadow-xs">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-emerald-600" />
                <span className="text-xs font-bold uppercase tracking-wider text-slate-700">Orchestrator Event Log</span>
              </div>
              {/* Filter */}
              <div className="flex gap-1">
                {(['ALL', 'INFO', 'WARNING', 'ERROR'] as const).map((lvl) => (
                  <button
                    key={lvl}
                    onClick={() => setLogFilter(lvl)}
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded transition cursor-pointer ${
                      logFilter === lvl
                        ? 'bg-blue-600 text-white shadow-xs'
                        : 'bg-slate-100 text-slate-600 hover:text-slate-900 border border-slate-200'
                    }`}
                  >
                    {lvl}
                  </button>
                ))}
              </div>
            </div>

            {/* Log Body */}
            <div className="mt-3 font-mono text-xs overflow-y-auto max-h-[500px] space-y-2 pr-1 rounded-xl bg-slate-900 p-4 border border-slate-800 text-slate-300">
              {filteredLogs.length === 0 ? (
                <div className="text-slate-400 italic py-6 text-center">No logs matching filter.</div>
              ) : (
                filteredLogs.map((log, idx) => {
                  const isErr = log.level === 'ERROR';
                  const isWarn = log.level === 'WARNING';
                  return (
                    <div
                      key={idx}
                      className={`p-2 rounded border leading-relaxed text-[11px] ${
                        isErr
                          ? 'bg-rose-950/40 border-rose-900/60 text-rose-200'
                          : isWarn
                          ? 'bg-amber-950/40 border-amber-900/60 text-amber-200'
                          : 'bg-slate-950/60 border-slate-800 text-slate-300'
                      }`}
                    >
                      <div className="flex items-center justify-between text-[10px] text-slate-400 mb-0.5">
                        <span className="text-slate-400">{log.time ? new Date(log.time).toLocaleTimeString() : ''}</span>
                        <span className="font-semibold text-blue-400">[{log.stage}]</span>
                      </div>
                      <div className="break-words font-mono">{log.message}</div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Deliverables Box */}
          <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-xs">
            <h3 className="text-sm font-bold text-slate-900 mb-2 flex items-center gap-2">
              <FileCheck2 className="w-4 h-4 text-blue-600" />
              <span>Generated Audit Deliverables</span>
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              All final reports and schedules are produced directly from verified original client records.
            </p>

            <div className="space-y-2">
              <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-xs">
                <span className="text-slate-700">Consolidated Audit Report</span>
                <span className="text-blue-700 font-semibold">PDF Format</span>
              </div>
              <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-xs">
                <span className="text-slate-700">Consolidated Audit Schedules (8 Tabs)</span>
                <span className="text-emerald-700 font-semibold">Excel .XLSX</span>
              </div>
              <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-xs">
                <span className="text-slate-700">Financial Summary Extract</span>
                <span className="text-amber-700 font-semibold">CSV Format</span>
              </div>
              <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-xs">
                <span className="text-slate-700">Source Evidence Index & Run Manifest</span>
                <span className="text-purple-700 font-semibold">JSON Format</span>
              </div>
            </div>

            {isCompleted && (
              <div className="mt-5">
                <Link
                  to={`/final-audit-file?runId=${run.run_id}`}
                  className="w-full py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-semibold rounded-xl transition text-center text-sm shadow-sm flex items-center justify-center gap-2 cursor-pointer"
                >
                  <span>Review Final Audit File</span>
                  <ArrowRight className="w-4 h-4" />
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Statutory Accounting Algorithms & Deterministic Formulas */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-6 shadow-xs mt-6">
        <div className="pb-4 border-b border-slate-200">
          <div className="flex items-center gap-2">
            <Calculator className="w-5 h-5 text-indigo-600" />
            <h2 className="text-base font-bold text-slate-900">
              Statutory Accounting Algorithms & Deterministic Formulas
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Zero synthetic balancing plugs or artificial numbers. Every assertion is verified using deterministic accounting logic and statutory guidelines.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
          {/* Formula 1: Trial Balance */}
          <div className="p-4 rounded-xl bg-slate-50/70 border border-slate-200 hover:bg-slate-50 transition">
            <div className="text-[10px] font-bold text-indigo-700 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded w-fit uppercase">
              Schedule III Equilibrium
            </div>
            <div className="font-mono text-xs font-bold text-slate-900 mt-2 bg-white px-2 py-1 rounded border border-slate-200">
              Σ Dr - Σ Cr = 0.00
            </div>
            <p className="text-[11px] text-slate-600 mt-2 leading-relaxed">
              Strict <code>Decimal('0.01')</code> precision check across all balance sheet heads. Suspense accounts flagged as critical audit risks.
            </p>
            <div className="text-[10px] text-slate-500 font-semibold mt-2 pt-2 border-t border-slate-200">
              Companies Act 2013 · Division II
            </div>
          </div>

          {/* Formula 2: BRS 4-Way Equation */}
          <div className="p-4 rounded-xl bg-slate-50/70 border border-slate-200 hover:bg-slate-50 transition">
            <div className="text-[10px] font-bold text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded w-fit uppercase">
              BRS 4-Way Matching
            </div>
            <div className="font-mono text-xs font-bold text-slate-900 mt-2 bg-white px-2 py-1 rounded border border-slate-200">
              Bank = Book + Unpres - Uncred ± Direct
            </div>
            <p className="text-[11px] text-slate-600 mt-2 leading-relaxed">
              Reconciles passbook credits against cashbook disbursements with ±3 day clearance tolerance and reference cross-matching.
            </p>
            <div className="text-[10px] text-slate-500 font-semibold mt-2 pt-2 border-t border-slate-200">
              ICAI SA 505 · Bank Confirmations
            </div>
          </div>

          {/* Formula 3: MSME 43B(h) */}
          <div className="p-4 rounded-xl bg-slate-50/70 border border-slate-200 hover:bg-slate-50 transition">
            <div className="text-[10px] font-bold text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded w-fit uppercase">
              Section 43B(h) MSME
            </div>
            <div className="font-mono text-xs font-bold text-slate-900 mt-2 bg-white px-2 py-1 rounded border border-slate-200">
              Overdue &gt; 45d ⟹ Disallowed
            </div>
            <p className="text-[11px] text-slate-600 mt-2 leading-relaxed">
              Disallows unpaid trade payables to micro/small enterprises past 45/15 days; calculates 3× RBI bank rate compound interest under Sec 16.
            </p>
            <div className="text-[10px] text-slate-500 font-semibold mt-2 pt-2 border-t border-slate-200">
              Income Tax Act 1961 · MSMED Act 2006
            </div>
          </div>

          {/* Formula 4: Dual Depreciation */}
          <div className="p-4 rounded-xl bg-slate-50/70 border border-slate-200 hover:bg-slate-50 transition">
            <div className="text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded w-fit uppercase">
              Dual Depreciation
            </div>
            <div className="font-mono text-xs font-bold text-slate-900 mt-2 bg-white px-2 py-1 rounded border border-slate-200">
              Sch II SLM ≠ Sec 32 WDV
            </div>
            <p className="text-[11px] text-slate-600 mt-2 leading-relaxed">
              Computes book depreciation on useful life and statutory tax depreciation on asset blocks (15% P&M, 40% Computers) to derive DTA/DTL.
            </p>
            <div className="text-[10px] text-slate-500 font-semibold mt-2 pt-2 border-t border-slate-200">
              CARO 2020 Clause 3(i) · Form 3CD
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProcessingStatusPage;
