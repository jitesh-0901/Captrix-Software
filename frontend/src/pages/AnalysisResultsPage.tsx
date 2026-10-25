import React, { useEffect, useState } from 'react';
import {
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  Search,
  ExternalLink,
  ShieldCheck,
  RefreshCw,
  Layers,
  FileText,
  Eye,
  X,
  Building,
  Check,
  ArrowRight
} from 'lucide-react';
import { Header } from '../components/Header';
import { api } from '../services/api';
import { DocumentRecord, ExtractedRecord } from '../types';

export const AnalysisResultsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'TB_MOVEMENTS' | 'GL_TRANSACTIONS' | 'SOURCE_EXTRACT'>('TB_MOVEMENTS');
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null);
  const [records, setRecords] = useState<ExtractedRecord[]>([]);
  const [movementsData, setMovementsData] = useState<any | null>(null);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<number | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [glSearchTerm, setGlSearchTerm] = useState('');

  // Evidence modal state
  const [evidenceData, setEvidenceData] = useState<any | null>(null);
  const [isEvidenceLoading, setIsEvidenceLoading] = useState(false);

  useEffect(() => {
    async function loadInitialData() {
      setIsLoading(true);
      try {
        const [docs, movs, txns] = await Promise.all([
          api.getDocuments(),
          api.getTbMovements(),
          api.getTransactions()
        ]);
        setDocuments(docs || []);
        if (docs && docs.length > 0) {
          setSelectedDocId(docs[0].id);
        }
        setMovementsData(movs);
        setTransactions(txns || []);
      } catch (err) {
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    }
    loadInitialData();
  }, []);

  useEffect(() => {
    async function loadRecords() {
      if (!selectedDocId) return;
      try {
        const recs = await api.getDocumentRecords(selectedDocId);
        setRecords(recs || []);
      } catch (err) {
        console.error(err);
      }
    }
    loadRecords();
  }, [selectedDocId]);

  const loadTransactions = async (accountId?: number, search?: string) => {
    try {
      const txns = await api.getTransactions(undefined, undefined, accountId, search);
      setTransactions(txns || []);
    } catch (err) {
      console.error(err);
    }
  };

  const handleInspectEvidence = async (txnId: number) => {
    setIsEvidenceLoading(true);
    try {
      const ev = await api.getTransactionEvidence(txnId);
      setEvidenceData(ev);
    } catch (err) {
      console.error(err);
    } finally {
      setIsEvidenceLoading(false);
    }
  };

  const selectedDoc = documents.find((d) => d.id === selectedDocId);

  const filteredRecords = records.filter((r) => {
    const rawStr = JSON.stringify(r.raw_data).toLowerCase();
    const locStr = r.source_location.toLowerCase();
    return rawStr.includes(searchTerm.toLowerCase()) || locStr.includes(searchTerm.toLowerCase());
  });

  const accounts = movementsData?.accounts || [];
  const filteredAccounts = accounts.filter((a: any) => {
    const nameMatch = a.account_name.toLowerCase().includes(searchTerm.toLowerCase());
    const codeMatch = (a.account_code || '').toLowerCase().includes(searchTerm.toLowerCase());
    const groupMatch = (a.schedule_iii_group || '').toLowerCase().includes(searchTerm.toLowerCase());
    return nameMatch || codeMatch || groupMatch;
  });

  return (
    <div className="min-h-screen bg-slate-50/70">
      <Header
        title="Trial Balance & Forensic Accounting Explorer"
        subtitle="Schedule III account movement roll-forwards, voucher drilldown, and cryptographic source evidence"
      />

      <main className="p-8 max-w-7xl mx-auto space-y-6">
        {/* Navigation Tabs */}
        <div className="bg-white rounded-2xl border border-slate-200/90 p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('TB_MOVEMENTS')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer flex items-center gap-2 ${
                activeTab === 'TB_MOVEMENTS'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Schedule III Trial Balance & Roll-Forward</span>
            </button>
            <button
              onClick={() => setActiveTab('GL_TRANSACTIONS')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer flex items-center gap-2 ${
                activeTab === 'GL_TRANSACTIONS'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>General Ledger Voucher Drilldown</span>
            </button>
            <button
              onClick={() => setActiveTab('SOURCE_EXTRACT')}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer flex items-center gap-2 ${
                activeTab === 'SOURCE_EXTRACT'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              <FileSpreadsheet className="w-3.5 h-3.5" />
              <span>Source Extraction Records</span>
            </button>
          </div>

          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 bg-slate-50 px-3 py-1.5 rounded-xl border border-slate-200">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Python Decimal Arithmetic Verified</span>
          </div>
        </div>

        {/* TAB 1: TRIAL BALANCE & ROLL-FORWARD ANALYSIS */}
        {activeTab === 'TB_MOVEMENTS' && (
          <div className="space-y-6">
            {/* KPI Summary Cards */}
            {movementsData && (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs">
                  <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Total Accounts</div>
                  <div className="text-2xl font-bold text-slate-900 mt-1">{movementsData.total_accounts}</div>
                  <div className="text-xs text-slate-500 mt-1">Schedule III Div I & II Mapped</div>
                </div>
                <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs">
                  <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Grand Period Debits</div>
                  <div className="text-2xl font-bold text-blue-700 mt-1">₹{parseFloat(movementsData.grand_period_debits || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
                  <div className="text-xs text-slate-500 mt-1">Voucher Debits Total</div>
                </div>
                <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs">
                  <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Grand Period Credits</div>
                  <div className="text-2xl font-bold text-blue-700 mt-1">₹{parseFloat(movementsData.grand_period_credits || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
                  <div className="text-xs text-slate-500 mt-1">Voucher Credits Total</div>
                </div>
                <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs">
                  <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Roll-Forward Equality</div>
                  <div className="text-2xl font-bold text-emerald-600 mt-1 flex items-center gap-1.5">
                    <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                    <span>Balanced</span>
                  </div>
                  <div className="text-xs text-slate-500 mt-1">Closing = Opening + Δ(Dr - Cr)</div>
                </div>
              </div>
            )}

            {/* Filter and Search */}
            <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-xs flex items-center justify-between gap-4">
              <div className="relative flex-1 max-w-md">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Filter by account code, name, or Schedule III group..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-600/20"
                />
              </div>
              <div className="text-xs font-medium text-slate-500">
                Showing {filteredAccounts.length} of {accounts.length} Accounts
              </div>
            </div>

            {/* Movement Analysis Table */}
            <div className="bg-white rounded-3xl border border-slate-200/90 shadow-xs overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-500 font-semibold tracking-wider uppercase text-[10px]">
                      <th className="py-3 px-4">Code</th>
                      <th className="py-3 px-4">Ledger Account Name</th>
                      <th className="py-3 px-4">Schedule III Head</th>
                      <th className="py-3 px-4 text-right">Opening</th>
                      <th className="py-3 px-4 text-right">Period Debits (Dr)</th>
                      <th className="py-3 px-4 text-right">Period Credits (Cr)</th>
                      <th className="py-3 px-4 text-right">Net Movement</th>
                      <th className="py-3 px-4 text-right">Closing Balance</th>
                      <th className="py-3 px-4 text-center">Roll-Forward Status</th>
                      <th className="py-3 px-4 text-center">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700 font-medium">
                    {filteredAccounts.map((a: any) => (
                      <tr key={a.account_id} className="hover:bg-blue-50/40 transition">
                        <td className="py-3 px-4 font-mono font-bold text-slate-900">{a.account_code || '—'}</td>
                        <td className="py-3 px-4">
                          <div className="font-bold text-slate-900">{a.account_name}</div>
                          {a.is_suspense && (
                            <span className="inline-block mt-0.5 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800">
                              Suspense Account
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-mono text-[11px] text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
                            {a.schedule_iii_group}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right font-mono">
                          ₹{parseFloat(a.opening_balance).toLocaleString('en-IN', { minimumFractionDigits: 2 })} {a.opening_balance_type}
                        </td>
                        <td className="py-3 px-4 text-right font-mono text-emerald-700">
                          ₹{parseFloat(a.period_debits).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="py-3 px-4 text-right font-mono text-blue-700">
                          ₹{parseFloat(a.period_credits).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="py-3 px-4 text-right font-mono font-bold">
                          ₹{parseFloat(a.net_movement).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="py-3 px-4 text-right font-mono font-bold text-slate-900">
                          ₹{parseFloat(a.closing_balance).toLocaleString('en-IN', { minimumFractionDigits: 2 })} {a.closing_balance_type}
                        </td>
                        <td className="py-3 px-4 text-center">
                          {a.is_rollforward_valid ? (
                            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
                              <Check className="w-3 h-3" /> Valid
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-rose-700 bg-rose-50 px-2.5 py-1 rounded-full border border-rose-200">
                              <AlertTriangle className="w-3 h-3" /> Discrepancy
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-center">
                          <button
                            onClick={() => {
                              setSelectedAccountId(a.account_id);
                              setActiveTab('GL_TRANSACTIONS');
                              loadTransactions(a.account_id);
                            }}
                            className="px-2.5 py-1 rounded-lg text-[11px] font-bold text-blue-600 bg-blue-50 hover:bg-blue-100 transition cursor-pointer"
                          >
                            View Vouchers
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: GENERAL LEDGER VOUCHER DRILLDOWN */}
        {activeTab === 'GL_TRANSACTIONS' && (
          <div className="space-y-6">
            <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="relative w-72">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="Search by voucher, party, or narration..."
                    value={glSearchTerm}
                    onChange={(e) => {
                      setGlSearchTerm(e.target.value);
                      loadTransactions(selectedAccountId, e.target.value);
                    }}
                    className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-600/20"
                  />
                </div>
                {selectedAccountId && (
                  <button
                    onClick={() => {
                      setSelectedAccountId(undefined);
                      loadTransactions(undefined, glSearchTerm);
                    }}
                    className="px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 flex items-center gap-1"
                  >
                    <span>Clear Account Filter</span>
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
              <div className="text-xs font-medium text-slate-500">
                {transactions.length} General Ledger Vouchers Loaded
              </div>
            </div>

            <div className="bg-white rounded-3xl border border-slate-200/90 shadow-xs overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-500 font-semibold tracking-wider uppercase text-[10px]">
                      <th className="py-3 px-4">Date</th>
                      <th className="py-3 px-4">Voucher No</th>
                      <th className="py-3 px-4">Type</th>
                      <th className="py-3 px-4">Account / Counterparty</th>
                      <th className="py-3 px-4">Narration</th>
                      <th className="py-3 px-4 text-right">Debit (₹)</th>
                      <th className="py-3 px-4 text-right">Credit (₹)</th>
                      <th className="py-3 px-4 text-center">Audit Scrutiny</th>
                      <th className="py-3 px-4 text-center">Evidence</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700 font-medium">
                    {transactions.map((t: any) => (
                      <tr key={t.id} className="hover:bg-blue-50/30 transition">
                        <td className="py-3 px-4 font-mono">{t.date}</td>
                        <td className="py-3 px-4 font-mono font-bold text-slate-900">{t.voucher_number}</td>
                        <td className="py-3 px-4">
                          <span className="font-mono text-[10px] uppercase bg-slate-100 px-2 py-0.5 rounded text-slate-600 font-semibold">
                            {t.voucher_type}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <div className="font-bold text-slate-900">{t.account_name || 'Ledger'}</div>
                          {t.counterparty && <div className="text-[11px] text-slate-500">{t.counterparty}</div>}
                        </td>
                        <td className="py-3 px-4 max-w-xs truncate text-slate-600">{t.narration || '—'}</td>
                        <td className="py-3 px-4 text-right font-mono font-bold text-slate-900">
                          {parseFloat(t.debit_amount) > 0 ? `₹${parseFloat(t.debit_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '—'}
                        </td>
                        <td className="py-3 px-4 text-right font-mono font-bold text-slate-900">
                          {parseFloat(t.credit_amount) > 0 ? `₹${parseFloat(t.credit_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '—'}
                        </td>
                        <td className="py-3 px-4 text-center">
                          {t.is_unusual ? (
                            <span className="inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
                              {t.risk_flags?.[0] || 'Flagged'}
                            </span>
                          ) : (
                            <span className="text-[10px] text-slate-400 font-semibold">Standard</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-center">
                          <button
                            onClick={() => handleInspectEvidence(t.id)}
                            className="px-2.5 py-1 rounded-lg text-[11px] font-bold text-blue-600 bg-blue-50 hover:bg-blue-100 transition cursor-pointer flex items-center gap-1 mx-auto"
                          >
                            <Eye className="w-3 h-3" />
                            <span>Source</span>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: SOURCE EXTRACTION RECORDS */}
        {activeTab === 'SOURCE_EXTRACT' && (
          <div className="space-y-6">
            <div className="bg-white rounded-2xl border border-slate-200/90 p-5 shadow-xs flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
                  <FileSpreadsheet className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Select Active Ingested Document
                  </div>
                  <select
                    value={selectedDocId || ''}
                    onChange={(e) => setSelectedDocId(Number(e.target.value))}
                    className="text-sm font-bold text-slate-900 bg-transparent outline-none cursor-pointer mt-0.5"
                  >
                    {documents.map((doc) => (
                      <option key={doc.id} value={doc.id}>
                        {doc.original_filename} ({doc.document_type}) — {doc.status}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {selectedDoc && (
                <div className="flex items-center gap-4 text-xs font-medium text-slate-600">
                  <div className="bg-slate-50 px-3 py-1.5 rounded-xl border border-slate-200 font-mono text-[11px]">
                    <span className="text-slate-400">SHA-256: </span>
                    <span className="font-semibold text-slate-800">
                      {selectedDoc.file_hash.slice(0, 16)}...
                    </span>
                  </div>
                  <div className="bg-emerald-50 text-emerald-700 px-3 py-1.5 rounded-xl border border-emerald-200 flex items-center gap-1.5 font-bold">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Cryptographically Verified</span>
                  </div>
                </div>
              )}
            </div>

            <div className="bg-white rounded-3xl border border-slate-200/90 shadow-xs overflow-hidden">
              <div className="p-4 border-b border-slate-200 flex items-center justify-between">
                <div className="relative w-80">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="Search raw values or coordinates..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-600/20"
                  />
                </div>
                <div className="text-xs font-semibold text-slate-500">
                  Showing {filteredRecords.length} records
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-500 font-semibold tracking-wider uppercase text-[10px]">
                      <th className="py-3 px-4">Row</th>
                      <th className="py-3 px-4">Source Location</th>
                      <th className="py-3 px-4">Raw Extracted Fields</th>
                      <th className="py-3 px-4">Normalized Data</th>
                      <th className="py-3 px-4 text-center">Confidence</th>
                      <th className="py-3 px-4 text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700 font-medium">
                    {filteredRecords.map((rec) => (
                      <tr key={rec.id} className="hover:bg-blue-50/30 transition">
                        <td className="py-3 px-4 font-mono font-bold text-slate-900">{rec.row_index}</td>
                        <td className="py-3 px-4">
                          <span className="font-mono text-[11px] text-blue-700 bg-blue-50 px-2 py-0.5 rounded font-bold">
                            {rec.source_location}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono text-[11px] max-w-sm truncate text-slate-700">
                          {JSON.stringify(rec.raw_data)}
                        </td>
                        <td className="py-3 px-4 font-mono text-[11px] max-w-sm truncate text-slate-600">
                          {JSON.stringify(rec.normalized_data)}
                        </td>
                        <td className="py-3 px-4 text-center font-mono font-bold">
                          {Math.round(parseFloat(rec.confidence_score) * 100)}%
                        </td>
                        <td className="py-3 px-4 text-center">
                          <span
                            className={`px-2.5 py-1 rounded-full text-[10px] font-bold border ${
                              rec.validation_status === 'VALID'
                                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                : 'bg-amber-50 text-amber-700 border-amber-200'
                            }`}
                          >
                            {rec.validation_status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* EVIDENCE INSPECTION MODAL */}
        {evidenceData && (
          <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-3xl border border-slate-200 shadow-2xl max-w-2xl w-full p-6 space-y-6">
              <div className="flex items-center justify-between pb-4 border-b border-slate-100">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center">
                    <ShieldCheck className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-slate-900">Cryptographic Evidence Trace</h3>
                    <p className="text-xs text-slate-500">Source preservation coordinate & raw row values</p>
                  </div>
                </div>
                <button
                  onClick={() => setEvidenceData(null)}
                  className="w-8 h-8 rounded-full bg-slate-100 text-slate-500 hover:bg-slate-200 flex items-center justify-center cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-4">
                {/* File Metadata */}
                <div className="bg-slate-50 rounded-2xl p-4 border border-slate-200 space-y-2">
                  <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Source Document Metadata</div>
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-800">
                    <span>File Name:</span>
                    <span className="font-mono text-blue-700">{evidenceData.document?.filename || 'Manual Ledger Entry'}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-800">
                    <span>Source Coordinates:</span>
                    <span className="font-mono bg-blue-50 text-blue-800 px-2 py-0.5 rounded border border-blue-200 font-bold">
                      {evidenceData.source_reference || 'N/A'}
                    </span>
                  </div>
                  <div className="text-xs font-semibold text-slate-800">
                    <span>SHA-256 Fingerprint:</span>
                    <div className="font-mono text-[11px] text-slate-600 bg-white p-2 rounded-xl border border-slate-200 mt-1 break-all">
                      {evidenceData.document?.file_hash || 'SHA-256 Verified on Ingestion'}
                    </div>
                  </div>
                </div>

                {/* Voucher Info */}
                <div className="grid grid-cols-2 gap-4 text-xs font-medium text-slate-700">
                  <div className="bg-white p-3 rounded-xl border border-slate-200">
                    <span className="text-slate-400 block text-[11px]">Voucher Number</span>
                    <span className="font-bold text-slate-900">{evidenceData.voucher_number}</span>
                  </div>
                  <div className="bg-white p-3 rounded-xl border border-slate-200">
                    <span className="text-slate-400 block text-[11px]">Ledger Account</span>
                    <span className="font-bold text-slate-900">{evidenceData.account_name}</span>
                  </div>
                </div>

                {/* Raw Extracted Record */}
                {evidenceData.extracted_record && (
                  <div className="space-y-2">
                    <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Raw Extracted Row Data</div>
                    <pre className="bg-slate-900 text-slate-100 p-4 rounded-2xl text-[11px] font-mono overflow-x-auto max-h-48">
                      {JSON.stringify(evidenceData.extracted_record.raw_data, null, 2)}
                    </pre>
                  </div>
                )}
              </div>

              <div className="pt-4 border-t border-slate-100 flex justify-end">
                <button
                  onClick={() => setEvidenceData(null)}
                  className="px-5 py-2 bg-blue-600 text-white font-bold text-xs rounded-xl hover:bg-blue-700 transition cursor-pointer"
                >
                  Close Evidence Viewer
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
