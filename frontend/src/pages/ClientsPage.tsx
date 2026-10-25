import React, { useEffect, useState, useCallback } from 'react';
import {
  Building2,
  Plus,
  MapPin,
  ChevronRight,
  Clock,
  GitBranch,
  Trash2,
  Loader2,
} from 'lucide-react';
import { Header } from '../components/Header';
import { api } from '../services/api';
import { Company } from '../types';
import { useNavigate } from 'react-router-dom';

export const ClientsPage: React.FC = () => {
  const navigate = useNavigate();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [isClearingAll, setIsClearingAll] = useState(false);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await api.getCompanies();
      setCompanies(data || []);
    } catch (err) {
      console.error('Failed to load companies', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleDeleteCompany = async (e: React.MouseEvent, id: number, name: string) => {
    e.stopPropagation();
    if (!window.confirm(`Are you sure you want to remove client "${name}" and all its associated audit files?`)) {
      return;
    }
    setDeletingId(id);
    try {
      await api.deleteCompany(id);
      setCompanies((prev) => prev.filter((c) => c.id !== id));
    } catch (err) {
      console.error('Failed to delete company', err);
      alert('Failed to delete client entity. Please try again.');
    } finally {
      setDeletingId(null);
    }
  };

  const handleClearAll = async () => {
    if (!window.confirm(`⚠️ WARNING: Are you sure you want to remove ALL ${companies.length} registered client entities? This action will permanently remove all test/client entities.`)) {
      return;
    }
    setIsClearingAll(true);
    try {
      await api.clearAllCompanies();
      setCompanies([]);
    } catch (err) {
      console.error('Failed to clear all companies', err);
      alert('Failed to clear clients. Please try again.');
    } finally {
      setIsClearingAll(false);
    }
  };

  const getTierBadge = (tier?: string) => {
    switch (tier) {
      case 'TIER_4_ENTERPRISE':
        return { label: 'Tier 4 — Large Enterprise', color: 'bg-purple-50 text-purple-700 border-purple-200' };
      case 'TIER_3_MID':
        return { label: 'Tier 3 — Mid-Market Pvt Ltd', color: 'bg-blue-50 text-blue-700 border-blue-200' };
      case 'TIER_2_SME':
        return { label: 'Tier 2 — SME / LLP', color: 'bg-emerald-50 text-emerald-700 border-emerald-200' };
      case 'TIER_1_SMALL':
        return { label: 'Tier 1 — Small / Proprietor', color: 'bg-amber-50 text-amber-700 border-amber-200' };
      default:
        return { label: 'Tier 3 — Mid-Market Pvt Ltd', color: 'bg-blue-50 text-blue-700 border-blue-200' };
    }
  };

  return (
    <div className="min-h-screen bg-slate-50/70">
      <Header
        title="Clients & Company Master"
        subtitle="Enterprise hierarchy, multi-branch entities, statutory identifiers, and business scale tiering"
      />

      <main className="p-8 max-w-7xl mx-auto space-y-8">
        {/* Top Summary Banner */}
        <div className="bg-white rounded-3xl border border-slate-200/90 p-6 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-lg">
              <Building2 className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">Registered Audit Client Entities</h2>
              <p className="text-xs text-slate-500">
                Manage company profiles, Corporate Identification Numbers (CIN), PAN, GSTINs, and branch consolidations.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            {companies.length > 0 && (
              <button
                onClick={handleClearAll}
                disabled={isClearingAll}
                className="px-3.5 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-xl text-xs font-semibold flex items-center gap-1.5 shadow-2xs transition cursor-pointer"
                title="Remove all registered client entities"
              >
                {isClearingAll ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-rose-600" />
                ) : (
                  <Trash2 className="w-3.5 h-3.5 text-rose-600" />
                )}
                <span>Remove All ({companies.length})</span>
              </button>
            )}

            <button
              onClick={() => navigate('/upload')}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold flex items-center gap-2 shadow-xs transition cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              Upload Client Documents
            </button>
          </div>
        </div>

        {/* Clients Grid */}
        {isLoading ? (
          <div className="bg-white rounded-3xl border border-slate-200/90 p-12 text-center text-slate-400">
            <Clock className="w-8 h-8 animate-spin mx-auto text-blue-500 mb-3" />
            <p className="text-sm font-medium">Loading client companies...</p>
          </div>
        ) : companies.length === 0 ? (
          <div className="bg-white rounded-3xl border border-slate-200/90 p-12 text-center text-slate-400">
            <Building2 className="w-10 h-10 mx-auto text-slate-300 mb-3" />
            <h3 className="text-base font-semibold text-slate-800">No Clients Configured Yet</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto mb-4">
              All client entities have been removed. Upload documents or start an audit run to register new clients.
            </p>
            <button
              onClick={() => navigate('/upload')}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold inline-flex items-center gap-2 shadow-xs transition cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              Upload Master Workbook
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {companies.map((co) => {
              const tier = getTierBadge(co.business_tier);
              const isDeletingThis = deletingId === co.id;
              return (
                <div
                  key={co.id}
                  className="bg-white rounded-2xl border border-slate-200/90 p-6 shadow-xs hover:border-slate-300 transition space-y-5"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-slate-100 text-slate-700 font-bold flex items-center justify-center text-sm">
                        {co.name.substring(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <h3 className="text-base font-bold text-slate-900">{co.name}</h3>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold border ${tier.color}`}>
                            {tier.label}
                          </span>
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-medium">
                            {co.entity_type.replace(/_/g, ' ')}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-1">
                      <button
                        onClick={(e) => handleDeleteCompany(e, co.id, co.name)}
                        disabled={isDeletingThis}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition cursor-pointer"
                        title={`Remove client ${co.name}`}
                        aria-label={`Remove client ${co.name}`}
                      >
                        {isDeletingThis ? (
                          <Loader2 className="w-4 h-4 animate-spin text-rose-600" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </button>

                      <button
                        onClick={() => navigate('/engagements')}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-blue-600 hover:bg-blue-50 transition cursor-pointer"
                        title="View Engagements"
                      >
                        <ChevronRight className="w-5 h-5" />
                      </button>
                    </div>
                  </div>

                  {/* Statutory Identifiers */}
                  <div className="grid grid-cols-3 gap-3 bg-slate-50/70 rounded-xl p-3 border border-slate-100 text-xs">
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase font-semibold block">CIN</span>
                      <span className="font-mono text-slate-800 font-medium truncate block">{co.cin || 'N/A'}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase font-semibold block">PAN</span>
                      <span className="font-mono text-slate-800 font-medium truncate block">{co.pan || 'N/A'}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase font-semibold block">GSTIN</span>
                      <span className="font-mono text-slate-800 font-medium truncate block">{co.gstin || 'N/A'}</span>
                    </div>
                  </div>

                  {/* Branch & Location Info */}
                  <div className="space-y-1.5 text-xs text-slate-600">
                    <div className="flex items-center gap-2 text-slate-700">
                      <GitBranch className="w-3.5 h-3.5 text-slate-400" />
                      <span>Branch: <strong>{co.branch_name || 'Head Office'}</strong> {co.branch_code ? `(${co.branch_code})` : ''}</span>
                    </div>
                    {co.registered_address && (
                      <div className="flex items-center gap-2 text-slate-500">
                        <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                        <span className="truncate">{co.registered_address}</span>
                      </div>
                    )}
                  </div>

                  {/* Action Link Footer */}
                  <div className="flex items-center justify-between pt-3 border-t border-slate-100 text-xs">
                    <span className="text-slate-400">Industry: <strong className="text-slate-600">{co.industry}</strong></span>
                    <div className="flex items-center gap-3">
                      <button
                        onClick={(e) => handleDeleteCompany(e, co.id, co.name)}
                        disabled={isDeletingThis}
                        className="text-slate-400 hover:text-rose-600 text-xs font-medium flex items-center gap-1 cursor-pointer transition"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        <span>Remove</span>
                      </button>
                      <span className="text-slate-200">|</span>
                      <button
                        onClick={() => navigate('/upload')}
                        className="text-blue-600 hover:text-blue-700 font-semibold flex items-center gap-1 cursor-pointer"
                      >
                        <span>New Audit Run</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
};

export default ClientsPage;
