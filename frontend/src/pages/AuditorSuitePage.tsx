import React, { useEffect, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  ShieldCheck,
  Play,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Sliders,
  FileCheck,
  Loader2,
  Layers,
  BookOpen,
  Building,
  Calendar,
  AlertOctagon,
  Users,
  RotateCw,
  ExternalLink,
  Info,
  DollarSign,
  Briefcase,
  Package,
  CheckSquare,
  Award,
  Lock,
  X,
  Zap,
} from 'lucide-react';
import { Header } from '../components/Header';
import { StatutoryClauseDetailModal } from '../components/StatutoryClauseDetailModal';
import { api } from '../services/api';
import {
  ProcedureExecution,
  EngagementWorkflowConfig,
  FixedAssetItem,
  SubledgerAgingRecord,
  RelatedPartyRecord,
  StatutoryClauseAuditRecord,
  CompletionChecklistResult,
} from '../types';

export const AuditorSuitePage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const getInitialTab = (raw: string | null): 'procedures' | 'workflows' | 'statutory' | 'caro' | 'aging' | 'assets' | 'forensic' | 'completion' => {
    if (raw === 'caro' || raw === 'caro-2020') return 'caro';
    if (raw === 'statutory' || raw === 'form-3cd') return 'statutory';
    if (raw === 'forensic' || raw === 'gl-scrutiny') return 'forensic';
    if (raw === 'procedures' || raw === 'schedule-iii') return 'procedures';
    if (raw === 'aging' || raw === 'subledger' || raw === 'msme') return 'aging';
    if (raw === 'assets' || raw === 'fixed-assets') return 'assets';
    if (raw === 'completion') return 'completion';
    return 'workflows';
  };

  const activeTab = getInitialTab(searchParams.get('tab'));
  const setActiveTab = (tab: 'procedures' | 'workflows' | 'statutory' | 'caro' | 'aging' | 'assets' | 'forensic' | 'completion') => {
    setSearchParams({ tab });
  };

  const [executions, setExecutions] = useState<ProcedureExecution[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRunningAll, setIsRunningAll] = useState(false);
  const [isAutoSolving, setIsAutoSolving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [selectedClause, setSelectedClause] = useState<StatutoryClauseAuditRecord | null>(null);

  // Phase 5 Completion Controls
  const [completionChecklist, setCompletionChecklist] = useState<CompletionChecklistResult | null>(null);
  const [isFinalizing, setIsFinalizing] = useState(false);
  const [overrideModalCode, setOverrideModalCode] = useState<string | null>(null);
  const [overrideReasonInput, setOverrideReasonInput] = useState('');

  // Phase 4 states
  const [engagements, setEngagements] = useState<any[]>([]);
  const [activeEngagementId, setActiveEngagementId] = useState<number | null>(null);
  const [workflowConfig, setWorkflowConfig] = useState<EngagementWorkflowConfig | null>(null);
  const [fixedAssets, setFixedAssets] = useState<FixedAssetItem[]>([]);
  const [farSummary, setFarSummary] = useState<any>(null);
  const [subledgerAging, setSubledgerAging] = useState<SubledgerAgingRecord[]>([]);
  const [subledgerSummary, setSubledgerSummary] = useState<any>(null);
  const [relatedParties, setRelatedParties] = useState<RelatedPartyRecord[]>([]);
  const [forensicData, setForensicData] = useState<any>(null);
  const [statutoryClauses, setStatutoryClauses] = useState<StatutoryClauseAuditRecord[]>([]);
  const [applicability, setApplicability] = useState<any>(null);

  // SA 320 Materiality state
  const [benchmarkAmount, setBenchmarkAmount] = useState('13000000.00'); // PBT: 1.30 Crore
  const [benchmarkPct, setBenchmarkPct] = useState('5.0');
  const [overallMat, setOverallMat] = useState(650000);
  const [perfMat, setPerfMat] = useState(487500);
  const [trivialThreshold, setTrivialThreshold] = useState(32500);

  const calculateMateriality = (amtStr: string, pctStr: string) => {
    const amt = parseFloat(amtStr) || 0;
    const pct = parseFloat(pctStr) || 0;
    const overall = (amt * pct) / 100;
    setOverallMat(overall);
    setPerfMat(overall * 0.75);
    setTrivialThreshold(overall * 0.05);
  };

  const loadData = useCallback(async (targetId?: number) => {
    setIsLoading(true);
    try {
      let resolvedId = targetId ?? activeEngagementId;
      if (!resolvedId) {
        const engs = await api.getEngagements().catch(() => []);
        setEngagements(engs || []);
        if (engs && engs.length > 0) {
          resolvedId = engs[0].id;
          setActiveEngagementId(resolvedId);
        }
      }

      const [execData, wConfig, faData, agingData, rpData, forensicRes, clausesData, appRes, chkRes] = await Promise.all([
        api.getProcedureExecutions().catch(() => []),
        api.getWorkflowConfig(resolvedId || undefined).catch(() => null),
        api.getFixedAssets(resolvedId || undefined).catch(() => []),
        api.getSubledgerAging(resolvedId || undefined).catch(() => []),
        api.getRelatedParties(resolvedId || undefined).catch(() => []),
        api.runForensicJournals(resolvedId || undefined).catch(() => null),
        api.getStatutoryClauses(resolvedId || undefined).catch(() => []),
        api.getStatutoryApplicability(resolvedId || undefined).catch(() => null),
        api.getCompletionChecklist(resolvedId || undefined).catch(() => null),
      ]);

      setExecutions(execData || []);
      setWorkflowConfig(wConfig && typeof wConfig === 'object' && !('detail' in wConfig) ? wConfig : null);
      setFixedAssets(Array.isArray(faData) ? faData : []);
      setSubledgerAging(Array.isArray(agingData) ? agingData : []);
      setRelatedParties(Array.isArray(rpData) ? rpData : []);
      setForensicData(forensicRes);
      setStatutoryClauses(Array.isArray(clausesData) ? clausesData : []);
      setApplicability(appRes);

      let safeChecklist: CompletionChecklistResult | null = null;
      if (chkRes && typeof chkRes === 'object' && !('detail' in chkRes)) {
        safeChecklist = {
          ...chkRes,
          blockers: Array.isArray(chkRes.blockers) ? chkRes.blockers : [],
          checklist_items: Array.isArray(chkRes.checklist_items) ? chkRes.checklist_items : [],
          permitted_exceptions: Array.isArray(chkRes.permitted_exceptions) ? chkRes.permitted_exceptions : [],
          completion_percentage: chkRes.completion_percentage ?? 0,
          overall_status: chkRes.overall_status ?? 'PENDING',
          can_finalize: Boolean(chkRes.can_finalize),
          is_finalized: Boolean(chkRes.is_finalized),
        };
      }
      setCompletionChecklist(safeChecklist);
    } catch (err) {
      console.error('Error loading auditor suite data', err);
    } finally {
      setIsLoading(false);
    }
  }, [activeEngagementId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleFinalizeEngagement = async (justification: string = "All audit procedures, reconciliations, and workpapers verified by Lead Partner.") => {
    setIsFinalizing(true);
    try {
      const res = await api.finalizeEngagement(activeEngagementId || undefined, justification);
      setSuccessMsg(res.message);
      await loadData(activeEngagementId || undefined);
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err: any) {
      alert(`Finalization blocked: ${err.message || (err.blockers ? err.blockers.join('; ') : 'Mandatory criteria incomplete')}`);
    } finally {
      setIsFinalizing(false);
    }
  };

  const handleRecordOverride = async () => {
    if (!overrideModalCode || !overrideReasonInput) return;
    try {
      await api.overrideChecklistException(activeEngagementId || undefined, overrideModalCode, overrideReasonInput);
      setOverrideModalCode(null);
      setOverrideReasonInput('');
      setSuccessMsg('Partner override recorded with audit trail.');
      await loadData(activeEngagementId || undefined);
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      alert(err.error || 'Failed to record exception override.');
    }
  };

  const handleRunAll = async () => {
    setIsRunningAll(true);
    try {
      const res = await api.runAllProcedures();
      setSuccessMsg(res.message);
      await loadData();
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err) {
      console.error(err);
    } finally {
      setIsRunningAll(false);
    }
  };

  const handleRunFarAudit = async () => {
    try {
      const res = await api.runFarAudit(activeEngagementId || 1);
      setFarSummary(res.summary);
      setFixedAssets(res.assets || []);
      setSuccessMsg("Fixed Asset Register & dual depreciation recalculated successfully.");
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err) {
      console.error(err);
    }
  };

  const handleAutoSolveAll = async () => {
    setIsAutoSolving(true);
    try {
      const res = await api.initializeStatutoryClauses(activeEngagementId || 1);
      setStatutoryClauses(res.clauses || []);
      setSuccessMsg(res.message || "100% Autonomous AI Audit Completed: All clauses audited and workpapers approved.");
      await loadData(activeEngagementId || undefined);
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err: any) {
      alert(`Autonomous Audit failed: ${err.message || err.error || 'Server error'}`);
    } finally {
      setIsAutoSolving(false);
    }
  };

  const handleInitClauses = async () => {
    return handleAutoSolveAll();
  };

  return (
    <div className="min-h-screen bg-slate-50/70">
      <Header
        title="India-Specific CA Audit & Statutory Assurance Suite"
        subtitle="Companies Act 2013 Schedule II & III, CARO 2020 Order, Form 3CD Clauses, MSMED Section 43B(h), and SA 240 Scrutiny"
      />

      <main className="p-8 max-w-7xl mx-auto space-y-6">
        {/* Active Engagement Indicator */}
        {engagements && engagements.length > 0 && (
          <div className="bg-white rounded-2xl border border-slate-200/90 px-4 py-3 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600 font-bold text-xs">
                CA
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] uppercase font-bold text-slate-400">Auditing Engagement</span>
                  <span className="text-[10px] font-bold text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded-full">
                    {engagements.find((e) => e.id === activeEngagementId)?.engagement_type || 'STATUTORY'}
                  </span>
                </div>
                <div className="text-xs font-bold text-slate-900">
                  {engagements.find((e) => e.id === activeEngagementId)?.company_name || 'Active Audit Client'} &bull; {engagements.find((e) => e.id === activeEngagementId)?.title || 'FY 2024-25'}
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={handleAutoSolveAll}
                disabled={isAutoSolving}
                className="px-4 py-2 bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-700 hover:from-blue-700 hover:to-indigo-800 text-white font-bold text-xs rounded-xl flex items-center gap-2 cursor-pointer transition shadow-xs hover:shadow-md disabled:opacity-50"
                title="Autonomously solves CARO 2020 (21 clauses), Form 3CD schedules, and SA 230 workpapers"
              >
                <Zap className={`w-3.5 h-3.5 ${isAutoSolving ? 'animate-spin' : 'text-amber-300 fill-amber-300'}`} />
                <span>{isAutoSolving ? 'Solving Everything 100%...' : '⚡ 100% Autonomous AI Audit (Auto-Solve All)'}</span>
              </button>

              {engagements.length > 1 && (
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-slate-500 font-medium">Switch Client:</span>
                  <select
                    value={activeEngagementId || ''}
                    onChange={(e) => {
                      const id = Number(e.target.value);
                      setActiveEngagementId(id);
                      loadData(id);
                    }}
                    className="bg-slate-50 border border-slate-200 text-slate-800 text-xs font-semibold rounded-xl px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
                  >
                    {engagements.map((eng) => (
                      <option key={eng.id} value={eng.id}>
                        {eng.company_name || `Company #${eng.company}`} ({eng.title})
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Navigation Tabs */}
        <div className="bg-white rounded-2xl border border-slate-200/90 p-2 shadow-xs flex flex-wrap gap-1.5">
          <button
            onClick={() => setActiveTab('workflows')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer ${
              activeTab === 'workflows' ? 'bg-blue-600 text-white shadow-xs' : 'bg-slate-50 text-slate-700 hover:bg-slate-100'
            }`}
          >
            <Layers className="w-4 h-4" />
            <span>Scope & Workflows Hub</span>
          </button>
          <button
            onClick={() => setActiveTab('statutory')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer ${
              activeTab === 'statutory' ? 'bg-blue-600 text-white shadow-xs' : 'bg-slate-50 text-slate-700 hover:bg-slate-100'
            }`}
          >
            <FileCheck className="w-4 h-4" />
            <span>Form 3CD & 3CA/3CB Matrix</span>
          </button>
          <button
            onClick={() => setActiveTab('caro')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer ${
              activeTab === 'caro' ? 'bg-blue-600 text-white shadow-xs' : 'bg-slate-50 text-slate-700 hover:bg-slate-100'
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            <span>CARO 2020 (21 Clauses)</span>
          </button>
          <button
            onClick={() => setActiveTab('aging')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer ${
              activeTab === 'aging' ? 'bg-blue-600 text-white shadow-xs' : 'bg-slate-50 text-slate-700 hover:bg-slate-100'
            }`}
          >
            <AlertOctagon className="w-4 h-4" />
            <span>MSMED & Sec 43B(h) Ageing</span>
          </button>
          <button
            onClick={() => setActiveTab('assets')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer ${
              activeTab === 'assets' ? 'bg-blue-600 text-white shadow-xs' : 'bg-slate-50 text-slate-700 hover:bg-slate-100'
            }`}
          >
            <Briefcase className="w-4 h-4" />
            <span>Fixed Assets & Dual Depn</span>
          </button>
          <button
            onClick={() => setActiveTab('forensic')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer ${
              activeTab === 'forensic' ? 'bg-blue-600 text-white shadow-xs' : 'bg-slate-50 text-slate-700 hover:bg-slate-100'
            }`}
          >
            <Users className="w-4 h-4" />
            <span>Related Parties & SA 240</span>
          </button>
          <button
            onClick={() => setActiveTab('procedures')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer ${
              activeTab === 'procedures' ? 'bg-blue-600 text-white shadow-xs' : 'bg-slate-50 text-slate-700 hover:bg-slate-100'
            }`}
          >
            <Sliders className="w-4 h-4" />
            <span>SA 320 & Execution</span>
          </button>
          <button
            onClick={() => setActiveTab('completion')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer ${
              activeTab === 'completion' ? 'bg-blue-600 text-white shadow-xs' : 'bg-slate-50 text-slate-700 hover:bg-slate-100'
            }`}
          >
            <CheckSquare className="w-4 h-4" />
            <span>Completion Controls (9 Checks)</span>
            {completionChecklist && (
              <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-extrabold ${
                completionChecklist.can_finalize ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'
              }`}>
                {completionChecklist.completion_percentage}%
              </span>
            )}
          </button>
        </div>

        {successMsg && (
          <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold px-4 py-3 rounded-2xl flex items-center justify-between">
            <span>{successMsg}</span>
            <button onClick={() => setSuccessMsg(null)} className="text-emerald-600 hover:text-emerald-900 font-bold">×</button>
          </div>
        )}

        {/* 1. Scope & Engagement Workflows Hub */}
        {activeTab === 'workflows' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-white rounded-3xl border border-slate-200/90 p-6 shadow-xs col-span-2">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <span className="text-[11px] font-bold text-blue-600 bg-blue-50 px-2.5 py-1 rounded-md">
                      {workflowConfig?.applicable_framework || 'COMPANIES_ACT_2013'}
                    </span>
                    <h3 className="text-base font-bold text-slate-900 mt-2">Active Engagement Scope Configuration</h3>
                  </div>
                  <span className="text-xs font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-1 rounded-full">
                    {workflowConfig?.completion_status || 'IN_PROGRESS'}
                  </span>
                </div>
                <p className="text-xs text-slate-600 mb-4">{workflowConfig?.scope_description}</p>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-50 p-4 rounded-2xl border border-slate-200/70 text-xs mb-6">
                  <div>
                    <span className="text-slate-400 font-bold block uppercase text-[10px]">CARO 2020</span>
                    <span className={`font-bold ${workflowConfig?.caro_applicable ? 'text-blue-600' : 'text-slate-500'}`}>
                      {workflowConfig?.caro_applicable ? 'Applicable (Company)' : 'Exempt (Non-Corp)'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 font-bold block uppercase text-[10px]">Tax Audit Form</span>
                    <span className="font-bold text-slate-900">Form {workflowConfig?.form_type || '3CA'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 font-bold block uppercase text-[10px]">MSMED Act Sec 43B(h)</span>
                    <span className="font-bold text-emerald-600">{workflowConfig?.msmed_applicable ? 'Active Filter' : 'N/A'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 font-bold block uppercase text-[10px]">Schedule III Division</span>
                    <span className="font-bold text-indigo-600">{workflowConfig?.schedule_iii_division || 'DIVISION_I'}</span>
                  </div>
                </div>

                <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-3">Statutory Document Evidence Checklist</h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                  {(workflowConfig?.required_documents || []).map((doc, idx) => (
                    <div key={idx} className="flex items-center justify-between p-2.5 rounded-xl border border-slate-200 bg-white">
                      <span className="font-medium text-slate-800">{doc.title}</span>
                      <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md">
                        <CheckCircle2 className="w-3 h-3" />
                        <span>{doc.status}</span>
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Engagement Type Selector / Switcher */}
              <div className="bg-white rounded-3xl border border-slate-200/90 p-6 shadow-xs space-y-4">
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <Briefcase className="w-4 h-4 text-blue-600" />
                  <span>Indian Engagement Types</span>
                </h3>
                <p className="text-xs text-slate-500">
                  Select applicable scope. Standards, CARO exemptions, and form templates adjust automatically.
                </p>

                <div className="space-y-2 text-xs">
                  {[
                    { type: 'STATUTORY', name: 'Statutory Audit (Companies Act 2013)', active: true, desc: 'Sch III Div I/II, CARO 2020, SA 320' },
                    { type: 'TAX_AUDIT', name: 'Tax Audit (Sec 44AB Form 3CD)', active: false, desc: 'Form 3CA/3CB, Sec 40A(3), Sec 43B(h)' },
                    { type: 'INTERNAL', name: 'Internal Audit (ICAI SIA)', active: false, desc: 'IFC Matrix, Fraud Scrutiny, SOPs' },
                    { type: 'BANK_AUDIT', name: 'Concurrent / Bank Audit', active: false, desc: 'RBI IRAC Norms, NPA Classification' },
                    { type: 'STOCK_AUDIT', name: 'Stock & Receivables Audit', active: false, desc: 'Drawing Power, Physical Stock Verification' },
                    { type: 'LLP_AUDIT', name: 'LLP Statutory Audit (LLP Act 2008)', active: false, desc: 'Form 8 Solvency, CARO Exempt!' },
                  ].map((e, idx) => (
                    <div
                      key={idx}
                      className={`p-3 rounded-2xl border transition ${
                        e.active ? 'border-blue-600 bg-blue-50/50' : 'border-slate-200 bg-slate-50/30'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-900">{e.name}</span>
                        {e.active && <span className="text-[10px] bg-blue-600 text-white font-bold px-2 py-0.5 rounded-full">Active</span>}
                      </div>
                      <p className="text-[11px] text-slate-500 mt-1">{e.desc}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 2. Form 3CD & 3CA/3CB Matrix */}
        {activeTab === 'statutory' && (
          <div className="space-y-6">
            <div className="bg-white rounded-3xl border border-slate-200/90 p-6 shadow-xs flex flex-col md:flex-row items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-indigo-700 bg-indigo-50 border border-indigo-200 px-2.5 py-1 rounded-md">
                    {applicability?.tax_audit_form?.form_type || 'FORM_3CA'}
                  </span>
                  <span className="text-xs text-slate-500">• Section 44AB Statement of Particulars</span>
                </div>
                <h3 className="text-base font-bold text-slate-900 mt-1">Tax Audit Form 3CD Clause Compliance Matrix</h3>
                <p className="text-xs text-slate-500">{applicability?.tax_audit_form?.reason}</p>
              </div>

              <button
                onClick={handleAutoSolveAll}
                disabled={isAutoSolving}
                className="px-4 py-2.5 bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-700 hover:from-blue-700 hover:to-indigo-800 text-white font-bold text-xs rounded-xl flex items-center gap-2 cursor-pointer transition shadow-xs hover:shadow-md disabled:opacity-50"
              >
                <Zap className={`w-3.5 h-3.5 ${isAutoSolving ? 'animate-spin' : 'text-amber-300 fill-amber-300'}`} />
                <span>{isAutoSolving ? 'Solving Everything 100%...' : '⚡ 1-Click 100% Autonomous AI Audit'}</span>
              </button>
            </div>

            {/* Touch to Open Notice */}
            <div className="p-3.5 bg-blue-50/80 border border-blue-200/80 rounded-2xl flex items-center justify-between text-xs text-blue-900 shadow-xs">
              <div className="flex items-center gap-2.5">
                <Info className="w-4 h-4 text-blue-600 shrink-0" />
                <span>
                  <strong>Interactive Statutory Matrix:</strong> Touch or click on any Form 3CD clause row below to inspect its detailed statutory provisions, ICAI verification criteria, substantive audit procedures, evidence trails, and reporting remarks.
                </span>
              </div>
            </div>

            <div className="bg-white rounded-3xl border border-slate-200/90 shadow-xs overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider font-bold border-b border-slate-200/80">
                  <tr>
                    <th className="py-3.5 px-6">Clause Ref</th>
                    <th className="py-3.5 px-6">Clause Title & Particulars</th>
                    <th className="py-3.5 px-6">Statutory Citation</th>
                    <th className="py-3.5 px-6">Evidence Status</th>
                    <th className="py-3.5 px-6">Audit Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {statutoryClauses
                    .filter((c) => c.form_type === 'FORM_3CD')
                    .map((clause) => (
                      <tr
                        key={clause.id}
                        onClick={() => setSelectedClause(clause)}
                        className="hover:bg-blue-50/60 cursor-pointer transition group"
                        title="Touch to open detailed statutory working paper"
                      >
                        <td className="py-3.5 px-6 font-mono font-bold text-blue-600">
                          <span className="flex items-center gap-1.5">
                            <span>{clause.clause_number}</span>
                            <ExternalLink className="w-3 h-3 text-blue-400 group-hover:text-blue-600 opacity-60 group-hover:opacity-100 transition" />
                          </span>
                        </td>
                        <td className="py-3.5 px-6">
                          <div className="font-bold text-slate-900 flex items-center gap-2">
                            <span className="group-hover:text-blue-700 transition">{clause.clause_title}</span>
                            <span className="text-[10px] font-semibold text-blue-600 bg-blue-50 border border-blue-200 px-1.5 py-0.5 rounded opacity-0 group-hover:opacity-100 transition">
                              Touch for Details
                            </span>
                          </div>
                          <div className="text-[11px] text-slate-500 mt-0.5">{clause.auditor_remarks}</div>
                        </td>
                        <td className="py-3.5 px-6 font-mono text-[11px] text-slate-600">{clause.statutory_citation}</td>
                        <td className="py-3.5 px-6">
                          <span className="inline-flex items-center gap-1 font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md text-[11px]">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>{clause.evidence_status}</span>
                          </span>
                        </td>
                        <td className="py-3.5 px-6">
                          <span className={`inline-flex items-center gap-1 font-bold px-2 py-0.5 rounded-md text-[11px] ${
                            clause.compliance_status === 'COMPLIANT'
                              ? 'text-emerald-700 bg-emerald-50'
                              : 'text-amber-700 bg-amber-50'
                          }`}>
                            {clause.compliance_status}
                          </span>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 3. CARO 2020 Assurance */}
        {activeTab === 'caro' && (
          <div className="space-y-6">
            <div className="bg-white rounded-3xl border border-slate-200/90 p-6 shadow-xs flex flex-col md:flex-row items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-bold px-2.5 py-1 rounded-md ${
                    applicability?.caro_2020?.is_applicable
                      ? 'text-blue-700 bg-blue-50 border border-blue-200'
                      : 'text-amber-700 bg-amber-50 border border-amber-200'
                  }`}>
                    {applicability?.caro_2020?.is_applicable ? 'CARO 2020 Applicable' : 'CARO 2020 Exempt'}
                  </span>
                  <span className="text-xs text-slate-500">• Ministry of Corporate Affairs (Order S.O. 849(E))</span>
                </div>
                <h3 className="text-base font-bold text-slate-900 mt-1">Companies (Auditor's Report) Order, 2020 — 21 Clauses Checklist</h3>
                <p className="text-xs text-slate-500">{applicability?.caro_2020?.reason}</p>
              </div>

              <button
                onClick={handleAutoSolveAll}
                disabled={isAutoSolving}
                className="px-4 py-2.5 bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-700 hover:from-blue-700 hover:to-indigo-800 text-white font-bold text-xs rounded-xl flex items-center gap-2 cursor-pointer transition shadow-xs hover:shadow-md disabled:opacity-50"
              >
                <Zap className={`w-3.5 h-3.5 ${isAutoSolving ? 'animate-spin' : 'text-amber-300 fill-amber-300'}`} />
                <span>{isAutoSolving ? 'Solving Everything 100%...' : '⚡ 1-Click 100% Autonomous AI Audit'}</span>
              </button>
            </div>

            {/* Interactive Touch Notice */}
            <div className="p-3.5 bg-blue-50/80 border border-blue-200/80 rounded-2xl flex items-center justify-between text-xs text-blue-900 shadow-xs">
              <div className="flex items-center gap-2.5">
                <Info className="w-4 h-4 text-blue-600 shrink-0" />
                <span>
                  <strong>Interactive ICAI Working Paper:</strong> Touch or click any CARO 2020 clause card below to inspect full statutory details, ICAI sub-clauses, substantive audit procedures, grounded evidence metrics, and live auditor reporting drafts.
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {statutoryClauses
                .filter((c) => c.form_type === 'CARO_2020')
                .map((cl) => (
                  <div
                    key={cl.id}
                    onClick={() => setSelectedClause(cl)}
                    className="bg-white rounded-2xl border border-slate-200/90 p-5 shadow-xs space-y-3 hover:border-blue-400 hover:shadow-md transition cursor-pointer group flex flex-col justify-between"
                    title="Touch to open detailed statutory working paper"
                  >
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-md flex items-center gap-1.5">
                          <span>{cl.clause_number}</span>
                          <ExternalLink className="w-3 h-3 text-blue-400 group-hover:text-blue-600 opacity-60 group-hover:opacity-100 transition" />
                        </span>
                        <span className={`text-[11px] font-bold px-2 py-0.5 rounded-md ${
                          cl.compliance_status === 'COMPLIANT'
                            ? 'bg-emerald-50 text-emerald-700'
                            : cl.compliance_status === 'EXEMPT'
                            ? 'bg-slate-100 text-slate-600'
                            : 'bg-rose-50 text-rose-700'
                        }`}>
                          {cl.compliance_status}
                        </span>
                      </div>
                      <h4 className="text-xs font-bold text-slate-900 group-hover:text-blue-700 transition leading-snug">{cl.clause_title}</h4>
                      <p className="text-[11px] text-slate-500 line-clamp-3 leading-relaxed">{cl.auditor_remarks}</p>
                    </div>

                    <div className="pt-2.5 border-t border-slate-100 flex items-center justify-between text-[10px]">
                      <span className="text-slate-400 font-mono truncate max-w-[170px]">{cl.statutory_citation}</span>
                      <span className="text-blue-600 font-semibold group-hover:underline flex items-center gap-1">
                        <span>Touch for Details</span> &rarr;
                      </span>
                    </div>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* 4. MSMED & Sec 43B(h) / Subledger Ageing */}
        {activeTab === 'aging' && (
          <div className="space-y-6">
            {/* Section 43B(h) Banner Alert */}
            <div className="bg-gradient-to-r from-rose-50 via-amber-50 to-orange-50 border border-rose-200 rounded-3xl p-6 shadow-xs flex flex-col md:flex-row items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 text-rose-700 font-bold text-xs uppercase tracking-wider">
                  <AlertOctagon className="w-4 h-4" />
                  <span>Section 43B(h) MSMED Act 2006 Statutory Disallowance Screen</span>
                </div>
                <h3 className="text-base font-bold text-slate-900 mt-1">
                  Overdue Micro & Small Enterprise Payables (&gt;45 Days)
                </h3>
                <p className="text-xs text-slate-600 mt-1 max-w-3xl">
                  Finance Act 2023 insertion requires actual payment to Micro and Small enterprises within statutory time limit (45 days under written agreement, 15 days without). Failing this, sum is disallowed in current FY and reported in Form 3CD Clause 22.
                </p>
              </div>

              <div className="bg-white p-4 rounded-2xl border border-rose-200 text-center shadow-xs">
                <span className="text-[10px] uppercase font-bold text-slate-400 block">43B(h) Disallowance Pool</span>
                <span className="text-lg font-bold font-mono text-rose-600">
                  ₹{subledgerAging
                    .filter((a) => a.is_overdue_43bh)
                    .reduce((sum, a) => sum + parseFloat(a.outstanding_amount || '0'), 0)
                    .toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </span>
                <span className="text-[10px] block text-rose-500 font-semibold mt-0.5">
                  {subledgerAging.filter((a) => a.is_overdue_43bh).length} Invoices Overdue
                </span>
              </div>
            </div>

            {/* Subledger Items Table */}
            <div className="bg-white rounded-3xl border border-slate-200/90 shadow-xs overflow-hidden">
              <div className="p-4 border-b border-slate-200/80 flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-900">Trade Receivables & Payables Ageing Schedule</h3>
                <span className="text-xs font-semibold text-slate-500">As of 31-Mar-2025</span>
              </div>

              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider font-bold border-b border-slate-200/80">
                  <tr>
                    <th className="py-3 px-6">Type</th>
                    <th className="py-3 px-6">Party Name</th>
                    <th className="py-3 px-6">MSME Category</th>
                    <th className="py-3 px-6">Invoice Ref</th>
                    <th className="py-3 px-6">Ageing Bucket</th>
                    <th className="py-3 px-6 text-right">Outstanding (₹)</th>
                    <th className="py-3 px-6">43B(h) Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {subledgerAging.map((row) => (
                    <tr key={row.id} className={row.is_overdue_43bh ? 'bg-rose-50/30' : 'hover:bg-slate-50/50'}>
                      <td className="py-3 px-6">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${
                          row.item_type === 'RECEIVABLE' ? 'bg-blue-50 text-blue-700' : 'bg-purple-50 text-purple-700'
                        }`}>
                          {row.item_type}
                        </span>
                      </td>
                      <td className="py-3 px-6 font-bold text-slate-900">{row.party_name}</td>
                      <td className="py-3 px-6">
                        <span className={`text-[11px] font-medium ${row.is_msme ? 'text-blue-700 font-bold' : 'text-slate-400'}`}>
                          {row.msme_type}
                        </span>
                      </td>
                      <td className="py-3 px-6 font-mono text-slate-600">{row.invoice_number}</td>
                      <td className="py-3 px-6">
                        <span className="font-semibold text-slate-700 bg-slate-100 px-2 py-0.5 rounded-md text-[11px]">
                          {row.ageing_bucket} ({row.ageing_days}d)
                        </span>
                      </td>
                      <td className="py-3 px-6 text-right font-mono font-bold text-slate-900">
                        ₹{parseFloat(row.outstanding_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 px-6">
                        {row.is_overdue_43bh ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-rose-700 bg-rose-50 px-2 py-0.5 rounded-md border border-rose-200">
                            <AlertTriangle className="w-3 h-3" />
                            <span>Overdue (&gt;45d)</span>
                          </span>
                        ) : (
                          <span className="text-[11px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md">
                            Compliant
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 5. Fixed Assets & Depreciation */}
        {activeTab === 'assets' && (
          <div className="space-y-6">
            <div className="bg-white rounded-3xl border border-slate-200/90 p-6 shadow-xs flex flex-col md:flex-row items-center justify-between gap-4">
              <div>
                <h3 className="text-base font-bold text-slate-900">Fixed Asset Register & Dual Depreciation Engine</h3>
                <p className="text-xs text-slate-500 mt-1">
                  Automated comparison: Companies Act 2013 Schedule II Useful Life (SLM/WDV) vs Income Tax Act Section 32 Block of Assets (with &lt;180 days half-rate rule).
                </p>
              </div>

              <button
                onClick={handleRunFarAudit}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs rounded-xl flex items-center gap-2 cursor-pointer transition shadow-xs"
              >
                <Play className="w-3.5 h-3.5 fill-white" />
                <span>Recalculate Dual Depreciation</span>
              </button>
            </div>

            <div className="bg-white rounded-3xl border border-slate-200/90 shadow-xs overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider font-bold border-b border-slate-200/80">
                  <tr>
                    <th className="py-3 px-6">Asset ID</th>
                    <th className="py-3 px-6">Asset Name</th>
                    <th className="py-3 px-6">Class</th>
                    <th className="py-3 px-6 text-right">Cost (₹)</th>
                    <th className="py-3 px-6 text-right">Sch II Depn (₹)</th>
                    <th className="py-3 px-6 text-right">Sec 32 Depn (₹)</th>
                    <th className="py-3 px-6">Put to Use</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {fixedAssets.map((fa) => (
                    <tr key={fa.id} className="hover:bg-slate-50/50">
                      <td className="py-3 px-6 font-mono font-bold text-blue-600">{fa.asset_id}</td>
                      <td className="py-3 px-6 font-bold text-slate-900">{fa.asset_name}</td>
                      <td className="py-3 px-6 text-slate-500">{fa.category}</td>
                      <td className="py-3 px-6 text-right font-mono font-bold text-slate-900">
                        ₹{parseFloat(fa.original_cost).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 px-6 text-right font-mono font-bold text-indigo-600">
                        ₹{parseFloat(fa.sch_ii_depreciation).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 px-6 text-right font-mono font-bold text-emerald-600">
                        ₹{parseFloat(fa.sec_32_depreciation).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 px-6 text-slate-500 font-mono text-[11px]">{fa.put_to_use_date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 6. Forensic & Related Party Scrutiny */}
        {activeTab === 'forensic' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Related Parties */}
              <div className="bg-white rounded-3xl border border-slate-200/90 p-6 shadow-xs space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">Section 2(76) / AS 18 Related Parties</h3>
                    <p className="text-xs text-slate-500">Entities requiring Section 188 arm's length scrutiny</p>
                  </div>
                  <span className="text-xs font-bold text-blue-700 bg-blue-50 px-2.5 py-1 rounded-full">
                    {relatedParties.length} Configured
                  </span>
                </div>

                <div className="space-y-3 text-xs">
                  {relatedParties.map((rp) => (
                    <div key={rp.id} className="p-3.5 rounded-2xl border border-slate-200 bg-slate-50/50 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-900">{rp.party_name}</span>
                        <span className="font-mono text-[11px] text-slate-500 font-semibold">{rp.pan}</span>
                      </div>
                      <div className="text-[11px] text-blue-600 font-semibold">{rp.relationship_type}</div>
                      <p className="text-[11px] text-slate-500">{rp.notes}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* SA 240 Forensic Journal Vouchers */}
              <div className="bg-white rounded-3xl border border-slate-200/90 p-6 shadow-xs space-y-4">
                <div>
                  <h3 className="text-sm font-bold text-slate-900">SA 240 Forensic Journal Entries Scrutiny</h3>
                  <p className="text-xs text-slate-500">Automated indicators of management override of controls</p>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="p-3 bg-slate-50 rounded-2xl border border-slate-200/80">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block">Weekend Postings</span>
                    <span className="text-base font-bold text-slate-900 font-mono">
                      {forensicData?.weekend_journals_count || 0}
                    </span>
                    <span className="text-[10px] text-slate-500 block mt-0.5">Saturday / Sunday vouchers</span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-2xl border border-slate-200/80">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block">Round Amounts</span>
                    <span className="text-base font-bold text-slate-900 font-mono">
                      {forensicData?.round_amount_journals_count || 0}
                    </span>
                    <span className="text-[10px] text-slate-500 block mt-0.5">Multiples of 50k / 1 Lakh</span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-2xl border border-slate-200/80">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block">Period-End Vouchers</span>
                    <span className="text-base font-bold text-slate-900 font-mono">
                      {forensicData?.period_end_journals_count || 0}
                    </span>
                    <span className="text-[10px] text-slate-500 block mt-0.5">Posted ±5 days of 31-March</span>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-2xl border border-slate-200/80">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block">Direct Revenue Debits</span>
                    <span className="text-base font-bold text-slate-900 font-mono">
                      {forensicData?.unusual_combinations_count || 0}
                    </span>
                    <span className="text-[10px] text-slate-500 block mt-0.5">Potential revenue reversals</span>
                  </div>
                </div>

                <div className="p-3 rounded-2xl bg-amber-50 border border-amber-200 text-amber-800 text-[11px]">
                  <strong>SA 240 Notice:</strong> {forensicData?.disclaimer || "Observations represent risk indicators under SA 240."}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 7. Procedures & Materiality Tab */}
        {activeTab === 'procedures' && (
          <div className="space-y-6">
            <div className="flex flex-col lg:flex-row gap-6">
              {/* SA 320 Materiality Calculator Card */}
              <div className="flex-1 bg-white rounded-3xl border border-slate-200/90 p-6 shadow-xs">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-blue-600" />
                    <h3 className="text-sm font-bold text-slate-900">SA 320 Materiality Framework</h3>
                  </div>
                  <span className="text-[11px] font-semibold text-slate-500 bg-slate-100 px-2.5 py-1 rounded-full">
                    Standard on Auditing SA 320
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="text-[11px] font-semibold text-slate-600 mb-1 block">
                      PBT Benchmark Amount (₹)
                    </label>
                    <input
                      type="text"
                      value={benchmarkAmount}
                      onChange={(e) => {
                        setBenchmarkAmount(e.target.value);
                        calculateMateriality(e.target.value, benchmarkPct);
                      }}
                      className="w-full px-3 py-1.5 rounded-xl border border-slate-200 text-xs font-mono font-medium focus:ring-1 focus:ring-blue-600 outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-slate-600 mb-1 block">
                      Benchmark Rate (%)
                    </label>
                    <input
                      type="text"
                      value={benchmarkPct}
                      onChange={(e) => {
                        setBenchmarkPct(e.target.value);
                        calculateMateriality(benchmarkAmount, e.target.value);
                      }}
                      className="w-full px-3 py-1.5 rounded-xl border border-slate-200 text-xs font-mono font-medium focus:ring-1 focus:ring-blue-600 outline-none"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-3 bg-slate-50 p-3.5 rounded-2xl border border-slate-200/70">
                  <div>
                    <div className="text-[10px] uppercase font-bold text-slate-400">Overall Materiality</div>
                    <div className="text-sm font-bold text-slate-900 font-mono mt-0.5">
                      ₹{overallMat.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase font-bold text-slate-400">Performance (75%)</div>
                    <div className="text-sm font-bold text-blue-600 font-mono mt-0.5">
                      ₹{perfMat.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase font-bold text-slate-400">Clearly Trivial (5%)</div>
                    <div className="text-sm font-bold text-slate-600 font-mono mt-0.5">
                      ₹{trivialThreshold.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                    </div>
                  </div>
                </div>
              </div>

              {/* Action Card: Run Substantive Testing */}
              <div className="w-full lg:w-96 bg-gradient-to-br from-[#0c1533] to-[#080d20] rounded-3xl p-6 text-white flex flex-col justify-between shadow-xs">
                <div>
                  <div className="flex items-center gap-2 text-cyan-400 text-xs font-bold uppercase tracking-wider mb-2">
                    <ShieldCheck className="w-4 h-4" />
                    <span>Automated Audit Execution</span>
                  </div>
                  <h3 className="text-base font-bold text-white">Execute All Statutory Procedures</h3>
                  <p className="text-xs text-slate-300 mt-1">
                    Runs cut-off testing, Section 40A(3), Form 3CD Clause 34 TDS, CARO 2020 PPE & Benford's Law scrutiny across all ledgers.
                  </p>
                </div>

                <button
                  onClick={handleRunAll}
                  disabled={isRunningAll}
                  className="mt-4 w-full py-3 bg-[#1d63ed] hover:bg-blue-600 active:bg-blue-700 text-white font-semibold text-xs rounded-xl flex items-center justify-center gap-2 cursor-pointer transition disabled:opacity-50"
                >
                  {isRunningAll ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Evaluating Audit Rules...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4 fill-white" />
                      <span>Run Complete Audit Procedures</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Procedures Execution List */}
            <div className="bg-white rounded-3xl border border-slate-200/90 shadow-xs p-6 space-y-4">
              <h3 className="text-base font-bold text-slate-900">Configured Audit Procedures Execution Log</h3>
              <div className="space-y-4">
                {executions.map((exec) => (
                  <div
                    key={exec.id}
                    className="border border-slate-200/90 rounded-2xl p-5 hover:border-blue-300 transition duration-150 bg-slate-50/20"
                  >
                    <div className="flex items-start justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-md">
                            {exec.procedure_code}
                          </span>
                          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                            • {exec.category}
                          </span>
                        </div>
                        <h4 className="text-sm font-bold text-slate-900">{exec.procedure_title}</h4>
                        <p className="text-xs text-slate-600 max-w-3xl mt-1">{exec.summary_findings}</p>
                      </div>

                      <div>
                        {exec.status === 'PASSED_NO_EXCEPTIONS' ? (
                          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Compliant (0 Exceptions)</span>
                          </span>
                        ) : exec.status === 'PASSED_WITH_EXCEPTIONS' ? (
                          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200">
                            <AlertTriangle className="w-3.5 h-3.5" />
                            <span>{exec.exceptions_count} Exceptions Detected</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-slate-100 text-slate-600">
                            <Clock className="w-3.5 h-3.5" />
                            <span>Ready to Run</span>
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-3 mt-3 border-t border-slate-100 text-[11px] text-slate-400">
                      <span>Tested records: {exec.tested_records_count} transactions</span>
                      <span>Last executed: {new Date(exec.executed_at).toLocaleString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* 8. Engagement Completion Controls (9 Checks) */}
        {activeTab === 'completion' && (
          completionChecklist ? (
            <div className="space-y-6">
              {/* Status & Finalize Banner */}
              <div className="bg-white rounded-3xl border border-slate-200/90 p-6 shadow-xs flex flex-wrap items-center justify-between gap-6">
                <div>
                  <div className="flex items-center gap-2">
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${
                      completionChecklist.overall_status === 'COMPLETED'
                        ? 'bg-emerald-100 text-emerald-800'
                        : completionChecklist.can_finalize
                        ? 'bg-blue-100 text-blue-800'
                        : 'bg-rose-100 text-rose-800'
                    }`}>
                      {completionChecklist.overall_status || 'PENDING'}
                    </span>
                    <span className="text-xs font-bold text-slate-500">
                      Completion Progress: {completionChecklist.completion_percentage ?? 0}%
                    </span>
                  </div>
                  <h3 className="text-lg font-bold text-slate-900 mt-2">
                    Statutory Engagement Completion Controls
                  </h3>
                  <p className="text-xs text-slate-500">
                    Real-time 9-point rule evaluation. Finalization fails closed if any mandatory condition remains unaddressed.
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  <button
                    onClick={() => handleFinalizeEngagement()}
                    disabled={!completionChecklist.can_finalize || isFinalizing || completionChecklist.is_finalized}
                    className="px-6 py-3 bg-emerald-700 hover:bg-emerald-600 disabled:bg-slate-300 text-white rounded-2xl text-xs font-bold flex items-center gap-2 cursor-pointer transition shadow-sm disabled:cursor-not-allowed"
                  >
                    {isFinalizing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Award className="w-4 h-4" />}
                    <span>{completionChecklist.is_finalized ? 'Engagement Finalized' : 'Finalize & Sign Audit Engagement'}</span>
                  </button>
                </div>
              </div>

              {/* Blockers alert if any */}
              {(completionChecklist.blockers || []).length > 0 && (
                <div className="bg-rose-50 border border-rose-200 rounded-3xl p-6 text-xs text-rose-950 space-y-3">
                  <div className="flex items-center gap-2 font-bold text-rose-900 text-sm">
                    <AlertTriangle className="w-4 h-4 text-rose-700" />
                    <span>Finalization Blocked ({(completionChecklist.blockers || []).length} Unresolved Conditions)</span>
                  </div>
                  <ul className="list-disc pl-5 space-y-1 font-medium">
                    {(completionChecklist.blockers || []).map((b, idx) => (
                      <li key={idx}>{b}</li>
                    ))}
                  </ul>
                  <p className="text-[11px] text-rose-800 pt-1 border-t border-rose-200/60 italic">
                    To finalize, either resolve the underlying exceptions or record an authorized CA partner permitted exception with justification below.
                  </p>
                </div>
              )}

              {/* 9-Point Checklist Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {(completionChecklist.checklist_items || []).map((item) => (
                  <div
                    key={item.code}
                    className={`bg-white rounded-2xl border p-5 space-y-3 shadow-2xs ${
                      item.is_satisfied
                        ? 'border-emerald-200 bg-emerald-50/20'
                        : item.is_overridden
                        ? 'border-blue-200 bg-blue-50/20'
                        : 'border-rose-200 bg-rose-50/20'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[10px] font-bold text-slate-400 bg-slate-100 px-2 py-0.5 rounded">
                        {item.code}
                      </span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        item.is_satisfied
                          ? 'bg-emerald-100 text-emerald-800'
                          : item.is_overridden
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-rose-100 text-rose-800'
                      }`}>
                        {item.is_satisfied ? 'Satisfied' : item.is_overridden ? 'Partner Overridden' : 'Blocked'}
                      </span>
                    </div>

                    <div>
                      <h4 className="text-xs font-bold text-slate-900">{item.title}</h4>
                      <p className="text-[11px] text-slate-600 mt-1 leading-relaxed">{item.details}</p>
                      {item.is_overridden && (
                        <p className="text-[10px] text-blue-800 italic mt-1 bg-blue-100/60 p-1.5 rounded">
                          Override note: {item.override_note}
                        </p>
                      )}
                    </div>

                    {!item.is_satisfied && (
                      <div className="pt-2 border-t border-slate-100 flex items-center justify-end">
                        <button
                          onClick={() => {
                            setOverrideModalCode(item.code);
                            setOverrideReasonInput('');
                          }}
                          className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-[10px] font-semibold transition cursor-pointer"
                        >
                          Record Partner Override
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Documented Overrides History */}
              {(completionChecklist.permitted_exceptions || []).length > 0 && (
                <div className="bg-white rounded-3xl border border-slate-200 p-6 space-y-3 shadow-xs">
                  <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Documented Partner Permitted Exceptions Audit Trail</h4>
                  <div className="space-y-2 text-xs">
                    {(completionChecklist.permitted_exceptions || []).map((ex, i) => (
                      <div key={i} className="p-3 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-between">
                        <div>
                          <span className="font-mono font-bold text-blue-700">{ex.code}</span>: <span className="text-slate-800">{ex.reason}</span>
                        </div>
                        <div className="text-[11px] text-slate-400">
                          {ex.authorized_by} • {new Date(ex.timestamp).toLocaleString()}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white rounded-3xl border border-slate-200/90 p-12 text-center shadow-xs">
              <CheckSquare className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <h3 className="text-sm font-bold text-slate-800">Completion Controls Ready</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
                No active checklist blockers detected. Upload client documents or select an active engagement to review the 9-point statutory completion controls.
              </p>
            </div>
          )
        )}

        {/* OVERRIDE EXCEPTION MODAL */}
        {overrideModalCode && (
          <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-4 border border-slate-200">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <h3 className="text-sm font-bold text-slate-900">Record Partner Permitted Exception</h3>
                <button onClick={() => setOverrideModalCode(null)} className="text-slate-400 hover:text-slate-600">
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="text-xs space-y-3">
                <div className="p-2.5 bg-blue-50 border border-blue-200 rounded-xl text-blue-900">
                  Item Code: <span className="font-mono font-bold">{overrideModalCode}</span>
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">Written Justification (Audit Trail):</label>
                  <textarea
                    rows={4}
                    value={overrideReasonInput}
                    onChange={(e) => setOverrideReasonInput(e.target.value)}
                    placeholder="Provide substantive professional reasoning for permitting this exception..."
                    className="w-full p-3 border border-slate-300 rounded-xl text-xs focus:outline-blue-500"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  onClick={() => setOverrideModalCode(null)}
                  className="px-3 py-1.5 bg-slate-100 text-slate-700 rounded-xl text-xs font-semibold cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  onClick={handleRecordOverride}
                  disabled={overrideReasonInput.length < 10}
                  className="px-4 py-1.5 bg-blue-600 disabled:bg-blue-300 text-white rounded-xl text-xs font-bold transition cursor-pointer"
                >
                  Save Partner Override
                </button>
              </div>
            </div>
          </div>
        )}

        {/* STATUTORY CLAUSE DETAIL & WORKING PAPER MODAL */}
        <StatutoryClauseDetailModal
          clause={selectedClause}
          companyName={engagements.find((e) => e.id === activeEngagementId)?.company_name || 'Active Audit Client'}
          financialYear={engagements.find((e) => e.id === activeEngagementId)?.title || 'FY 2024-25'}
          onClose={() => setSelectedClause(null)}
          onSave={(updated) => {
            setSelectedClause(updated);
            setStatutoryClauses((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
          }}
        />
      </main>
    </div>
  );
};

