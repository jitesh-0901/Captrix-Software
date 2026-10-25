import React, { useEffect, useState } from 'react';
import {
  FileText,
  CheckCircle2,
  Clock,
  UserCheck,
  PlusCircle,
  FileSpreadsheet,
  ArrowRight,
  AlertTriangle,
  RotateCcw,
  ShieldCheck,
  History,
  X,
  Check,
  Filter,
} from 'lucide-react';
import { Header } from '../components/Header';
import { api } from '../services/api';
import { Workpaper, ProposedAdjustment } from '../types';

export const WorkpapersPage: React.FC = () => {
  const [workpapers, setWorkpapers] = useState<Workpaper[]>([]);
  const [adjustments, setAdjustments] = useState<ProposedAdjustment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRegenerating, setIsRegenerating] = useState(false);
  
  // Review Modal State
  const [activeModalWp, setActiveModalWp] = useState<Workpaper | null>(null);
  const [modalAction, setModalAction] = useState<'APPROVE' | 'REQUEST_CORRECTION' | 'VERIFY_EVIDENCE'>('APPROVE');
  const [modalReason, setModalReason] = useState('');
  const [modalNotes, setModalNotes] = useState('');
  const [verifyEvidenceCheck, setVerifyEvidenceCheck] = useState(true);
  const [sodOverrideCheck, setSodOverrideCheck] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Filter
  const [filterMode, setFilterMode] = useState<'ALL' | 'OUTSTANDING'>('ALL');

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [wps, ajes] = await Promise.all([api.getWorkpapers(), api.getAdjustments()]);
      setWorkpapers(wps || []);
      setAdjustments(ajes || []);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRegenerate = async () => {
    setIsRegenerating(true);
    try {
      await api.regenerateWorkpapers();
      await loadData();
    } catch (err) {
      console.error('Failed to regenerate workpapers:', err);
    } finally {
      setIsRegenerating(false);
    }
  };

  const handleOpenReviewModal = (wp: Workpaper, action: 'APPROVE' | 'REQUEST_CORRECTION' | 'VERIFY_EVIDENCE') => {
    setActiveModalWp(wp);
    setModalAction(action);
    setModalReason(action === 'APPROVE' ? 'Auditor verified audit evidence and confirms conclusion.' : '');
    setModalNotes('');
    setVerifyEvidenceCheck(wp.evidence_verified || true);
    setSodOverrideCheck(false);
    setModalError(null);
  };

  const handleSubmitReviewAction = async () => {
    if (!activeModalWp) return;
    setModalError(null);
    try {
      await api.reviewWorkpaper(activeModalWp.id, {
        action_type: modalAction,
        reason: modalReason,
        notes: modalNotes,
        verify_evidence: verifyEvidenceCheck,
        override_separation_of_duties: sodOverrideCheck,
        evidence_reference: activeModalWp.wp_reference
      });
      setActiveModalWp(null);
      await loadData();
    } catch (err: any) {
      setModalError(err.error || 'Review action failed.');
    }
  };

  const displayedWorkpapers = workpapers.filter((wp) => {
    if (filterMode === 'OUTSTANDING') {
      return ['READY_FOR_REVIEW', 'REVIEW_REQUIRED', 'RETURNED_FOR_CORRECTION', 'DRAFT'].includes(wp.status);
    }
    return true;
  });

  const outstandingCount = workpapers.filter((wp) =>
    ['READY_FOR_REVIEW', 'REVIEW_REQUIRED', 'RETURNED_FOR_CORRECTION'].includes(wp.status)
  ).length;

  return (
    <div className="min-h-screen bg-slate-50/70">
      <Header
        title="Audit Workpapers & Proposed Adjustments (SA 230)"
        subtitle="Standardized, evidence-linked working papers, separation-of-duties review queue & adjusting journal entries layer (AJE)"
      />

      <main className="p-8 max-w-7xl mx-auto space-y-8">
        {/* Governance & Policy Banner */}
        <div className="bg-white rounded-3xl border border-slate-200/90 p-6 shadow-xs flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">SA 220 & SQC 1 Quality Control Framework</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Separation of duties policy active: Preparers cannot approve their own workpapers without partner authorization.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setFilterMode('ALL')}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer ${
                filterMode === 'ALL' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              All Workpapers ({workpapers.length})
            </button>
            <button
              onClick={() => setFilterMode('OUTSTANDING')}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer flex items-center gap-1.5 ${
                filterMode === 'OUTSTANDING' ? 'bg-amber-500 text-slate-950 font-extrabold' : 'bg-amber-50 text-amber-800 border border-amber-200 hover:bg-amber-100'
              }`}
            >
              <span>Outstanding Review Queue</span>
              {outstandingCount > 0 && (
                <span className="bg-amber-700 text-white rounded-full px-1.5 py-0.2 text-[10px]">
                  {outstandingCount}
                </span>
              )}
            </button>
          </div>
        </div>

        {/* Workpapers Section */}
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-bold text-slate-900">Working Papers Index (SA 230)</h2>
              <p className="text-xs text-slate-500">
                Documentation of procedures executed, evidence tested, reviewer timestamps, and conclusions drawn
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleRegenerate}
                disabled={isRegenerating}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-400 text-white rounded-xl text-xs font-bold transition flex items-center gap-2 cursor-pointer shadow-xs"
              >
                <FileText className={`w-3.5 h-3.5 ${isRegenerating ? 'animate-spin' : ''}`} />
                <span>{isRegenerating ? 'Drafting from Evidence...' : 'Regenerate Workpapers (SA 230)'}</span>
              </button>
            </div>
          </div>

          <div className="space-y-4">
            {displayedWorkpapers.map((wp) => (
              <div
                key={wp.id}
                className="bg-white rounded-3xl border border-slate-200/90 p-6 shadow-xs space-y-4 hover:border-blue-300 transition duration-150"
              >
                <div className="flex items-start justify-between flex-wrap gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-blue-700 bg-blue-50 px-2.5 py-0.5 rounded-md border border-blue-200">
                        {wp.wp_reference}
                      </span>
                      <span className="text-xs font-semibold text-slate-400">• {wp.audit_area}</span>
                      {wp.evidence_verified && (
                        <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                          Evidence Verified
                        </span>
                      )}
                      <span className="text-[10px] font-mono text-slate-400">v{wp.version}</span>
                    </div>
                    <h3 className="text-base font-bold text-slate-900 mt-1">{wp.title}</h3>
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={`px-3 py-1 rounded-full text-xs font-bold border ${
                        wp.status === 'APPROVED'
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : wp.status === 'RETURNED_FOR_CORRECTION'
                          ? 'bg-rose-50 text-rose-700 border-rose-200'
                          : wp.status === 'REVIEWED'
                          ? 'bg-blue-50 text-blue-700 border-blue-200'
                          : 'bg-amber-50 text-amber-700 border-amber-200'
                      }`}
                    >
                      {wp.status}
                    </span>

                    {wp.status !== 'APPROVED' ? (
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => handleOpenReviewModal(wp, 'APPROVE')}
                          className="px-3 py-1.5 bg-emerald-700 hover:bg-emerald-600 text-white rounded-xl text-xs font-semibold cursor-pointer transition flex items-center gap-1 shadow-2xs"
                        >
                          <Check className="w-3.5 h-3.5" />
                          <span>Approve</span>
                        </button>
                        <button
                          onClick={() => handleOpenReviewModal(wp, 'REQUEST_CORRECTION')}
                          className="px-3 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-xl text-xs font-semibold cursor-pointer transition flex items-center gap-1"
                        >
                          <RotateCcw className="w-3.5 h-3.5" />
                          <span>Return</span>
                        </button>
                      </div>
                    ) : (
                      <span className="text-xs text-slate-400 font-medium italic">
                        Signed off by {wp.reviewed_by_name || wp.reviewer_name || 'Chartered Accountant'}
                      </span>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs bg-slate-50 p-4 rounded-2xl border border-slate-200/70 text-slate-700">
                  <div>
                    <div className="font-bold text-slate-900 mb-0.5">Audit Objective:</div>
                    <p className="text-slate-600">{wp.audit_objective}</p>
                    <div className="font-bold text-slate-900 mt-2 mb-0.5">Scope & Sampling:</div>
                    <p className="text-slate-600">{wp.scope_and_coverage}</p>
                  </div>
                  <div>
                    <div className="font-bold text-slate-900 mb-0.5">Testing Summary & Methodology:</div>
                    <p className="text-slate-600">{wp.results_summary}</p>
                    <div className="font-bold text-emerald-800 mt-2 mb-0.5">Proposed Conclusion:</div>
                    <p className="text-emerald-900 font-medium">{wp.proposed_conclusion}</p>
                  </div>
                </div>

                {wp.exceptions_noted && wp.exceptions_noted !== 'None' && wp.exceptions_noted !== 'Zero exceptions noted' && (
                  <div className="bg-amber-50/70 border border-amber-200 rounded-xl p-3 text-xs text-amber-900 flex items-start gap-2">
                    <span className="font-bold uppercase tracking-wider text-[10px] bg-amber-200/70 text-amber-800 px-1.5 py-0.5 rounded">
                      Exceptions Noted:
                    </span>
                    <span className="font-medium">{wp.exceptions_noted}</span>
                  </div>
                )}

                {wp.return_reason && (
                  <div className="bg-rose-50 border border-rose-200 rounded-xl p-3 text-xs text-rose-900 flex items-start gap-2">
                    <span className="font-bold uppercase tracking-wider text-[10px] bg-rose-200 text-rose-800 px-1.5 py-0.5 rounded">
                      Correction Requested:
                    </span>
                    <span className="font-medium">{wp.return_reason}</span>
                  </div>
                )}

                {/* Footer Attribution */}
                <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-100">
                  <div>
                    Preparer: <span className="font-semibold text-slate-600">{wp.preparer_name || 'Senior Auditor'}</span> | Reviewer: <span className="font-semibold text-slate-600">{wp.reviewer_name || 'Audit Manager'}</span>
                  </div>
                  <div>
                    {wp.approved_at ? `Approved at ${new Date(wp.approved_at).toLocaleString()}` : 'Awaiting Reviewer Sign-off'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Proposed Adjustments (AJE) Section */}
        <div className="bg-white rounded-3xl border border-slate-200/90 shadow-xs p-6 space-y-4">
          <div className="border-b border-slate-100 pb-3 flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Proposed Adjusting Journal Entries (AJE Layer)
              </h2>
              <p className="text-xs text-slate-500">
                Audit adjustments layer that preserves raw company ledgers while reflecting corrected balances
              </p>
            </div>
            <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200">
              Balanced Dr/Cr Layer
            </span>
          </div>

          <div className="space-y-4">
            {adjustments.map((aje) => (
              <div key={aje.id} className="border border-slate-200 rounded-2xl p-4 bg-slate-50/30 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded-md">
                      {aje.adjustment_number}
                    </span>
                    <h4 className="text-xs font-bold text-slate-900">{aje.title}</h4>
                  </div>
                  <span className="font-mono text-xs font-bold text-slate-700">
                    P&L Impact: ₹{aje.pnl_impact}
                  </span>
                </div>
                <p className="text-xs text-slate-600 italic">{aje.reason}</p>

                <div className="bg-white rounded-xl border border-slate-200 p-3 mt-2">
                  <div className="grid grid-cols-3 text-[11px] font-bold text-slate-400 uppercase border-b border-slate-100 pb-1 mb-1">
                    <span>Account</span>
                    <span className="text-right">Debit (₹)</span>
                    <span className="text-right">Credit (₹)</span>
                  </div>
                  {aje.journal_entries.map((entry, idx) => (
                    <div key={idx} className="grid grid-cols-3 text-xs text-slate-800 py-1 font-medium">
                      <span>{entry.account}</span>
                      <span className="text-right font-mono font-bold text-slate-900">
                        {parseFloat(entry.debit) > 0 ? `₹${entry.debit}` : '-'}
                      </span>
                      <span className="text-right font-mono font-bold text-slate-900">
                        {parseFloat(entry.credit) > 0 ? `₹${entry.credit}` : '-'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* REVIEW ACTION MODAL */}
        {activeModalWp && (
          <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-5 border border-slate-200">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div>
                  <span className="text-[10px] font-mono font-bold text-blue-600 uppercase bg-blue-50 px-2 py-0.5 rounded">
                    {activeModalWp.wp_reference}
                  </span>
                  <h3 className="text-base font-bold text-slate-900 mt-1">
                    {modalAction === 'APPROVE' ? 'Approve Audit Workpaper' : 'Return Workpaper for Correction'}
                  </h3>
                </div>
                <button
                  onClick={() => setActiveModalWp(null)}
                  className="w-8 h-8 rounded-full hover:bg-slate-100 flex items-center justify-center text-slate-400 cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {modalError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs font-semibold text-rose-800 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                  <span>{modalError}</span>
                </div>
              )}

              <div className="space-y-4 text-xs">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">
                    {modalAction === 'APPROVE' ? 'Auditor Approval Rationale:' : 'Reason for Return:'}
                  </label>
                  <textarea
                    rows={3}
                    value={modalReason}
                    onChange={(e) => setModalReason(e.target.value)}
                    placeholder="Enter written justification or required correction details..."
                    className="w-full p-3 rounded-xl border border-slate-300 focus:outline-blue-500 text-xs text-slate-800"
                  />
                </div>

                {modalAction === 'APPROVE' && (
                  <div className="space-y-2 p-3 bg-slate-50 rounded-xl border border-slate-200">
                    <label className="flex items-center gap-2 cursor-pointer font-medium text-slate-700">
                      <input
                        type="checkbox"
                        checked={verifyEvidenceCheck}
                        onChange={(e) => setVerifyEvidenceCheck(e.target.checked)}
                        className="rounded border-slate-300 text-blue-600"
                      />
                      <span>Verify underlying documentary evidence & voucher references</span>
                    </label>

                    <label className="flex items-center gap-2 cursor-pointer font-medium text-slate-700">
                      <input
                        type="checkbox"
                        checked={sodOverrideCheck}
                        onChange={(e) => setSodOverrideCheck(e.target.checked)}
                        className="rounded border-slate-300 text-blue-600"
                      />
                      <span className="text-[11px] text-slate-500">
                        Sole-practitioner / Partner override (Separation of Duties exception)
                      </span>
                    </label>
                  </div>
                )}
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  onClick={() => setActiveModalWp(null)}
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-semibold cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSubmitReviewAction}
                  className={`px-5 py-2 text-white rounded-xl text-xs font-bold cursor-pointer transition shadow-xs ${
                    modalAction === 'APPROVE' ? 'bg-emerald-700 hover:bg-emerald-600' : 'bg-rose-600 hover:bg-rose-500'
                  }`}
                >
                  {modalAction === 'APPROVE' ? 'Confirm Partner Approval' : 'Send Correction Request'}
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
