import React, { useEffect, useState } from 'react';
import {
  Briefcase,
  Calendar,
  CheckCircle2,
  Clock,
  ChevronRight,
  ShieldCheck,
  Scale,
  Plus,
  AlertCircle,
  FileText,
  Building2,
  Lock,
} from 'lucide-react';
import { Header } from '../components/Header';
import { api } from '../services/api';
import { Engagement } from '../types';
import { useNavigate } from 'react-router-dom';

export const EngagementsPage: React.FC = () => {
  const navigate = useNavigate();
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const data = await api.getEngagements();
      setEngagements(data || []);
    } catch (err) {
      console.error('Failed to load engagements', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const formatCurrency = (val: string | number) => {
    const num = Number(val) || 0;
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(num);
  };

  return (
    <div className="min-h-screen bg-slate-50/70">
      <Header
        title="Audit Engagements & Scoping"
        subtitle="SA 300 planning, SA 320 materiality benchmarks, statutory milestones, and engagement governance"
      />

      <main className="p-8 max-w-7xl mx-auto space-y-8">
        {/* Banner */}
        <div className="bg-white rounded-3xl border border-slate-200/90 p-6 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-lg">
              <Briefcase className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">Active Audit Engagements</h2>
              <p className="text-xs text-slate-500">
                Track scope of work, materiality limits, fieldwork milestones, and multi-tier completion criteria.
              </p>
            </div>
          </div>

          <button
            onClick={() => navigate('/upload')}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold flex items-center gap-2 shadow-xs transition cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            New Document Batch
          </button>
        </div>

        {/* Engagements List */}
        {isLoading ? (
          <div className="bg-white rounded-3xl border border-slate-200/90 p-12 text-center text-slate-400">
            <Clock className="w-8 h-8 animate-spin mx-auto text-blue-500 mb-3" />
            <p className="text-sm font-medium">Loading engagement portfolios...</p>
          </div>
        ) : engagements.length === 0 ? (
          <div className="bg-white rounded-3xl border border-slate-200/90 p-12 text-center text-slate-400">
            <Briefcase className="w-10 h-10 mx-auto text-slate-300 mb-3" />
            <h3 className="text-base font-semibold text-slate-800">No Engagements Created Yet</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              Engagements are automatically created or bound during document upload and processing runs.
            </p>
          </div>
        ) : (
          <div className="space-y-5">
            {engagements.map((eng) => (
              <div
                key={eng.id}
                className="bg-white rounded-2xl border border-slate-200/90 p-6 shadow-xs hover:border-slate-300 transition space-y-5"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3.5">
                    <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
                      <Scale className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-base font-bold text-slate-900">{eng.title}</h3>
                        <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                          {(eng.engagement_type || 'STATUTORY').replace(/_/g, ' ')}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-slate-500 mt-0.5">
                        <span className="flex items-center gap-1">
                          <Building2 className="w-3.5 h-3.5 text-slate-400" />
                          {eng.company_name || 'Apex Infotech Pvt Ltd'}
                        </span>
                        <span>•</span>
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3.5 h-3.5 text-slate-400" />
                          {eng.fy_label || 'FY 2024-25'}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs px-2.5 py-1 rounded-full font-semibold border ${
                        eng.status === 'COMPLETED'
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : eng.status === 'REVIEW'
                          ? 'bg-purple-50 text-purple-700 border-purple-200'
                          : eng.status === 'FIELDWORK'
                          ? 'bg-blue-50 text-blue-700 border-blue-200'
                          : 'bg-amber-50 text-amber-700 border-amber-200'
                      }`}
                    >
                      {(eng.status || 'PLANNING').replace(/_/g, ' ')}
                    </span>
                  </div>
                </div>

                {/* SA 320 Materiality Framework */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-slate-50/70 rounded-xl p-4 border border-slate-100">
                  <div>
                    <span className="text-[10px] text-slate-400 uppercase font-semibold block">
                      Overall Materiality (SA 320)
                    </span>
                    <span className="text-sm font-bold text-slate-900 mt-0.5 block">
                      {formatCurrency(eng.overall_materiality)}
                    </span>
                    <span className="text-[10px] text-slate-500">Benchmark tolerance ceiling</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 uppercase font-semibold block">
                      Performance Materiality (75%)
                    </span>
                    <span className="text-sm font-bold text-slate-900 mt-0.5 block">
                      {formatCurrency(eng.performance_materiality)}
                    </span>
                    <span className="text-[10px] text-slate-500">Substantive testing threshold</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400 uppercase font-semibold block">
                      Clearly Trivial Threshold (5%)
                    </span>
                    <span className="text-sm font-bold text-slate-900 mt-0.5 block">
                      {formatCurrency(eng.clearly_trivial_threshold)}
                    </span>
                    <span className="text-[10px] text-slate-500">Sum-of-differences posting floor</span>
                  </div>
                </div>

                {/* Engagement Actions */}
                <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-100">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => navigate('/workpapers')}
                      className="px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer"
                    >
                      <FileText className="w-3.5 h-3.5 text-blue-600" />
                      View Working Papers
                    </button>
                    <button
                      onClick={() => navigate('/review-queue')}
                      className="px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer"
                    >
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                      Review Queue
                    </button>
                  </div>

                  <button
                    onClick={() => navigate('/final-audit-file')}
                    className="text-blue-600 hover:text-blue-700 font-semibold text-xs flex items-center gap-1 cursor-pointer"
                  >
                    <span>Final Audit File & Package</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
};

export default EngagementsPage;
