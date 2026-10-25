import React, { useEffect, useState } from 'react';
import {
  ShieldCheck,
  CheckCircle2,
  Clock,
  RotateCcw,
  AlertCircle,
  FileText,
  UserCheck,
  Filter,
  Check,
  X,
  ExternalLink,
  MessageSquare,
  AlertTriangle,
  ArrowRight,
} from 'lucide-react';
import { Header } from '../components/Header';
import { api } from '../services/api';
import { Workpaper } from '../types';

export const ReviewQueuePage: React.FC = () => {
  const [workpapers, setWorkpapers] = useState<Workpaper[]>([]);
  const [metrics, setMetrics] = useState({
    total: 0,
    ready_for_review: 0,
    returned_for_correction: 0,
    approved: 0,
    draft: 0,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [filterTab, setFilterTab] = useState<'ALL' | 'READY_FOR_REVIEW' | 'RETURNED_FOR_CORRECTION' | 'APPROVED' | 'DRAFT'>('READY_FOR_REVIEW');

  // Modal State
  const [activeWp, setActiveWp] = useState<Workpaper | null>(null);
  const [modalAction, setModalAction] = useState<'APPROVE' | 'REQUEST_CORRECTION' | 'VERIFY_EVIDENCE'>('APPROVE');
  const [modalReason, setModalReason] = useState('');
  const [modalNotes, setModalNotes] = useState('');
  const [verifyEvidenceCheck, setVerifyEvidenceCheck] = useState(true);
  const [sodOverrideCheck, setSodOverrideCheck] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const res = await api.getReviewQueue();
      if (res && res.metrics) {
        setMetrics(res.metrics);
        setWorkpapers(res.items || []);
      } else {
        const wps = await api.getWorkpapers();
        setWorkpapers(wps || []);
        const total = (wps || []).length;
        const ready = (wps || []).filter((w: Workpaper) => w.status === 'READY_FOR_REVIEW').length;
        const returned = (wps || []).filter((w: Workpaper) => w.status === 'RETURNED_FOR_CORRECTION').length;
        const approved = (wps || []).filter((w: Workpaper) => w.status === 'APPROVED').length;
        const draft = (wps || []).filter((w: Workpaper) => w.status === 'DRAFT').length;
        setMetrics({ total, ready_for_review: ready, returned_for_correction: returned, approved, draft });
      }
    } catch (err) {
      console.error('Failed to load review queue', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const openReviewModal = (wp: Workpaper, action: 'APPROVE' | 'REQUEST_CORRECTION' | 'VERIFY_EVIDENCE') => {
    setActiveWp(wp);
    setModalAction(action);
    setModalReason(
      action === 'APPROVE'
        ? 'Reviewed and approved in accordance with SA 230 audit documentation and SA 220 quality standards.'
        : ''
    );
    setModalNotes('');
    setVerifyEvidenceCheck(wp.evidence_verified || true);
    setSodOverrideCheck(false);
    setModalError(null);
  };

  const handleReviewSubmit = async () => {
    if (!activeWp) return;
    setIsSubmitting(true);
    setModalError(null);
    try {
      await api.performWorkpaperReviewAction(activeWp.id, modalAction, {
        notes: modalNotes,
        reason: modalReason,
        verify_evidence: verifyEvidenceCheck,
        override_separation_of_duties: sodOverrideCheck,
        evidence_reference: activeWp.wp_reference,
      });
      setActiveWp(null);
      await loadData();
    } catch (err: any) {
      setModalError(err.error || 'Failed to complete review action.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const filteredItems = workpapers.filter((wp) => {
    if (filterTab === 'ALL') return true;
    return wp.status === filterTab;
  });

  return (
    <div className="min-h-screen bg-slate-50/70">
      <Header
        title="Review Queue & Sign-Off Controls"
        subtitle="Separation-of-duties review queue under SA 220 (Quality Control) and SA 230 (Audit Documentation)"
      />

      <main className="p-8 max-w-7xl mx-auto space-y-8">
        {/* KPI Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          <div className="bg-white rounded-2xl border border-slate-200/90 p-5 shadow-xs">
            <div className="flex items-center justify-between text-slate-500">
              <span className="text-xs font-semibold uppercase tracking-wider">Total Workpapers</span>
              <div className="w-8 h-8 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center">
                <FileText className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-900">{metrics.total}</span>
              <span className="text-xs text-slate-500 font-medium">persisted schedules</span>
            </div>
          </div>

          <div
            onClick={() => setFilterTab('READY_FOR_REVIEW')}
            className={`bg-white rounded-2xl border p-5 shadow-xs cursor-pointer transition ${
              filterTab === 'READY_FOR_REVIEW' ? 'border-amber-400 ring-2 ring-amber-100' : 'border-slate-200/90 hover:border-amber-300'
            }`}
          >
            <div className="flex items-center justify-between text-amber-600">
              <span className="text-xs font-semibold uppercase tracking-wider">Ready for Review</span>
              <div className="w-8 h-8 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
                <Clock className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-amber-700">{metrics.ready_for_review}</span>
              <span className="text-xs text-amber-600 font-medium">pending sign-off</span>
            </div>
          </div>

          <div
            onClick={() => setFilterTab('RETURNED_FOR_CORRECTION')}
            className={`bg-white rounded-2xl border p-5 shadow-xs cursor-pointer transition ${
              filterTab === 'RETURNED_FOR_CORRECTION' ? 'border-rose-400 ring-2 ring-rose-100' : 'border-slate-200/90 hover:border-rose-300'
            }`}
          >
            <div className="flex items-center justify-between text-rose-600">
              <span className="text-xs font-semibold uppercase tracking-wider">Returned for Correction</span>
              <div className="w-8 h-8 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center">
                <RotateCcw className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-rose-700">{metrics.returned_for_correction}</span>
              <span className="text-xs text-rose-600 font-medium">action required</span>
            </div>
          </div>

          <div
            onClick={() => setFilterTab('APPROVED')}
            className={`bg-white rounded-2xl border p-5 shadow-xs cursor-pointer transition ${
              filterTab === 'APPROVED' ? 'border-emerald-400 ring-2 ring-emerald-100' : 'border-slate-200/90 hover:border-emerald-300'
            }`}
          >
            <div className="flex items-center justify-between text-emerald-600">
              <span className="text-xs font-semibold uppercase tracking-wider">Partner Approved</span>
              <div className="w-8 h-8 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
                <CheckCircle2 className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-emerald-700">{metrics.approved}</span>
              <span className="text-xs text-emerald-600 font-medium">SA 230 cleared</span>
            </div>
          </div>
        </div>

        {/* Filter Navigation Tabs */}
        <div className="flex items-center justify-between border-b border-slate-200 pb-3">
          <div className="flex items-center gap-2">
            {[
              { id: 'READY_FOR_REVIEW', label: 'Ready for Review', count: metrics.ready_for_review },
              { id: 'RETURNED_FOR_CORRECTION', label: 'Returned for Correction', count: metrics.returned_for_correction },
              { id: 'APPROVED', label: 'Approved', count: metrics.approved },
              { id: 'DRAFT', label: 'Draft', count: metrics.draft },
              { id: 'ALL', label: 'All Items', count: metrics.total },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setFilterTab(tab.id as any)}
                className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition cursor-pointer ${
                  filterTab === tab.id
                    ? 'bg-blue-600 text-white shadow-xs'
                    : 'bg-white text-slate-600 hover:text-slate-900 border border-slate-200/80 hover:bg-slate-50'
                }`}
              >
                <span>{tab.label}</span>
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                    filterTab === tab.id ? 'bg-blue-700 text-blue-100' : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {tab.count}
                </span>
              </button>
            ))}
          </div>

          <div className="text-xs text-slate-500 font-medium">
            Showing <strong className="text-slate-800">{filteredItems.length}</strong> workpapers
          </div>
        </div>

        {/* Workpapers Review List */}
        {isLoading ? (
          <div className="bg-white rounded-3xl border border-slate-200/90 p-12 text-center text-slate-400">
            <Clock className="w-8 h-8 animate-spin mx-auto text-blue-500 mb-3" />
            <p className="text-sm font-medium">Loading review queue items...</p>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="bg-white rounded-3xl border border-slate-200/90 p-12 text-center text-slate-400">
            <CheckCircle2 className="w-10 h-10 mx-auto text-emerald-500 mb-3" />
            <h3 className="text-base font-semibold text-slate-800">Review Queue Clear</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              No workpapers currently matching the selected filter ({filterTab}).
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredItems.map((wp) => (
              <div
                key={wp.id}
                className="bg-white rounded-2xl border border-slate-200/90 p-6 shadow-xs hover:border-slate-300 transition space-y-4"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className="px-2.5 py-1 rounded-lg bg-blue-50 text-blue-700 font-mono text-xs font-bold border border-blue-200/60">
                      {wp.wp_reference}
                    </span>
                    <div>
                      <h3 className="text-sm font-bold text-slate-900">{wp.title}</h3>
                      <p className="text-xs text-slate-500">{wp.audit_area}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {/* Status Pill */}
                    <span
                      className={`text-xs px-2.5 py-1 rounded-full font-semibold border ${
                        wp.status === 'APPROVED'
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : wp.status === 'READY_FOR_REVIEW'
                          ? 'bg-amber-50 text-amber-700 border-amber-200'
                          : wp.status === 'RETURNED_FOR_CORRECTION'
                          ? 'bg-rose-50 text-rose-700 border-rose-200'
                          : 'bg-slate-100 text-slate-700 border-slate-200'
                      }`}
                    >
                      {wp.status.replace(/_/g, ' ')}
                    </span>

                    {/* Evidence Verification Pill */}
                    {wp.evidence_verified ? (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-teal-50 text-teal-700 border border-teal-200 font-medium flex items-center gap-1">
                        <ShieldCheck className="w-3 h-3 text-teal-600" />
                        Evidence Verified
                      </span>
                    ) : (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 font-medium flex items-center gap-1">
                        <AlertCircle className="w-3 h-3 text-slate-400" />
                        Evidence Pending
                      </span>
                    )}
                  </div>
                </div>

                {/* Audit Objective & Results Summary */}
                <div className="bg-slate-50/70 rounded-xl p-4 border border-slate-100 space-y-2">
                  <div className="text-xs text-slate-700">
                    <strong className="text-slate-900 font-semibold">Objective: </strong>
                    {wp.audit_objective}
                  </div>
                  <div className="text-xs text-slate-700">
                    <strong className="text-slate-900 font-semibold">Testing Summary: </strong>
                    {wp.results_summary}
                  </div>
                  {wp.exceptions_noted && (
                    <div className="text-xs text-rose-700 bg-rose-50/80 rounded-lg p-2.5 border border-rose-100 flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600 mt-0.5" />
                      <div>
                        <strong className="font-semibold">Exceptions Identified: </strong>
                        {wp.exceptions_noted}
                      </div>
                    </div>
                  )}
                  {wp.return_reason && (
                    <div className="text-xs text-amber-800 bg-amber-50/80 rounded-lg p-2.5 border border-amber-200 flex items-start gap-2">
                      <RotateCcw className="w-4 h-4 shrink-0 text-amber-600 mt-0.5" />
                      <div>
                        <strong className="font-semibold">Reviewer Return Note: </strong>
                        {wp.return_reason}
                      </div>
                    </div>
                  )}
                </div>

                {/* Governance Footer with Preparer/Reviewer details & Action buttons */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-2 border-t border-slate-100">
                  <div className="flex items-center gap-4 text-xs text-slate-500">
                    <div>
                      Preparer: <strong className="text-slate-700">{(wp as any).preparer_name || 'Senior Associate'}</strong>
                    </div>
                    <div>
                      Reviewer: <strong className="text-slate-700">{(wp as any).reviewer_name || (wp as any).reviewed_by_name || 'Partner'}</strong>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => openReviewModal(wp, 'VERIFY_EVIDENCE')}
                      className="px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer"
                    >
                      <ShieldCheck className="w-3.5 h-3.5 text-teal-600" />
                      Verify Evidence
                    </button>
                    <button
                      onClick={() => openReviewModal(wp, 'REQUEST_CORRECTION')}
                      className="px-3 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer"
                    >
                      <RotateCcw className="w-3.5 h-3.5 text-rose-600" />
                      Return for Correction
                    </button>
                    <button
                      onClick={() => openReviewModal(wp, 'APPROVE')}
                      className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold flex items-center gap-1.5 shadow-xs transition cursor-pointer"
                    >
                      <Check className="w-3.5 h-3.5" />
                      Approve & Sign Off
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Review & Sign-Off Action Modal */}
        {activeWp && (
          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-3xl border border-slate-200 max-w-xl w-full p-6 shadow-xl space-y-5 animate-in fade-in zoom-in duration-150">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div className="flex items-center gap-2.5">
                  <div
                    className={`w-8 h-8 rounded-xl flex items-center justify-center ${
                      modalAction === 'APPROVE'
                        ? 'bg-emerald-50 text-emerald-600'
                        : modalAction === 'REQUEST_CORRECTION'
                        ? 'bg-rose-50 text-rose-600'
                        : 'bg-blue-50 text-blue-600'
                    }`}
                  >
                    {modalAction === 'APPROVE' ? (
                      <CheckCircle2 className="w-4 h-4" />
                    ) : modalAction === 'REQUEST_CORRECTION' ? (
                      <RotateCcw className="w-4 h-4" />
                    ) : (
                      <ShieldCheck className="w-4 h-4" />
                    )}
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">
                      {modalAction === 'APPROVE'
                        ? 'Approve & Sign Off Workpaper'
                        : modalAction === 'REQUEST_CORRECTION'
                        ? 'Return Workpaper for Correction'
                        : 'Verify Underlying Audit Evidence'}
                    </h3>
                    <p className="text-xs text-slate-500 font-mono">{activeWp.wp_reference} — {activeWp.title}</p>
                  </div>
                </div>
                <button
                  onClick={() => setActiveWp(null)}
                  className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Error Callout */}
              {modalError && (
                <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-start gap-2.5">
                  <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold">Review Check Failed:</span> {modalError}
                  </div>
                </div>
              )}

              {/* Workpaper Summary Context */}
              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-100 space-y-1 text-xs text-slate-600">
                <div className="font-semibold text-slate-800">Audit Scope & Coverage:</div>
                <div className="line-clamp-2">{activeWp.scope_and_coverage}</div>
              </div>

              {/* Action Form Inputs */}
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">
                    {modalAction === 'REQUEST_CORRECTION' ? 'Reason for Return (Required)' : 'Sign-Off Justification'}
                  </label>
                  <textarea
                    rows={3}
                    value={modalReason}
                    onChange={(e) => setModalReason(e.target.value)}
                    placeholder={
                      modalAction === 'REQUEST_CORRECTION'
                        ? 'Explain deficiencies or additional testing required...'
                        : 'Confirm procedures comply with engagement materiality...'
                    }
                    className="w-full text-xs p-3 rounded-xl border border-slate-300 focus:outline-hidden focus:ring-2 focus:ring-blue-500 bg-white"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Detailed Review Notes</label>
                  <input
                    type="text"
                    value={modalNotes}
                    onChange={(e) => setModalNotes(e.target.value)}
                    placeholder="Specific transaction references or instructions..."
                    className="w-full text-xs p-2.5 rounded-xl border border-slate-300 focus:outline-hidden focus:ring-2 focus:ring-blue-500 bg-white"
                  />
                </div>

                {modalAction === 'APPROVE' && (
                  <div className="space-y-2 pt-2 border-t border-slate-100">
                    <label className="flex items-center gap-2 text-xs text-slate-700 font-medium cursor-pointer">
                      <input
                        type="checkbox"
                        checked={verifyEvidenceCheck}
                        onChange={(e) => setVerifyEvidenceCheck(e.target.checked)}
                        className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                      />
                      <span>Confirm audit evidence verified against original source documents (SA 500)</span>
                    </label>

                    <label className="flex items-center gap-2 text-xs text-slate-500 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={sodOverrideCheck}
                        onChange={(e) => setSodOverrideCheck(e.target.checked)}
                        className="rounded border-slate-300 text-amber-600 focus:ring-amber-500"
                      />
                      <span>Override separation-of-duties check (Sole practitioner / Emergency review)</span>
                    </label>
                  </div>
                )}
              </div>

              {/* Modal Actions */}
              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  onClick={() => setActiveWp(null)}
                  className="px-4 py-2 rounded-xl text-xs font-medium text-slate-600 hover:bg-slate-100 transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  onClick={handleReviewSubmit}
                  disabled={isSubmitting || (modalAction === 'REQUEST_CORRECTION' && !modalReason.trim())}
                  className={`px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 shadow-xs transition cursor-pointer ${
                    modalAction === 'APPROVE'
                      ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                      : modalAction === 'REQUEST_CORRECTION'
                      ? 'bg-rose-600 hover:bg-rose-500 text-white disabled:opacity-50'
                      : 'bg-blue-600 hover:bg-blue-500 text-white'
                  }`}
                >
                  {isSubmitting ? (
                    <Clock className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Check className="w-3.5 h-3.5" />
                  )}
                  <span>
                    {modalAction === 'APPROVE'
                      ? 'Confirm Approval'
                      : modalAction === 'REQUEST_CORRECTION'
                      ? 'Submit Return Notice'
                      : 'Verify Evidence'}
                  </span>
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default ReviewQueuePage;
