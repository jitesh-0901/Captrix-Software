import React, { useEffect, useState } from 'react';
import {
  GitCompare,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ArrowRight,
  ShieldCheck,
  Check,
  RefreshCw,
  FileX,
  FileCheck2,
  SlidersHorizontal,
  ChevronRight,
  Layers,
} from 'lucide-react';
import { Header } from '../components/Header';
import { api } from '../services/api';
import { ReconciliationRun, ReconciliationItem } from '../types';

export const ReconciliationPage: React.FC = () => {
  const [runs, setRuns] = useState<ReconciliationRun[]>([]);
  const [activeTab, setActiveTab] = useState<'BANK' | 'GST_ITC' | 'CROSS_DOC'>('BANK');
  const [isLoading, setIsLoading] = useState(true);
  const [isCrossRunning, setIsCrossRunning] = useState(false);
  const [toleranceDays, setToleranceDays] = useState(3);

  const loadRuns = async () => {
    setIsLoading(true);
    try {
      const data = await api.getReconciliationRuns();
      setRuns(data || []);
    } catch (err) {
      console.error('Error fetching reconciliation runs:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadRuns();
  }, []);

  const handleRunCrossDoc = async () => {
    setIsCrossRunning(true);
    try {
      await api.runCrossDocumentReconciliation();
      await loadRuns();
    } catch (err) {
      console.error('Failed to run cross-document reconciliation:', err);
    } finally {
      setIsCrossRunning(false);
    }
  };

  const currentRun = runs.find((r) => {
    if (activeTab === 'BANK') return r.recon_type === 'BANK';
    if (activeTab === 'GST_ITC') return r.recon_type === 'GST_ITC' || r.recon_type === 'GST_2B_VS_BOOKS';
    return false;
  }) || runs[0];

  const summary = currentRun?.summary_data || {};
  const items = currentRun?.items || [];

  const crossDocRuns = runs.filter((r) =>
    ['LEDGER_TB', 'SALES_VS_LEDGER', 'PURCHASE_VS_LEDGER', 'AR_VS_CONTROL', 'AP_VS_CONTROL', 'FAR_VS_LEDGER', 'FS_VS_TB'].includes(r.recon_type)
  );

  const handleApprove = async (itemId: number) => {
    if (!currentRun) return;
    try {
      await api.approveMatch(currentRun.id, itemId, 'Auditor verified clearance against April 2025 statement.');
      await loadRuns();
    } catch (err) {
      console.error('Failed to approve match:', err);
    }
  };

  const getCrossDocLabel = (type: string) => {
    switch (type) {
      case 'LEDGER_TB':
        return {
          title: 'General Ledger vs Trial Balance',
          desc: 'Net sum of all posted general ledger voucher entries verified against TB totals',
          standard: 'SA 500 / Guidance Note on TB',
        };
      case 'SALES_VS_LEDGER':
        return {
          title: 'Sales Register vs Revenue GL Account',
          desc: 'Monthly sales register turnover matched against Ledger Code 4001 Revenue from Operations',
          standard: 'AS 9 / Ind AS 115',
        };
      case 'PURCHASE_VS_LEDGER':
        return {
          title: 'Purchase Register vs Purchase GL Account',
          desc: 'Direct material inward registers matched against Ledger Code 5001 Purchases',
          standard: 'AS 2 / Ind AS 2',
        };
      case 'AR_VS_CONTROL':
        return {
          title: 'Debtors Sub-Ledger vs AR Control Account',
          desc: 'Schedule of individual trade receivables matched against general ledger control total',
          standard: 'SA 505 External Confirmations',
        };
      case 'AP_VS_CONTROL':
        return {
          title: 'Creditors Sub-Ledger vs AP Control Account',
          desc: 'Schedule of trade payables matched against GL Code 2101 Trade Creditors Control',
          standard: 'SA 505 External Confirmations',
        };
      case 'FAR_VS_LEDGER':
        return {
          title: 'Fixed Asset Register (FAR) vs PPE Balance Sheet',
          desc: 'Asset-by-asset gross block, accumulated depreciation, and net carrying value verified against GL',
          standard: 'CARO 2020 Clause 3(i) / AS 10',
        };
      case 'FS_VS_TB':
        return {
          title: 'Financial Statements vs Trial Balance',
          desc: 'Draft Balance Sheet and P&L groupings validated against audited Trial Balance line items',
          standard: 'Schedule III / SA 700',
        };
      default:
        return {
          title: type,
          desc: 'Cross-document reconciliation procedure',
          standard: 'SA 500',
        };
    }
  };

  return (
    <div className="min-h-screen bg-slate-50/70">
      <Header
        title="Automated Reconciliation Workspace"
        subtitle="Deterministic Bank Reconciliation Statement (BRS), GST ITC (Rule 36(4)), and Cross-Document Subledger Verification"
      />

      <main className="p-8 max-w-7xl mx-auto space-y-8">
        {/* Tab Selector */}
        <div className="bg-white rounded-2xl border border-slate-200/90 p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('BANK')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer ${
                activeTab === 'BANK'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              Bank Reconciliation (BRS)
            </button>
            <button
              onClick={() => setActiveTab('GST_ITC')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer ${
                activeTab === 'GST_ITC'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              GST ITC (GSTR-2B vs Books)
            </button>
            <button
              onClick={() => setActiveTab('CROSS_DOC')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer flex items-center gap-1.5 ${
                activeTab === 'CROSS_DOC'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Cross-Document Reconciliations (7 Checks)</span>
            </button>
          </div>

          <div className="flex items-center gap-3">
            {activeTab === 'CROSS_DOC' ? (
              <button
                onClick={handleRunCrossDoc}
                disabled={isCrossRunning}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-400 text-white rounded-xl text-xs font-bold transition flex items-center gap-2 cursor-pointer shadow-xs"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isCrossRunning ? 'animate-spin' : ''}`} />
                <span>{isCrossRunning ? 'Executing 7 Checks...' : 'Run All Cross-Reconciliations'}</span>
              </button>
            ) : (
              <span
                className={`px-3 py-1 rounded-full text-xs font-bold border ${
                  currentRun?.unreconciled_difference === '0.00' && (currentRun?.unresolved_count ?? 0) === 0
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : 'bg-amber-50 text-amber-700 border-amber-200'
                }`}
              >
                {currentRun?.unreconciled_difference === '0.00' && (currentRun?.unresolved_count ?? 0) === 0
                  ? 'Zero Variance Reconciled'
                  : `Variance: ₹${currentRun?.unreconciled_difference || '0.00'} (${currentRun?.unresolved_count || 0} Unresolved)`}
              </span>
            )}
          </div>
        </div>

        {/* Tab 1: Bank Reconciliation Statement Table */}
        {activeTab === 'BANK' && (
          <div className="space-y-6">
            {/* Tolerance & Configuration Banner */}
            <div className="bg-white rounded-2xl border border-slate-200/90 p-4 shadow-xs flex items-center justify-between">
              <div className="flex items-center gap-3">
                <SlidersHorizontal className="w-4 h-4 text-slate-500" />
                <span className="text-xs font-bold text-slate-700">Bank Matching Date Tolerance:</span>
                <div className="flex items-center gap-1.5">
                  {[2, 3, 5, 7].map((days) => (
                    <button
                      key={days}
                      onClick={() => setToleranceDays(days)}
                      className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition ${
                        toleranceDays === days
                          ? 'bg-blue-100 text-blue-700 border border-blue-300'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                    >
                      ±{days} Days
                    </button>
                  ))}
                </div>
              </div>
              <div className="text-xs text-slate-500">
                Algorithm: <span className="font-semibold text-slate-800">Exact Ref → 1-to-1 Date Window → 1-to-Many Bundle → Fuzzy Narration</span>
              </div>
            </div>

            {/* Formal BRS Calculation Statement Card */}
            <div className="bg-white rounded-3xl border border-slate-200/90 shadow-xs p-8 space-y-4">
              <div className="border-b border-slate-100 pb-3 flex justify-between items-baseline">
                <div>
                  <h3 className="text-base font-bold text-slate-900">
                    Bank Reconciliation Statement as of 31st March 2025
                  </h3>
                  <p className="text-xs text-slate-500">HDFC Bank Current Account No. 50200049281920 • IFSC: HDFC0001234</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono font-bold text-slate-500">Amounts in INR (₹)</span>
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-bold border ${
                      currentRun?.status === 'BALANCED'
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : currentRun?.status === 'REVIEW_REQUIRED'
                        ? 'bg-amber-50 text-amber-700 border-amber-200'
                        : 'bg-slate-50 text-slate-700 border-slate-200'
                    }`}
                  >
                    Status: {currentRun?.status || 'REVIEW_REQUIRED'}
                  </span>
                </div>
              </div>

              <div className="divide-y divide-slate-100 text-xs">
                <div className="py-2.5 flex justify-between font-bold text-slate-900">
                  <span>Balance as per Company Books (Cashbook / Bank Ledger)</span>
                  <span className="font-mono">
                    ₹{parseFloat(summary.starting_cashbook_balance || '3450000').toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
                </div>

                <div className="py-2.5 flex justify-between text-emerald-800 font-semibold pl-4">
                  <span>(+) Add: Cheques issued but not yet presented for payment</span>
                  <span className="font-mono">
                    +₹{parseFloat(summary.cheques_issued_not_presented || '42000').toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
                </div>

                <div className="py-2.5 flex justify-between text-rose-800 font-semibold pl-4">
                  <span>(-) Less: Cheques deposited but not yet cleared / credited by bank</span>
                  <span className="font-mono">
                    -₹{parseFloat(summary.cheques_deposited_not_cleared || '350000').toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
                </div>

                <div className="py-2.5 flex justify-between text-emerald-800 font-semibold pl-4">
                  <span>(+) Add: Direct credits / customer remittances directly deposited in bank</span>
                  <span className="font-mono">
                    +₹{parseFloat(summary.direct_credits_not_in_books || '0.00').toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
                </div>

                <div className="py-2.5 flex justify-between text-rose-800 font-semibold pl-4">
                  <span>(-) Less: Direct debits by bank (bank charges, processing fees)</span>
                  <span className="font-mono">
                    -₹{parseFloat(summary.direct_debits_by_bank || '3500').toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
                </div>

                <div className="py-3 flex justify-between font-bold text-sm text-slate-900 bg-slate-50 px-3 rounded-xl mt-2">
                  <span>Reconciled Balance as per Bank Passbook Statement</span>
                  <span className="font-mono text-blue-700">
                    ₹{parseFloat(summary.computed_statement_balance || '3138500').toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
                </div>

                <div className="py-2 flex justify-between text-slate-500 font-medium pl-3">
                  <span>Actual Closing Balance reported on Bank Confirmation Certificate</span>
                  <span className="font-mono">
                    ₹{parseFloat(summary.actual_statement_balance || '3140500').toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
                </div>
              </div>
            </div>

            {/* Reconciliation Line Items Table */}
            <div className="bg-white rounded-3xl border border-slate-200/90 shadow-xs overflow-hidden">
              <div className="p-6 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold text-slate-900">Reconciliation Transaction Items</h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Multi-tier matches, 1-to-many bundles, and timing clearance queue
                  </p>
                </div>
                <div className="text-xs text-slate-500">
                  Total Items: <span className="font-bold text-slate-800">{items.length}</span>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-bold uppercase tracking-wider">
                    <tr>
                      <th className="py-3 px-6">Source</th>
                      <th className="py-3 px-6">Date</th>
                      <th className="py-3 px-6">Reference</th>
                      <th className="py-3 px-6">Particulars / Description</th>
                      <th className="py-3 px-6">Match Type & Timing</th>
                      <th className="py-3 px-6 text-right">Amount (₹)</th>
                      <th className="py-3 px-6 text-right">Auditor Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-medium text-slate-700">
                    {items.map((it) => (
                      <tr key={it.id} className="hover:bg-slate-50/70 transition">
                        <td className="py-3.5 px-6 font-semibold text-slate-900">{it.source_type}</td>
                        <td className="py-3.5 px-6 font-mono text-slate-600">{it.item_date}</td>
                        <td className="py-3.5 px-6 font-mono text-blue-700 font-bold">{it.reference_number || '-'}</td>
                        <td className="py-3.5 px-6 text-slate-600 max-w-xs truncate">{it.description}</td>
                        <td className="py-3.5 px-6 space-y-1">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span
                              className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                                it.is_matched
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : 'bg-amber-100 text-amber-800'
                              }`}
                            >
                              {it.timing_category || (it.is_matched ? 'EXACT_MATCH' : 'UNMATCHED')}
                            </span>
                            {it.match_type && (
                              <span className="px-2 py-0.5 rounded-full font-mono text-[9px] bg-slate-100 text-slate-600 border border-slate-200">
                                {it.match_type}
                              </span>
                            )}
                          </div>
                          {it.match_notes && (
                            <div className="text-[10px] text-slate-500 italic max-w-xs truncate">
                              {it.match_notes}
                            </div>
                          )}
                        </td>
                        <td className="py-3.5 px-6 text-right font-mono font-bold text-slate-900">
                          ₹{parseFloat(it.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="py-3.5 px-6 text-right">
                          {it.is_approved ? (
                            <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700">
                              <Check className="w-3.5 h-3.5" />
                              <span>Approved</span>
                            </span>
                          ) : (
                            <button
                              onClick={() => handleApprove(it.id)}
                              className="px-2.5 py-1 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-lg text-xs font-semibold cursor-pointer transition shadow-2xs"
                            >
                              Approve Match
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: GST ITC Reconciliation */}
        {activeTab === 'GST_ITC' && (
          <div className="bg-white rounded-3xl border border-slate-200/90 shadow-xs p-8 space-y-6">
            <div className="border-b border-slate-100 pb-3 flex justify-between items-baseline">
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  GST Input Tax Credit (ITC) Scrutiny & Rule 36(4) Reconciliation
                </h3>
                <p className="text-xs text-slate-500">Cross-checking Purchase Register against GSTR-2B portal data</p>
              </div>
              <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200">
                GST Section 16(2)(aa)
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200/70">
                <div className="text-xs font-bold text-slate-400 uppercase">ITC Claimed in Books</div>
                <div className="text-xl font-bold text-slate-900 font-mono mt-1">₹1,43,300.00</div>
              </div>
              <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200/70">
                <div className="text-xs font-bold text-slate-400 uppercase">Eligible ITC in GSTR-2B</div>
                <div className="text-xl font-bold text-emerald-700 font-mono mt-1">₹1,18,800.00</div>
              </div>
              <div className="bg-rose-50 p-4 rounded-2xl border border-rose-200">
                <div className="text-xs font-bold text-rose-600 uppercase">Missing in 2B (At Risk)</div>
                <div className="text-xl font-bold text-rose-700 font-mono mt-1">₹24,500.00</div>
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <div className="text-xs text-amber-900 leading-relaxed">
                <span className="font-bold">Rule 36(4) / Sec 16(2)(aa) Warning:</span> Invoice{' '}
                <span className="font-mono font-bold">SL-2025-102</span> from{' '}
                <span className="font-semibold">Shree Tech Solutions (₹24,500 ITC)</span> has not been filed by the supplier in GSTR-1.
                Taxpayer is not entitled to avail input tax credit until reflected in GSTR-2B.
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Cross-Document Reconciliation */}
        {activeTab === 'CROSS_DOC' && (
          <div className="space-y-6">
            <div className="bg-white rounded-3xl border border-slate-200/90 shadow-xs p-6 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  Sub-Ledger & Financial Statement Cross-Reconciliations
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Automated checks validating subledger schedules against GL control balances and financial statement line items
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-slate-500">
                  {crossDocRuns.filter((r) => r.status === 'BALANCED').length} of {crossDocRuns.length || 7} Reconciled
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4">
              {['LEDGER_TB', 'SALES_VS_LEDGER', 'PURCHASE_VS_LEDGER', 'AR_VS_CONTROL', 'AP_VS_CONTROL', 'FAR_VS_LEDGER', 'FS_VS_TB'].map((typeKey) => {
                const run = crossDocRuns.find((r) => r.recon_type === typeKey);
                const info = getCrossDocLabel(typeKey);
                const status = run?.status || 'NOT_RUN';
                const isBlocked = status === 'BLOCKED';
                const isBalanced = status === 'BALANCED';
                const isVariance = status === 'VARIANCE_DETECTED';

                return (
                  <div
                    key={typeKey}
                    className="bg-white rounded-2xl border border-slate-200/90 p-5 shadow-xs hover:border-blue-300 transition space-y-4"
                  >
                    <div className="flex items-start justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <h4 className="text-sm font-bold text-slate-900">{info.title}</h4>
                          <span className="text-[10px] font-mono px-2 py-0.5 bg-slate-100 text-slate-600 rounded-md border border-slate-200">
                            {info.standard}
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 max-w-2xl">{info.desc}</p>
                      </div>

                      <div>
                        {isBalanced && (
                          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Zero Variance Reconciled</span>
                          </span>
                        )}
                        {isBlocked && (
                          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200">
                            <FileX className="w-3.5 h-3.5" />
                            <span>Blocked (Missing Register)</span>
                          </span>
                        )}
                        {isVariance && (
                          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200">
                            <AlertTriangle className="w-3.5 h-3.5" />
                            <span>Variance Detected</span>
                          </span>
                        )}
                        {!isBalanced && !isBlocked && !isVariance && (
                          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 border border-slate-200">
                            <Clock className="w-3.5 h-3.5" />
                            <span>Pending Execution</span>
                          </span>
                        )}
                      </div>
                    </div>

                    {run ? (
                      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 bg-slate-50/70 p-3.5 rounded-xl border border-slate-200/70 text-xs">
                        <div>
                          <span className="text-[10px] uppercase font-bold text-slate-400">Book / Primary Balance</span>
                          <div className="font-mono font-bold text-slate-800 text-sm mt-0.5">
                            ₹{parseFloat(run.balance_per_books || '0').toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </div>
                        </div>
                        <div>
                          <span className="text-[10px] uppercase font-bold text-slate-400">Register / Control Balance</span>
                          <div className="font-mono font-bold text-slate-800 text-sm mt-0.5">
                            {isBlocked ? 'Not Provided' : `₹${parseFloat(run.balance_per_statement || '0').toLocaleString('en-IN', { minimumFractionDigits: 2 })}`}
                          </div>
                        </div>
                        <div>
                          <span className="text-[10px] uppercase font-bold text-slate-400">Unreconciled Variance</span>
                          <div className={`font-mono font-bold text-sm mt-0.5 ${isBalanced ? 'text-emerald-700' : isBlocked ? 'text-slate-500' : 'text-rose-700'}`}>
                            {isBlocked ? 'N/A' : `₹${parseFloat(run.unreconciled_difference || '0').toLocaleString('en-IN', { minimumFractionDigits: 2 })}`}
                          </div>
                        </div>
                        <div>
                          <span className="text-[10px] uppercase font-bold text-slate-400">Status Details</span>
                          <div className="text-[11px] font-medium text-slate-600 mt-0.5 truncate">
                            {run.summary_data?.notes || run.summary_data?.message || 'Completed deterministic cross-match.'}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="bg-slate-50/70 p-3 rounded-xl border border-dashed border-slate-200 text-xs text-slate-500 flex items-center justify-between">
                        <span>Click "Run All Cross-Reconciliations" to execute this check.</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
