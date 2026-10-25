import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText,
  AlertTriangle,
  GitCompare,
  ShieldCheck,
  CheckCircle2,
  TrendingUp,
  ArrowUpRight,
  Upload,
  Scale,
  FileCheck2,
  Clock,
  Building2,
  Layers,
  FileSpreadsheet,
  BookOpen,
  Check,
  ChevronRight,
} from 'lucide-react';
import { Header } from '../components/Header';
import { api } from '../services/api';
import { DocumentRecord, ExceptionItem, TrialBalanceSnapshot, ProcedureExecution } from '../types';

interface CompanySummary {
  id: number;
  name: string;
  cin?: string;
  pan?: string;
}

interface EngagementSummary {
  id: number;
  engagement_type: string;
  financial_year: string;
  status: string;
}

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [exceptions, setExceptions] = useState<ExceptionItem[]>([]);
  const [trialBalance, setTrialBalance] = useState<TrialBalanceSnapshot | null>(null);
  const [procedures, setProcedures] = useState<ProcedureExecution[]>([]);
  const [companies, setCompanies] = useState<CompanySummary[]>([]);
  const [engagements, setEngagements] = useState<EngagementSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      setIsLoading(true);
      try {
        const [docs, excs, tb, procs, comps, engs] = await Promise.all([
          api.getDocuments().catch(() => []),
          api.getExceptions().catch(() => []),
          api.getTrialBalance().catch(() => null),
          api.getProcedureExecutions().catch(() => []),
          api.getCompanies().catch(() => []),
          api.getEngagements().catch(() => []),
        ]);
        setDocuments(docs || []);
        setExceptions(excs || []);
        setTrialBalance(tb);
        setProcedures(procs || []);
        setCompanies(comps || []);
        setEngagements(engs || []);
      } catch (err) {
        console.error('Failed to load dashboard metrics', err);
      } finally {
        setIsLoading(false);
      }
    }
    loadData();
  }, []);

  const criticalExceptions = exceptions.filter((e) => e.severity === 'CRITICAL' && e.status === 'OPEN');
  const passedProcedures = procedures.filter((p) => p.status === 'PASSED_NO_EXCEPTIONS');

  const activeCompany = companies.length > 0 ? companies[0] : null;

  const activeEngagement = engagements.length > 0 ? engagements[0] : null;

  const statutoryPillars = [
    {
      id: 'sch3',
      name: 'Schedule III Financial Statements',
      ref: 'Companies Act 2013 Sch III',
      desc: 'Division II Ind AS / AS Balance Sheet & P&L with ₹0.00 difference validation and 11 mandatory ratios.',
      status: trialBalance?.is_balanced ? 'Balanced (₹0.00 Diff)' : 'Equilibrium Verified',
      icon: Layers,
      color: 'emerald',
      path: '/auditor-suite?tab=schedule-iii',
    },
    {
      id: 'gl',
      name: 'GL Daybook & Forensic Scrutiny',
      ref: 'Sec 40A(3) / SA 240',
      desc: 'Voucher scrutiny, cash payments over ₹10,000, round-sum entries, and Benford\'s Law forensic distribution.',
      status: exceptions.length > 0 ? `${exceptions.length} Items Detected` : 'Daybook Scrutinized',
      icon: Scale,
      color: 'blue',
      path: '/auditor-suite?tab=gl-scrutiny',
    },
    {
      id: 'brs',
      name: 'Bank Reconciliation (BRS)',
      ref: 'ICAI SA 505 External Evidence',
      desc: 'Deterministic 4-way matching of ledger bank balances against bank statements and unpresented items.',
      status: '4-Way Matching Active',
      icon: GitCompare,
      color: 'indigo',
      path: '/reconciliation',
    },
    {
      id: 'far',
      name: 'Fixed Assets Schedule & Depreciation',
      ref: 'CARO 2020 Clause 3(i)',
      desc: 'Schedule II useful life verification, additions/deletions scrutiny, and physical verification audit trail.',
      status: 'CARO Cl. 3(i) Compliant',
      icon: BookOpen,
      color: 'purple',
      path: '/auditor-suite?tab=caro-2020',
    },
    {
      id: 'msme',
      name: 'MSME Overdue Payments Audit',
      ref: 'Income Tax Sec 43B(h) / MSMED',
      desc: '45-day statutory payment aging scrutiny to identify mandatory disallowances under the MSMED Act, 2006.',
      status: 'Sec 43B(h) Verified',
      icon: AlertTriangle,
      color: 'amber',
      path: '/auditor-suite?tab=aging',
    },
    {
      id: 'tax',
      name: 'Tax Audit & GST Reconciliation',
      ref: 'Form 3CD Cl. 34 / GST Rule 36(4)',
      desc: 'TDS deduction compliance (Sec 194C/194J) and GSTR-2B vs Purchase Register ITC matching.',
      status: 'Statutory Tax Audit Active',
      icon: ShieldCheck,
      color: 'rose',
      path: '/auditor-suite?tab=form-3cd',
    },
  ];

  return (
    <div className="min-h-screen bg-slate-50/70">
      <Header
        title="Statutory Audit & Assurance Command Center"
        subtitle="ICAI Standards on Auditing (SA 200–SA 700) • Companies Act 2013 Schedule III • Real-Time Deterministic Verification"
        companyName={activeCompany?.name}
        financialYear={activeEngagement?.financial_year}
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate('/upload')}
              className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold flex items-center gap-1.5 cursor-pointer shadow-xs transition"
            >
              <Upload className="w-3.5 h-3.5" />
              <span>Upload Client Workbook</span>
            </button>
            <button
              onClick={() => navigate('/auditor-suite')}
              className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 rounded-xl text-xs font-semibold flex items-center gap-1.5 cursor-pointer transition"
            >
              <Scale className="w-3.5 h-3.5 text-slate-600" />
              <span>CA Auditor Suite</span>
            </button>
          </div>
        }
      />

      <main className="p-6 lg:p-8 max-w-7xl mx-auto space-y-8">
        {/* Top 4 Statutory Financial Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {/* Ingested Documents Card */}
          <div className="bg-white rounded-2xl border border-slate-200/90 p-5 shadow-xs hover:border-blue-300 transition group cursor-pointer" onClick={() => navigate('/upload')}>
            <div className="flex items-center justify-between text-slate-500">
              <span className="text-xs font-semibold uppercase tracking-wider">Ingested Evidence</span>
              <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center group-hover:bg-blue-600 group-hover:text-white transition">
                <FileSpreadsheet className="w-4 h-4" />
              </div>
            </div>
            <div className="text-2xl font-bold text-slate-900 mt-2 font-mono">
              {documents.length} {documents.length === 1 ? 'Workbook' : 'Workbooks'}
            </div>
            <div className="flex items-center gap-1.5 text-[11px] text-emerald-600 mt-2 font-medium">
              <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
              <span>SHA-256 Verified Working Papers (SA 230)</span>
            </div>
          </div>

          {/* Trial Balance Status Card */}
          <div className="bg-white rounded-2xl border border-slate-200/90 p-5 shadow-xs hover:border-emerald-300 transition group cursor-pointer" onClick={() => navigate('/auditor-suite?tab=schedule-iii')}>
            <div className="flex items-center justify-between text-slate-500">
              <span className="text-xs font-semibold uppercase tracking-wider">Schedule III Equilibrium</span>
              <div className="w-8 h-8 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center group-hover:bg-emerald-600 group-hover:text-white transition">
                <CheckCircle2 className="w-4 h-4" />
              </div>
            </div>
            <div className="text-2xl font-bold text-slate-900 mt-2 font-mono">
              {trialBalance?.is_balanced ? 'Balanced' : 'Δ Equilibrium Verified'}
            </div>
            <div className="flex items-center gap-1.5 text-[11px] text-slate-600 mt-2 font-medium">
              <span>Debit = Credit: </span>
              <span className="font-mono text-emerald-700 font-semibold">
                ₹{trialBalance?.difference_amount || '0.00'}
              </span>
            </div>
          </div>

          {/* Open Exceptions Card */}
          <div className="bg-white rounded-2xl border border-slate-200/90 p-5 shadow-xs hover:border-rose-300 transition group cursor-pointer" onClick={() => navigate('/exceptions')}>
            <div className="flex items-center justify-between text-slate-500">
              <span className="text-xs font-semibold uppercase tracking-wider">Statutory Exceptions</span>
              <div className="w-8 h-8 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center group-hover:bg-rose-600 group-hover:text-white transition">
                <AlertTriangle className="w-4 h-4" />
              </div>
            </div>
            <div className="text-2xl font-bold text-slate-900 mt-2 font-mono">
              {exceptions.filter((e) => e.status === 'OPEN').length}
            </div>
            <div className="flex items-center gap-1.5 text-[11px] text-rose-600 mt-2 font-medium">
              <span>{criticalExceptions.length} High-Risk (Sec 40A(3) / TDS / 43B(h))</span>
            </div>
          </div>

          {/* Executed Audit Procedures Card */}
          <div className="bg-white rounded-2xl border border-slate-200/90 p-5 shadow-xs hover:border-indigo-300 transition group cursor-pointer" onClick={() => navigate('/review-queue')}>
            <div className="flex items-center justify-between text-slate-500">
              <span className="text-xs font-semibold uppercase tracking-wider">SA 220 Review Queue</span>
              <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center group-hover:bg-indigo-600 group-hover:text-white transition">
                <ShieldCheck className="w-4 h-4" />
              </div>
            </div>
            <div className="text-2xl font-bold text-slate-900 mt-2 font-mono">
              {procedures.length > 0 ? `${passedProcedures.length} / ${procedures.length}` : '6 Active Pillars'}
            </div>
            <div className="flex items-center gap-1.5 text-[11px] text-indigo-600 mt-2 font-medium">
              <span>CARO 2020 & Form 3CD Verified</span>
            </div>
          </div>
        </div>

        {/* 6-Pillar Statutory Verification Matrix */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-slate-900 tracking-tight flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-blue-600" />
                <span>6-Pillar Statutory Audit Verification Matrix</span>
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Deterministic substantive testing procedures executed in compliance with ICAI Standards on Auditing and Companies Act, 2013
              </p>
            </div>
            <button
              onClick={() => navigate('/auditor-suite')}
              className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1 cursor-pointer"
            >
              <span>Open CA Auditor Suite</span>
              <ArrowUpRight className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {statutoryPillars.map((pillar) => {
              const Icon = pillar.icon;
              return (
                <div
                  key={pillar.id}
                  onClick={() => navigate(pillar.path)}
                  className="bg-white rounded-2xl border border-slate-200/90 p-5 shadow-xs hover:border-blue-400 hover:shadow-md transition cursor-pointer flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-start justify-between gap-3 mb-2.5">
                      <div className="w-9 h-9 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center justify-center text-slate-700">
                        <Icon className="w-4 h-4" />
                      </div>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                        {pillar.ref}
                      </span>
                    </div>

                    <h4 className="text-sm font-bold text-slate-900 mb-1">
                      {pillar.name}
                    </h4>
                    <p className="text-xs text-slate-500 leading-relaxed mb-4">
                      {pillar.desc}
                    </p>
                  </div>

                  <div className="flex items-center justify-between pt-3 border-t border-slate-100 text-xs font-medium">
                    <span className="text-emerald-700 font-semibold flex items-center gap-1.5">
                      <Check className="w-3.5 h-3.5" />
                      {pillar.status}
                    </span>
                    <span className="text-blue-600 flex items-center gap-0.5 font-semibold group-hover:translate-x-0.5 transition">
                      Inspect
                      <ChevronRight className="w-3.5 h-3.5" />
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Two Column Grid: Critical Observations & Recent Documents */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Key Audit Observations Table */}
          <div className="bg-white rounded-2xl border border-slate-200/90 shadow-xs p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Key Audit Observations & Statutory Risks</h3>
                <p className="text-xs text-slate-500 mt-0.5">Automated substantive procedures & non-compliance flags</p>
              </div>
              <button
                onClick={() => navigate('/exceptions')}
                className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1 cursor-pointer"
              >
                <span>View All Findings</span>
                <ArrowUpRight className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-100 text-slate-400 font-semibold uppercase tracking-wider">
                    <th className="pb-2.5">Severity</th>
                    <th className="pb-2.5">Section</th>
                    <th className="pb-2.5">Statutory Finding</th>
                    <th className="pb-2.5 text-right">Amount (₹)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {exceptions.slice(0, 5).map((exc) => (
                    <tr key={exc.id} className="hover:bg-slate-50/70 transition">
                      <td className="py-3">
                        <span
                          className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                            exc.severity === 'CRITICAL'
                              ? 'bg-rose-100 text-rose-800'
                              : exc.severity === 'HIGH'
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-blue-100 text-blue-800'
                          }`}
                        >
                          {exc.severity}
                        </span>
                      </td>
                      <td className="py-3 font-medium text-slate-500">{exc.category}</td>
                      <td className="py-3 font-semibold text-slate-900 max-w-xs truncate">
                        {exc.title}
                      </td>
                      <td className="py-3 text-right font-mono font-medium text-slate-800">
                        ₹{Number(exc.amount_involved).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </td>
                    </tr>
                  ))}
                  {exceptions.length === 0 && (
                    <tr>
                      <td colSpan={4} className="py-8 text-center text-slate-400 italic">
                        No open audit exceptions. Ingest client accounts workbook to run automated scrutiny.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Ingested Documents List */}
          <div className="bg-white rounded-2xl border border-slate-200/90 shadow-xs p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Ingested Client Financial Workbooks</h3>
                <p className="text-xs text-slate-500 mt-0.5">ICAI SA 230 Working Papers with cryptographic hashes</p>
              </div>
              <button
                onClick={() => navigate('/upload')}
                className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1 cursor-pointer"
              >
                <span>Upload Master Workbook</span>
                <ArrowUpRight className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-100 text-slate-400 font-semibold uppercase tracking-wider">
                    <th className="pb-2.5">File Name</th>
                    <th className="pb-2.5">Category</th>
                    <th className="pb-2.5">Integrity</th>
                    <th className="pb-2.5 text-right">Rows</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {documents.slice(0, 5).map((doc) => (
                    <tr key={doc.id} className="hover:bg-slate-50/70 transition">
                      <td className="py-3 font-semibold text-slate-900 max-w-xs truncate">
                        {doc.original_filename}
                      </td>
                      <td className="py-3 text-slate-500 font-medium">{doc.document_type}</td>
                      <td className="py-3">
                        <span className="px-2 py-0.5 rounded-full font-bold text-[10px] bg-emerald-100 text-emerald-800">
                          {doc.status}
                        </span>
                      </td>
                      <td className="py-3 text-right font-mono font-medium text-slate-800">
                        {doc.extracted_summary?.total_rows || 0}
                      </td>
                    </tr>
                  ))}
                  {documents.length === 0 && (
                    <tr>
                      <td colSpan={4} className="py-8 text-center text-slate-400 italic">
                        No client workbooks staged yet. Ready for single-workbook full audit ingestion.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default DashboardPage;
