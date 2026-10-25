import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  FileQuestion,
  ArrowLeft,
  Home,
  CloudUpload,
  FileCheck2,
  AlertTriangle,
  Compass,
  ShieldAlert
} from 'lucide-react';

export const NotFoundPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center items-center px-4 py-12 sm:px-6 lg:px-8">
      <div className="max-w-xl w-full text-center space-y-8">
        {/* Visual Badge & Icon */}
        <div className="flex flex-col items-center">
          <div className="relative mb-4">
            <div className="w-24 h-24 sm:w-28 sm:h-28 rounded-3xl bg-blue-50 border-2 border-blue-200 flex items-center justify-center text-blue-600 shadow-sm">
              <FileQuestion className="w-12 h-12 sm:w-14 sm:h-14 stroke-[1.5]" />
            </div>
            <div className="absolute -bottom-2 -right-2 p-2 bg-amber-500 text-white rounded-xl shadow-md border-2 border-white">
              <ShieldAlert className="w-5 h-5" />
            </div>
          </div>
          
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-100/80 text-amber-800 border border-amber-300">
            <span>SA 230 DOCUMENTATION NOTICE</span>
          </div>

          <h1 className="mt-4 text-4xl sm:text-5xl font-black text-slate-900 tracking-tight">
            404 <span className="text-blue-600 font-semibold text-2xl sm:text-3xl block sm:inline sm:ml-2">Working Paper Not Found</span>
          </h1>
          <p className="mt-3 text-sm sm:text-base text-slate-600 max-w-md mx-auto leading-relaxed">
            The audit schedule, ledger voucher, or engagement route you are attempting to inspect does not exist in the active working papers.
          </p>
        </div>

        {/* Primary Action Buttons */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <button
            onClick={() => navigate(-1)}
            className="w-full sm:w-auto px-5 py-2.5 rounded-xl border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 font-semibold text-xs flex items-center justify-center gap-2 shadow-2xs transition cursor-pointer"
          >
            <ArrowLeft className="w-4 h-4 text-slate-500" />
            <span>Go Back to Previous File</span>
          </button>
          <Link
            to="/"
            className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs flex items-center justify-center gap-2 shadow-md shadow-blue-600/20 transition cursor-pointer"
          >
            <Home className="w-4 h-4" />
            <span>Audit Dashboard</span>
          </Link>
        </div>

        {/* Quick Directory for Statutory Auditors */}
        <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-2xs text-left">
          <div className="flex items-center gap-2 mb-3 pb-2 border-b border-slate-100">
            <Compass className="w-4 h-4 text-blue-600" />
            <span className="text-xs font-bold text-slate-800 uppercase tracking-wide">
              Quick Audit Navigation Links
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-xs">
            <Link
              to="/upload"
              className="p-3 rounded-xl bg-slate-50 hover:bg-blue-50/60 border border-slate-200/80 hover:border-blue-200 text-slate-700 hover:text-blue-700 transition flex items-center gap-2.5 group"
            >
              <CloudUpload className="w-4 h-4 text-slate-400 group-hover:text-blue-600 shrink-0" />
              <div>
                <span className="font-semibold block">Upload Pack</span>
                <span className="text-[10px] text-slate-500">Master Workbooks</span>
              </div>
            </Link>

            <Link
              to="/final-audit-file"
              className="p-3 rounded-xl bg-slate-50 hover:bg-blue-50/60 border border-slate-200/80 hover:border-blue-200 text-slate-700 hover:text-blue-700 transition flex items-center gap-2.5 group"
            >
              <FileCheck2 className="w-4 h-4 text-slate-400 group-hover:text-blue-600 shrink-0" />
              <div>
                <span className="font-semibold block">Final Audit File</span>
                <span className="text-[10px] text-slate-500">Schedule III & P&L</span>
              </div>
            </Link>

            <Link
              to="/exceptions"
              className="p-3 rounded-xl bg-slate-50 hover:bg-blue-50/60 border border-slate-200/80 hover:border-blue-200 text-slate-700 hover:text-blue-700 transition flex items-center gap-2.5 group"
            >
              <AlertTriangle className="w-4 h-4 text-slate-400 group-hover:text-amber-600 shrink-0" />
              <div>
                <span className="font-semibold block">Exceptions</span>
                <span className="text-[10px] text-slate-500">MSME & GST Risks</span>
              </div>
            </Link>
          </div>
        </div>

        {/* Security & Integrity Note */}
        <p className="text-[11px] text-slate-400">
          Captrix Statutory Audit Engine • Fail-Closed Audit Trail • ICAI Standards Compliant
        </p>
      </div>
    </div>
  );
};

export default NotFoundPage;
