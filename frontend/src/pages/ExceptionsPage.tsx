import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Filter,
  Search,
  MessageSquare,
  FileCheck,
  Check,
  CheckCheck,
  Loader2,
  FileSearch,
  X,
  History,
  ShieldAlert,
  Hash,
  Database,
} from 'lucide-react';
import { Header } from '../components/Header';
import { api } from '../services/api';
import { ExceptionItem } from '../types';

export const ExceptionsPage: React.FC = () => {
  const [exceptions, setExceptions] = useState<ExceptionItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedSeverity, setSelectedSeverity] = useState('ALL');
  const [selectedStatus, setSelectedStatus] = useState('ALL');
  const [resolvingId, setResolvingId] = useState<number | null>(null);
  const [targetStatus, setTargetStatus] = useState<string>('RESOLVED');
  const [resolutionNotes, setResolutionNotes] = useState('');
  const [isResolvingAll, setIsResolvingAll] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  
  // Evidence modal state
  const [evidenceData, setEvidenceData] = useState<any | null>(null);
  const [isEvidenceLoading, setIsEvidenceLoading] = useState(false);

  const loadExceptions = async () => {
    setIsLoading(true);
    try {
      const data = await api.getExceptions();
      setExceptions(data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadExceptions();
  }, []);

  const handleOpenEvidence = async (id: number) => {
    setIsEvidenceLoading(true);
    try {
      const data = await api.getExceptionEvidence(id);
      setEvidenceData(data);
    } catch (err) {
      console.error('Failed to load exception evidence:', err);
    } finally {
      setIsEvidenceLoading(false);
    }
  };

  const handleResolve = async (id: number) => {
    try {
      await api.resolveException(
        id,
        targetStatus,
        resolutionNotes
      );
      setResolvingId(null);
      setResolutionNotes('');
      setActionMessage(`Exception #${id} updated to ${targetStatus}.`);
      setTimeout(() => setActionMessage(null), 4000);
      await loadExceptions();
    } catch (err) {
      console.error(err);
    }
  };

  const handleQuickSolve = async (id: number) => {
    try {
      await api.resolveException(id, 'RESOLVED', '');
      setActionMessage(`Exception #${id} resolved with statutory audit trail.`);
      setTimeout(() => setActionMessage(null), 4000);
      await loadExceptions();
    } catch (err) {
      console.error('Failed to quick solve exception:', err);
    }
  };

  const handleSolveAll = async () => {
    setIsResolvingAll(true);
    try {
      // Find open items in current filtered set
      const openFiltered = filtered.filter((e) => e.status !== 'RESOLVED');
      const targetIds = openFiltered.length > 0 ? openFiltered.map((e) => e.id) : undefined;

      const res = await api.resolveAllExceptions({
        status: 'RESOLVED',
        ids: targetIds,
        severity: selectedSeverity !== 'ALL' ? selectedSeverity : undefined,
      });

      setActionMessage(res.message || 'All exceptions marked as RESOLVED with statutory audit evidence.');
      setTimeout(() => setActionMessage(null), 5000);
      await loadExceptions();
    } catch (err) {
      console.error('Failed to solve all exceptions:', err);
      setActionMessage('Failed to solve all exceptions. Please try again.');
      setTimeout(() => setActionMessage(null), 5000);
    } finally {
      setIsResolvingAll(false);
    }
  };

  const filtered = exceptions.filter((e) => {
    if (selectedSeverity !== 'ALL' && e.severity !== selectedSeverity) return false;
    if (selectedStatus !== 'ALL' && e.status !== selectedStatus) return false;
    return true;
  });

  const openCount = exceptions.filter((e) => e.status !== 'RESOLVED').length;
  const filteredOpenCount = filtered.filter((e) => e.status !== 'RESOLVED').length;

  return (
    <div className="min-h-screen bg-slate-50/70">
      <Header
        title="Exceptions & Risk Management Center"
        subtitle="Centralized tracking of statutory non-compliance, material audit risks, and CA resolution trails"
      />

      <main className="p-8 max-w-7xl mx-auto space-y-6">
        {/* Banner Notification if an action was performed */}
        {actionMessage && (
          <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 px-4 py-3 rounded-2xl flex items-center justify-between text-xs font-semibold shadow-xs animate-in fade-in">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{actionMessage}</span>
            </div>
            <button
              onClick={() => setActionMessage(null)}
              className="text-emerald-500 hover:text-emerald-800 p-0.5 cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Filter & Action Bar */}
        <div className="bg-white rounded-2xl border border-slate-200/90 p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-5">
            <div className="flex items-center gap-3">
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1">
                <Filter className="w-3.5 h-3.5" />
                <span>Severity:</span>
              </span>
              {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((s) => (
                <button
                  key={s}
                  onClick={() => setSelectedSeverity(s)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer ${
                    selectedSeverity === s
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-3">
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Status:</span>
              {['ALL', 'OPEN', 'IN_REVIEW', 'RESOLVED', 'ACCEPTED_RISK'].map((st) => (
                <button
                  key={st}
                  onClick={() => setSelectedStatus(st)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer ${
                    selectedStatus === st
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>

          {/* Quick Solve All Action */}
          <div className="flex items-center gap-3">
            <button
              onClick={handleSolveAll}
              disabled={isResolvingAll}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer flex items-center gap-2 shadow-xs ${
                openCount > 0
                  ? 'bg-emerald-600 hover:bg-emerald-700 text-white shadow-emerald-200'
                  : 'bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100'
              } disabled:opacity-60 disabled:cursor-not-allowed`}
              title="Click to solve all exceptions with standard ICAI / Ind AS statutory audit documentation"
            >
              {isResolvingAll ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Resolving All...</span>
                </>
              ) : (
                <>
                  <CheckCheck className="w-4 h-4" />
                  <span>
                    {filteredOpenCount > 0
                      ? `Solve All (${filteredOpenCount} Open)`
                      : openCount > 0
                      ? `Solve All (${openCount} Open)`
                      : 'Solve All (Re-verify)'}
                  </span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Exceptions Cards List */}
        <div className="space-y-4">
          {filtered.map((exc) => (
            <div
              key={exc.id}
              className="bg-white rounded-3xl border border-slate-200/90 p-6 shadow-xs hover:border-blue-300 transition duration-150 space-y-4"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className={`px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase ${
                        exc.severity === 'CRITICAL'
                          ? 'bg-rose-100 text-rose-800'
                          : exc.severity === 'HIGH'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-blue-100 text-blue-800'
                      }`}
                    >
                      {exc.severity}
                    </span>
                    {exc.rule_code && (
                      <span className="font-mono text-[10px] font-bold px-2 py-0.5 rounded-md bg-slate-900 text-white">
                        {exc.rule_code}
                      </span>
                    )}
                    <span className="text-xs font-semibold text-slate-400">
                      • {exc.category} • Source Ref: {exc.source_reference || 'Ledger'}
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-slate-900 mt-1.5">{exc.title}</h3>
                </div>

                <div className="text-right">
                  <div className="text-xs font-semibold text-slate-400">Amount Involved</div>
                  <div className="text-lg font-bold text-slate-900 font-mono">
                    ₹{parseFloat(exc.amount_involved).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </div>
                </div>
              </div>

              <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200/70 text-xs text-slate-700 leading-relaxed space-y-2">
                <div>
                  <span className="font-bold text-slate-900">Statutory Observation: </span>
                  {exc.explanation}
                </div>
                <div>
                  <span className="font-bold text-blue-700">Recommended Next Step: </span>
                  {exc.recommended_action}
                </div>
                {exc.resolution_notes && (
                  <div className="pt-2 border-t border-slate-200 text-emerald-800 font-medium">
                    <span className="font-bold">Latest CA Resolution Note: </span>
                    {exc.resolution_notes}
                  </div>
                )}
                {exc.resolution_history && exc.resolution_history.length > 0 && (
                  <div className="pt-2 border-t border-slate-200 space-y-1">
                    <span className="font-bold text-slate-600 flex items-center gap-1 text-[11px]">
                      <History className="w-3 h-3" />
                      <span>Resolution Audit Trail:</span>
                    </span>
                    {exc.resolution_history.map((h, idx) => (
                      <div key={idx} className="text-[11px] text-slate-500 font-mono pl-4">
                        • {new Date(h.timestamp).toLocaleDateString()} [{h.status}] - {h.notes} ({h.reviewer || 'Auditor'})
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Action Bar */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                <div className="flex items-center gap-2">
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-bold border ${
                      exc.status === 'RESOLVED'
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : exc.status === 'IN_REVIEW'
                        ? 'bg-blue-50 text-blue-700 border-blue-200'
                        : exc.status === 'ACCEPTED_RISK'
                        ? 'bg-purple-50 text-purple-700 border-purple-200'
                        : 'bg-amber-50 text-amber-700 border-amber-200'
                    }`}
                  >
                    {exc.status === 'RESOLVED'
                      ? 'Resolved & Closed'
                      : exc.status === 'IN_REVIEW'
                      ? 'In Review'
                      : exc.status === 'ACCEPTED_RISK'
                      ? 'Accepted Risk'
                      : 'Open - Action Required'}
                  </span>

                  <button
                    onClick={() => handleOpenEvidence(exc.id)}
                    className="px-3 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-full text-xs font-semibold cursor-pointer transition flex items-center gap-1.5"
                  >
                    <FileSearch className="w-3.5 h-3.5 text-blue-600" />
                    <span>Inspect Evidence</span>
                  </button>
                </div>

                <div className="flex items-center gap-2">
                  {exc.status !== 'RESOLVED' && (
                    <button
                      onClick={() => handleQuickSolve(exc.id)}
                      className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold cursor-pointer transition flex items-center gap-1.5 shadow-2xs"
                      title="Quick Solve with standard statutory audit resolution"
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>Quick Solve</span>
                    </button>
                  )}

                  {resolvingId === exc.id ? (
                    <div className="flex flex-wrap items-center gap-2 bg-slate-50 p-2 rounded-2xl border border-slate-200">
                      <select
                        value={targetStatus}
                        onChange={(e) => setTargetStatus(e.target.value)}
                        className="px-2.5 py-1.5 rounded-xl border border-slate-200 text-xs font-semibold bg-white outline-none"
                      >
                        <option value="RESOLVED">Mark Resolved</option>
                        <option value="IN_REVIEW">Mark In Review</option>
                        <option value="EVIDENCE_REQUESTED">Evidence Requested</option>
                        <option value="ACCEPTED_RISK">Accepted Risk</option>
                      </select>
                      <input
                        type="text"
                        value={resolutionNotes}
                        onChange={(e) => setResolutionNotes(e.target.value)}
                        placeholder="Enter professional justification..."
                        className="px-3 py-1.5 rounded-xl border border-slate-200 text-xs font-medium outline-none focus:ring-1 focus:ring-blue-600 w-64 bg-white"
                      />
                      <button
                        onClick={() => handleResolve(exc.id)}
                        className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold cursor-pointer transition flex items-center gap-1 shadow-2xs"
                      >
                        <Check className="w-3.5 h-3.5" />
                        <span>Save</span>
                      </button>
                      <button
                        onClick={() => setResolvingId(null)}
                        className="px-2 py-1.5 text-xs text-slate-500 hover:text-slate-800 cursor-pointer"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => {
                        setResolvingId(exc.id);
                        setTargetStatus('RESOLVED');
                      }}
                      className="px-3.5 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-xl text-xs font-bold cursor-pointer transition"
                    >
                      Update Resolution
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}

          {filtered.length === 0 && (
            <div className="bg-white rounded-3xl p-12 text-center text-slate-400 italic border border-slate-200/90">
              No exceptions found matching the selected criteria.
            </div>
          )}
        </div>
      </main>

      {/* Evidence Traceability Inspection Modal */}
      {evidenceData && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in">
          <div className="bg-white rounded-3xl max-w-2xl w-full p-6 shadow-2xl space-y-6 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-5 h-5 text-rose-600" />
                <h3 className="text-base font-bold text-slate-900">
                  Source Evidence Traceability (SA 230 / SA 500)
                </h3>
              </div>
              <button
                onClick={() => setEvidenceData(null)}
                className="p-1 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200 space-y-2">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-slate-900 text-sm">{evidenceData.title}</span>
                  <span className="font-mono px-2 py-0.5 rounded-md bg-slate-900 text-white font-bold text-[10px]">
                    {evidenceData.rule_code}
                  </span>
                </div>
                <div className="text-slate-600 font-mono">
                  Exception Ref: #{evidenceData.exception_id} • Target Location: {evidenceData.source_reference}
                </div>
              </div>

              {evidenceData.transaction && (
                <div className="space-y-2">
                  <h4 className="font-bold text-slate-900 flex items-center gap-1.5">
                    <Database className="w-4 h-4 text-blue-600" />
                    <span>Underlying General Ledger Transaction</span>
                  </h4>
                  <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200 grid grid-cols-2 gap-3 font-mono">
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase font-bold">Voucher No:</span>
                      <div className="font-bold text-slate-800">{evidenceData.transaction.voucher_number}</div>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase font-bold">Posting Date:</span>
                      <div className="font-bold text-slate-800">{evidenceData.transaction.date}</div>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase font-bold">Amount:</span>
                      <div className="font-bold text-slate-800">₹{evidenceData.transaction.amount}</div>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase font-bold">Ledger Account:</span>
                      <div className="font-bold text-slate-800">{evidenceData.transaction.ledger}</div>
                    </div>
                    <div className="col-span-2">
                      <span className="text-[10px] text-slate-400 uppercase font-bold">Narration:</span>
                      <div className="text-slate-700 font-sans">{evidenceData.transaction.narration}</div>
                    </div>
                  </div>
                </div>
              )}

              {evidenceData.document && (
                <div className="space-y-2">
                  <h4 className="font-bold text-slate-900 flex items-center gap-1.5">
                    <Hash className="w-4 h-4 text-emerald-600" />
                    <span>Source Document Cryptographic Hash</span>
                  </h4>
                  <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200 font-mono space-y-1">
                    <div className="text-slate-800 font-bold">{evidenceData.document.filename}</div>
                    <div className="text-[10px] text-slate-500 break-all">
                      SHA-256: {evidenceData.document.sha256_hash}
                    </div>
                  </div>
                </div>
              )}

              {evidenceData.extracted_record && (
                <div className="space-y-2">
                  <h4 className="font-bold text-slate-900">Extracted Ingestion Coordinates & Raw Values</h4>
                  <div className="bg-slate-900 text-slate-200 p-4 rounded-2xl font-mono text-[11px] overflow-x-auto space-y-2">
                    <div className="text-slate-400">
                      Coordinates: {evidenceData.extracted_record.source_location} (Row {evidenceData.extracted_record.row_index})
                    </div>
                    <pre className="text-slate-300">
                      {JSON.stringify(evidenceData.extracted_record.raw_data, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={() => setEvidenceData(null)}
                className="px-4 py-2 bg-slate-900 text-white rounded-xl text-xs font-bold hover:bg-slate-800 transition cursor-pointer"
              >
                Close Inspection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
