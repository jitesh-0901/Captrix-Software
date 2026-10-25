import React, { useState } from 'react';
import {
  Shield,
  Lock,
  UserCheck,
  CheckCircle2,
  AlertTriangle,
  FileCheck,
  Key,
  Database,
  Building,
  Fingerprint,
} from 'lucide-react';
import { Header } from '../components/Header';

export const SettingsPage: React.FC = () => {
  const [sodPolicy, setSodPolicy] = useState(true);
  const [hashVerification, setHashVerification] = useState(true);
  const [draftWatermark, setDraftWatermark] = useState(true);

  return (
    <div className="min-h-screen bg-slate-50/70">
      <Header
        title="Settings & Access Control"
        subtitle="Role-based governance, separation of duties policies, cryptographic file integrity, and professional sign-off controls"
      />

      <main className="p-8 max-w-7xl mx-auto space-y-8">
        {/* Statutory Assurance & Integrity Guardrails */}
        <div className="bg-gradient-to-r from-blue-900 to-[#0a1128] rounded-3xl p-6 text-white shadow-md flex items-center justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-[#00e5ff]" />
              <h2 className="text-base font-bold">ICAI Professional Sign-Off & Ethics Policy</h2>
            </div>
            <p className="text-xs text-blue-200 max-w-2xl leading-relaxed">
              Captrix strictly enforces the professional code of ethics. The system never fabricates an ICAI Unique Document Identification Number (UDIN), CA digital signature, or statutory sign-off. All exported reports are branded as draft workpapers until explicitly approved by an authorized Chartered Accountant.
            </p>
          </div>
          <div className="hidden sm:flex items-center gap-2 bg-blue-950/80 px-4 py-2 rounded-xl border border-blue-800 text-xs font-semibold text-blue-300">
            <Fingerprint className="w-4 h-4 text-[#00e5ff]" />
            <span>SA 220 Enforced</span>
          </div>
        </div>

        {/* Governance Controls Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Access Control & Separation of Duties */}
          <div className="bg-white rounded-2xl border border-slate-200/90 p-6 shadow-xs space-y-5">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
                <UserCheck className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900">Separation of Duties (SA 220 / SQC 1)</h3>
                <p className="text-xs text-slate-500">Dual-custody controls for audit sign-offs</p>
              </div>
            </div>

            <div className="space-y-4 pt-2">
              <div className="flex items-center justify-between p-3.5 bg-slate-50 rounded-xl border border-slate-100">
                <div>
                  <div className="text-xs font-bold text-slate-800">Preparer-Reviewer Segregation</div>
                  <div className="text-[11px] text-slate-500">Prevent preparers from approving their own workpapers</div>
                </div>
                <input
                  type="checkbox"
                  checked={sodPolicy}
                  onChange={(e) => setSodPolicy(e.target.checked)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-4 h-4 cursor-pointer"
                />
              </div>

              <div className="flex items-center justify-between p-3.5 bg-slate-50 rounded-xl border border-slate-100">
                <div>
                  <div className="text-xs font-bold text-slate-800">Draft Watermarking</div>
                  <div className="text-[11px] text-slate-500">Embed DRAFT banner across unapproved PDF/Excel exports</div>
                </div>
                <input
                  type="checkbox"
                  checked={draftWatermark}
                  onChange={(e) => setDraftWatermark(e.target.checked)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-4 h-4 cursor-pointer"
                />
              </div>

              <div className="flex items-center justify-between p-3.5 bg-slate-50 rounded-xl border border-slate-100">
                <div>
                  <div className="text-xs font-bold text-slate-800">SHA-256 Cryptographic Immutability</div>
                  <div className="text-[11px] text-slate-500">Verify file byte integrity before and after ingestion</div>
                </div>
                <input
                  type="checkbox"
                  checked={hashVerification}
                  onChange={(e) => setHashVerification(e.target.checked)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-4 h-4 cursor-pointer"
                />
              </div>
            </div>
          </div>

          {/* User Role Matrix */}
          <div className="bg-white rounded-2xl border border-slate-200/90 p-6 shadow-xs space-y-5">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center font-bold">
                <Lock className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900">User Role Permissions</h3>
                <p className="text-xs text-slate-500">Engagement-level permissions matrix</p>
              </div>
            </div>

            <div className="space-y-2.5 pt-2 text-xs">
              {[
                { role: 'Partner (CA)', desc: 'Full authority, final engagement sign-off, permitted exception approvals, and report release.', color: 'border-purple-200 bg-purple-50/60 text-purple-900' },
                { role: 'Audit Manager', desc: 'Workpaper review, review queue clearance, materiality benchmarking, procedure assignment.', color: 'border-blue-200 bg-blue-50/60 text-blue-900' },
                { role: 'Senior Auditor', desc: 'Substantive testing, GL scrutiny, reconciliation approval, audit exception tagging.', color: 'border-teal-200 bg-teal-50/60 text-teal-900' },
                { role: 'Preparer / Articled Assistant', desc: 'Document upload, routine data normalization, drafting initial workpapers.', color: 'border-slate-200 bg-slate-50 text-slate-800' },
              ].map((r) => (
                <div key={r.role} className={`p-3 rounded-xl border ${r.color}`}>
                  <div className="font-bold">{r.role}</div>
                  <div className="text-[11px] opacity-90 mt-0.5">{r.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default SettingsPage;
