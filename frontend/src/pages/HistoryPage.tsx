import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  History,
  Search,
  Filter,
  Download,
  FileCheck2,
  Activity,
  Layers,
  Calendar,
  Building2,
  Clock,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
  ExternalLink,
  Hash,
  ChevronRight,
  FileText
} from 'lucide-react';
import { api } from '../services/api';
import { ProcessingRun } from '../types';

export const HistoryPage: React.FC = () => {
  const [runs, setRuns] = useState<ProcessingRun[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchRuns = async (showLoading = false) => {
    if (showLoading) setIsLoading(true);
    setIsRefreshing(true);
    try {
      const data = await api.getProcessingRuns();
      setRuns(Array.isArray(data) ? data : []);
    } catch (err: any) {
      console.error('Failed to fetch runs history', err);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchRuns(true);
  }, []);

  const handleDownloadZip = async (runId: string) => {
    try {
      await api.downloadAuditPackage(runId);
    } catch (err: any) {
      alert(`Download failed: ${err.message || 'Audit package not ready'}`);
    }
  };

  const filteredRuns = runs.filter((r) => {
    const matchesSearch =
      r.run_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.company_name && r.company_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (r.engagement_title && r.engagement_title.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesStatus = statusFilter === 'ALL' || r.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="min-h-screen bg-slate-50/70 text-slate-900 p-6 lg:p-10 font-sans">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold px-2.5 py-1 rounded-md bg-purple-50 text-purple-700 border border-purple-200 uppercase tracking-wider flex items-center gap-1.5">
              <History className="w-3.5 h-3.5" />
              <span>Immutable Audit Archive</span>
            </span>
            <span className="text-slate-500 text-xs font-semibold">
              {runs.length} Processing {runs.length === 1 ? 'Run' : 'Runs'} Recorded
            </span>
          </div>
          <h1 className="text-2xl lg:text-3xl font-extrabold text-slate-900 tracking-tight mt-1">
            Audit Engagement History & Versions
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Dedicated chronological archive of all autonomous audit processing runs, original evidence, and finalized workpapers.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => fetchRuns(false)}
            disabled={isRefreshing}
            className="px-4 py-2.5 rounded-xl bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 font-medium text-sm flex items-center gap-2 transition shadow-xs cursor-pointer"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <Link
            to="/upload"
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-semibold text-sm flex items-center gap-2 transition shadow-sm cursor-pointer"
          >
            <FileText className="w-4 h-4" />
            <span>New Document Run</span>
          </Link>
        </div>
      </div>

      {/* Filter & Search Toolbar */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-4 mt-6 bg-white border border-slate-200/90 p-4 rounded-2xl shadow-xs">
        {/* Search */}
        <div className="relative w-full md:w-96">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
          <input
            type="text"
            placeholder="Search by Company, Run ID, or Engagement..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-slate-50 border border-slate-300 rounded-xl pl-10 pr-4 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 transition"
          />
        </div>

        {/* Status Filters */}
        <div className="flex items-center gap-1.5 w-full md:w-auto overflow-x-auto pb-1 md:pb-0">
          {[
            { id: 'ALL', label: 'All Runs' },
            { id: 'COMPLETED', label: 'Completed' },
            { id: 'REVIEW_REQUIRED', label: 'Review Required' },
            { id: 'BLOCKED', label: 'Blocked' },
            { id: 'FAILED', label: 'Failed' },
          ].map((st) => (
            <button
              key={st.id}
              onClick={() => setStatusFilter(st.id)}
              className={`text-xs px-3 py-1.5 rounded-xl font-medium transition whitespace-nowrap cursor-pointer ${
                statusFilter === st.id
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-slate-50 text-slate-600 hover:text-slate-900 border border-slate-200 hover:bg-slate-100'
              }`}
            >
              {st.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Table / Runs List */}
      <div className="mt-6">
        {isLoading ? (
          <div className="py-20 flex flex-col items-center justify-center">
            <Activity className="w-10 h-10 text-blue-600 animate-spin mb-3" />
            <span className="text-slate-500 text-sm">Loading audit run history...</span>
          </div>
        ) : filteredRuns.length === 0 ? (
          <div className="bg-white border border-slate-200 rounded-2xl p-12 text-center shadow-xs">
            <History className="w-12 h-12 text-slate-400 mx-auto mb-3" />
            <h3 className="text-base font-bold text-slate-900 mb-1">No Processing Runs Found</h3>
            <p className="text-slate-500 text-xs max-w-sm mx-auto mb-5">
              {searchTerm || statusFilter !== 'ALL'
                ? 'No runs match the specified filter criteria. Try adjusting your search.'
                : 'No documents have been uploaded yet. Upload your accounting records to launch an automated audit run.'}
            </p>
            <Link
              to="/upload"
              className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-xl transition text-xs inline-flex items-center gap-2 cursor-pointer shadow-sm"
            >
              <FileText className="w-4 h-4" /> Go to Document Upload
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredRuns.map((item) => {
              const isCompleted = item.status === 'COMPLETED' || item.status === 'PARTIALLY_COMPLETED';
              const isFailed = item.status === 'FAILED' || item.status === 'BLOCKED';

              return (
                <div
                  key={item.id}
                  className="bg-white border border-slate-200/90 hover:border-slate-300 rounded-2xl p-5 transition shadow-xs"
                >
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    {/* Left details */}
                    <div className="min-w-0">
                      <div className="flex items-center gap-3 flex-wrap">
                        {/* Status Badge */}
                        <span
                          className={`text-[10px] font-bold px-2.5 py-0.5 rounded uppercase tracking-wider ${
                            isCompleted
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : isFailed
                              ? 'bg-rose-50 text-rose-700 border border-rose-200'
                              : 'bg-blue-50 text-blue-700 border border-blue-200'
                          }`}
                        >
                          {item.status.replace('_', ' ')}
                        </span>

                        <span className="font-mono text-xs text-blue-700 font-semibold">{item.run_id}</span>
                        <span className="text-slate-500 text-xs">
                          {new Date(item.started_at).toLocaleDateString()} {new Date(item.started_at).toLocaleTimeString()}
                        </span>

                        {/* Test Dataset vs Client Audit Badge */}
                        {item.summary_metrics?.is_synthetic_test_data || item.company_name?.includes('[TEST DEMO]') || item.engagement_title?.includes('[SYNTHETIC') ? (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-300 uppercase tracking-wider">
                            [TEST DATASET]
                          </span>
                        ) : (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-cyan-50 text-cyan-800 border border-cyan-300 uppercase tracking-wider">
                            [CLIENT AUDIT]
                          </span>
                        )}
                      </div>

                      <h3 className="text-base font-bold text-slate-900 mt-1.5 tracking-tight truncate">
                        {item.company_name || 'Assurance Client Entity'}
                      </h3>

                      <div className="flex items-center gap-4 text-xs text-slate-500 mt-1 flex-wrap">
                        <span className="flex items-center gap-1.5">
                          <Layers className="w-3.5 h-3.5 text-indigo-600" />
                          <span>{item.documents?.length || 0} Original Documents</span>
                        </span>

                        <span className="flex items-center gap-1.5">
                          <ShieldCheck className="w-3.5 h-3.5 text-blue-600" />
                          <span>{item.engagement_title || 'Statutory Audit'}</span>
                        </span>

                        {item.summary_metrics?.total_records && (
                          <span>• {item.summary_metrics.total_records} Records Parsed</span>
                        )}

                        {item.summary_metrics?.exceptions_raised !== undefined && (
                          <span className={item.summary_metrics.exceptions_raised > 0 ? 'text-amber-700 font-semibold' : 'text-slate-500'}>
                            • {item.summary_metrics.exceptions_raised} Exceptions
                          </span>
                        )}

                        {item.zip_package_hash && (
                          <span className="font-mono text-[11px] text-slate-400">
                            Hash: {item.zip_package_hash.substring(0, 12)}...
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Right actions */}
                    <div className="flex items-center gap-2.5 shrink-0 flex-wrap">
                      <Link
                        to={`/processing/${item.run_id}`}
                        className="px-3.5 py-2 rounded-xl bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 text-xs font-medium flex items-center gap-1.5 transition cursor-pointer"
                      >
                        <Activity className="w-3.5 h-3.5 text-blue-600" />
                        <span>Execution Logs</span>
                      </Link>

                      {isCompleted && (
                        <>
                          <button
                            onClick={() => handleDownloadZip(item.run_id)}
                            className="px-3.5 py-2 rounded-xl bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 text-xs font-medium flex items-center gap-1.5 transition cursor-pointer"
                            title="Download Audit Package (.ZIP)"
                          >
                            <Download className="w-3.5 h-3.5 text-emerald-600" />
                            <span>Download .ZIP</span>
                          </button>

                          <Link
                            to={`/final-audit-file?runId=${item.run_id}`}
                            className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs flex items-center gap-1.5 transition shadow-xs cursor-pointer"
                          >
                            <FileCheck2 className="w-3.5 h-3.5" />
                            <span>Open Final Audit File</span>
                            <ChevronRight className="w-3.5 h-3.5" />
                          </Link>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default HistoryPage;
