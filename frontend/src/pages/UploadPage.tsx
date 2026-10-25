import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  CloudUpload,
  Building2,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Check,
  Layers,
  X,
  FileSpreadsheet,
  FileText,
  FileArchive,
  ShieldCheck,
  ArrowRight,
  Plus,
  AlertTriangle,
  HelpCircle
} from 'lucide-react';
import { api } from '../services/api';

interface AuditDocRequirement {
  title: string;
  key: string;
  mandatory: boolean;
  procedureImpact: string;
}

export const UploadPage: React.FC = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [companyName, setCompanyName] = useState('');
  const [financialYear, setFinancialYear] = useState('FY 2024-25');
  const [auditType, setAuditType] = useState('STATUTORY');
  const [businessTier, setBusinessTier] = useState<string>('AUTO');
  const [stagedFiles, setStagedFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const getRequiredDocsMatrix = (tier: string, eType: string): AuditDocRequirement[] => {
    const docs: AuditDocRequirement[] = [
      {
        title: 'Signed Trial Balance',
        key: 'trial',
        mandatory: true,
        procedureImpact: 'Mandatory for double-entry equilibrium, financial statements, and balance sheet mapping.'
      },
      {
        title: 'General Ledger Dump',
        key: 'ledger',
        mandatory: true,
        procedureImpact: 'Mandatory for voucher scrutiny, Benford\'s Law forensic testing, and round-sum journal checks.'
      },
      {
        title: 'Bank Statements & BRS',
        key: 'bank',
        mandatory: true,
        procedureImpact: 'Required for Bank Reconciliation Statement (BRS) 4-way matching against book entries.'
      },
    ];

    if (eType === 'STATUTORY' || eType === 'TAX' || tier === 'AUTO' || tier === 'TIER_3_MID' || tier === 'TIER_4_ENTERPRISE') {
      docs.push(
        {
          title: 'Fixed Asset Register (FAR)',
          key: 'asset',
          mandatory: false,
          procedureImpact: 'Required for CARO 2020 Clause 3(i) & dual depreciation recalculation (Companies Act vs IT Act).'
        },
        {
          title: 'Sundry Debtors & Creditors (MSME)',
          key: 'subledger',
          mandatory: false,
          procedureImpact: 'Required for Section 43B(h) MSME 45-day overdue disallowance and aging risk screening.'
        },
        {
          title: 'GSTR-2B Statement',
          key: 'gstr',
          mandatory: false,
          procedureImpact: 'Required for GST Rule 36(4) Input Tax Credit (ITC) reconciliation against purchase registers.'
        },
        {
          title: 'Purchase / Sales Register',
          key: 'purchase',
          mandatory: false,
          procedureImpact: 'Required for cross-document trade payables and turnover substantiation.'
        }
      );
    }
    return docs;
  };

  const inferDocType = (filename: string): { label: string; key: string } => {
    const fn = filename.toLowerCase();
    if (fn.endsWith('.zip')) return { label: 'Client Documents Archive (ZIP)', key: 'zip' };
    if (fn.includes('trial') || fn.includes('tb')) return { label: 'Trial Balance', key: 'trial' };
    if (fn.includes('bank') || fn.includes('statement') || fn.includes('passbook') || fn.includes('brs')) return { label: 'Bank Statement', key: 'bank' };
    if (fn.includes('gstr') || fn.includes('2b')) return { label: 'GSTR-2B ITC Statement', key: 'gstr' };
    if (fn.includes('purchase')) return { label: 'Purchase Register', key: 'purchase' };
    if (fn.includes('sales')) return { label: 'Sales Register', key: 'sales' };
    if (fn.includes('asset') || fn.includes('far')) return { label: 'Fixed Asset Register (FAR)', key: 'asset' };
    if (fn.includes('aging') || fn.includes('debtor') || fn.includes('creditor') || fn.includes('subledger') || fn.includes('msme')) {
      return { label: 'Subledger Aging (Debtors/Creditors)', key: 'subledger' };
    }
    if (fn.includes('ledger') || fn.includes('gl')) return { label: 'General Ledger Dump', key: 'ledger' };
    return { label: 'Financial Accounting Document', key: 'other' };
  };

  const isDocStaged = (key: string): { staged: boolean; filename?: string } => {
    // If a ZIP archive is staged, all core documents are assumed bundled
    const zipFile = stagedFiles.find((f) => f.name.toLowerCase().endsWith('.zip'));
    if (zipFile) {
      return { staged: true, filename: zipFile.name };
    }

    // If a Master Multi-Sheet Excel workbook or Financial Report is staged
    const masterWorkbook = stagedFiles.find((f) => {
      const fn = f.name.toLowerCase();
      return (
        (fn.endsWith('.xlsx') || fn.endsWith('.xls')) &&
        (stagedFiles.length === 1 ||
          fn.includes('master') ||
          fn.includes('account') ||
          fn.includes('financial') ||
          fn.includes('annual') ||
          fn.includes('audit') ||
          fn.includes('pack') ||
          fn.includes('reliance') ||
          fn.includes('client'))
      );
    });
    if (masterWorkbook) {
      return { staged: true, filename: `${masterWorkbook.name} [Workbook Tab]` };
    }

    const match = stagedFiles.find((f) => inferDocType(f.name).key === key);
    if (match) {
      return { staged: true, filename: match.name };
    }
    return { staged: false };
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const addFilesToBatch = (newFiles: File[]) => {
    const validFiles: File[] = [];
    const ALLOWED = ['.csv', '.xlsx', '.xls', '.pdf', '.png', '.jpg', '.jpeg', '.zip'];

    for (const file of newFiles) {
      if (file.size === 0) {
        setErrorMsg(`File '${file.name}' is empty (0 bytes).`);
        continue;
      }
      const ext = '.' + file.name.split('.').pop()?.toLowerCase();
      if (!ALLOWED.includes(ext)) {
        setErrorMsg(`Unsupported file type '${ext}'. Please upload financial documents (.csv, .xlsx, .xls, .pdf, .zip).`);
        continue;
      }
      validFiles.push(file);
    }

    if (validFiles.length > 0) {
      // Deduplicate by name and size
      setStagedFiles((prev) => {
        const existingKeys = new Set(prev.map((f) => `${f.name}-${f.size}`));
        const toAdd = validFiles.filter((f) => !existingKeys.has(`${f.name}-${f.size}`));
        return [...prev, ...toAdd];
      });
      setErrorMsg(null);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addFilesToBatch(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFilesToBatch(Array.from(e.target.files));
    }
  };

  const removeFile = (index: number) => {
    setStagedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleStartProcessing = async () => {
    if (stagedFiles.length === 0) {
      setErrorMsg('Please select at least one financial document (.csv, .xlsx, .pdf, or .zip) to analyze.');
      return;
    }

    setIsLoading(true);
    setErrorMsg(null);
    try {
      const formData = new FormData();
      stagedFiles.forEach((file) => {
        formData.append('files', file);
        if (file.name.toLowerCase().endsWith('.zip')) {
          formData.append('archive', file);
        }
      });
      if (companyName.trim()) formData.append('company_name', companyName.trim());
      if (financialYear.trim()) formData.append('fy_label', financialYear.trim());
      if (auditType) formData.append('audit_type', auditType);
      if (businessTier) formData.append('business_tier', businessTier);

      const run = await api.startProcessingRun(formData);
      if (run && run.run_id) {
        navigate(`/processing/${run.run_id}`);
      } else {
        throw new Error('Run initiated without valid run ID');
      }
    } catch (err: any) {
      setErrorMsg(err.error || err.message || 'Error occurred during pipeline initiation.');
    } finally {
      setIsLoading(false);
    }
  };

  const requiredDocs = getRequiredDocsMatrix(businessTier, auditType);
  const stagedCount = requiredDocs.filter((d) => isDocStaged(d.key).staged).length;
  const missingCount = requiredDocs.length - stagedCount;

  return (
    <div className="min-h-screen bg-slate-50/70 text-slate-900 p-6 lg:p-10 font-sans">
      {/* Header */}
      <div className="max-w-5xl mx-auto flex items-center justify-between pb-6 border-b border-slate-200 mb-8">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/')}
            className="w-10 h-10 rounded-xl border border-slate-200 bg-white flex items-center justify-center text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition shadow-xs cursor-pointer"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <CloudUpload className="w-5 h-5 text-blue-600" />
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                Upload Master Financial Year Audit Workbook
              </h1>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Single-Workbook Full Audit Ingestion: Upload your client's FY accounts workbook (.xlsx). Captrix automatically reads all sheets and executes statutory audit procedures in one single pass.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-50 border border-blue-200 text-blue-700 text-xs font-semibold">
            <ShieldCheck className="w-4 h-4 text-blue-600" />
            <span>ICAI SA 230 Compliant Ingestion</span>
          </div>
        </div>
      </div>

      {/* Main Upload Card */}
      <div className="max-w-5xl mx-auto bg-white rounded-3xl border border-slate-200/90 p-8 shadow-sm">
        {/* Error Alert */}
        {errorMsg && (
          <div className="mb-6 p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Audit Context Configuration */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1.5 flex items-center gap-1.5">
              <Building2 className="w-3.5 h-3.5 text-blue-600" />
              <span>Company Legal Name</span>
            </label>
            <input
              type="text"
              placeholder="e.g. Acme Ltd (or auto-infer)"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 transition"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1.5">
              Financial Year
            </label>
            <input
              type="text"
              placeholder="e.g. FY 2024-25"
              value={financialYear}
              onChange={(e) => setFinancialYear(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 transition"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1.5">
              Engagement Type
            </label>
            <select
              value={auditType}
              onChange={(e) => setAuditType(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 transition"
            >
              <option value="STATUTORY">Statutory Audit (Companies Act 2013)</option>
              <option value="TAX">Tax Audit (Section 44AB / Form 3CD)</option>
              <option value="INTERNAL">Internal Audit (Risk & Controls)</option>
              <option value="BANK">Bank Concurrent Audit</option>
              <option value="STOCK">Stock & Working Capital Audit</option>
              <option value="LLP">LLP Statutory Audit</option>
            </select>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1.5 flex items-center justify-between">
              <span>Business Scale Tier</span>
              <span className="text-[10px] text-blue-600 font-normal">Auto-detected from Turnover</span>
            </label>
            <select
              value={businessTier}
              onChange={(e) => setBusinessTier(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 transition"
            >
              <option value="AUTO">⚡ Auto-Detect Scale (Automated Scale Detection)</option>
              <option value="TIER_3_MID">Tier 3 — Mid-Market Pvt Ltd (Standard Statutory Audit)</option>
              <option value="TIER_4_ENTERPRISE">Tier 4 — Large Enterprise (Reliance / Listed / Multi-Branch)</option>
              <option value="TIER_2_SME">Tier 2 — SME / LLP (Growing Firm)</option>
              <option value="TIER_1_SMALL">Tier 1 — Small / Sole Prop (Light Scrutiny)</option>
            </select>
          </div>
        </div>

        {/* UNIFIED MASTER AUDIT PACK STATUS & CORE AUDIT AREAS */}
        {stagedFiles.length === 0 ? (
          <div className="mb-6 p-5 rounded-2xl bg-slate-50 border border-slate-200">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-blue-600" />
                <span className="text-xs font-bold text-slate-900">
                  Universal Financial Ingestion (Excel, PDF Statements & ZIP Archives)
                </span>
              </div>
              <span className="text-[11px] font-semibold text-blue-700 bg-blue-50 px-2.5 py-0.5 rounded-full border border-blue-200">
                Direct PDF & Excel Acceptance
              </span>
            </div>
            <p className="text-xs text-slate-600 mb-3.5 leading-relaxed">
              Upload your client's <strong>Financial Master Workbook (.xlsx / .xls)</strong> or <strong>PDF Statements (.pdf)</strong>. Captrix automatically detects document formats, strips header/footer noise and disclaimers, stitches multi-line narrations, and executes statutory audit algorithms across all 6 areas:
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 text-xs">
              <div className="p-3 rounded-xl bg-white border border-slate-200 flex items-center gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <div className="min-w-0">
                  <span className="font-semibold text-slate-800 block truncate">1. Trial Balance (XLSX / PDF)</span>
                  <span className="text-[10px] text-slate-500 block truncate">Schedule III Balancing</span>
                </div>
              </div>
              <div className="p-3 rounded-xl bg-white border border-slate-200 flex items-center gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <div className="min-w-0">
                  <span className="font-semibold text-slate-800 block truncate">2. General Ledger / Daybook</span>
                  <span className="text-[10px] text-slate-500 block truncate">Vouchers & Benford's Law</span>
                </div>
              </div>
              <div className="p-3 rounded-xl bg-white border border-slate-200 flex items-center gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <div className="min-w-0">
                  <span className="font-semibold text-slate-800 block truncate">3. Bank Statements (PDF / XLS)</span>
                  <span className="text-[10px] text-slate-500 block truncate">3-Way BRS Reconciliation</span>
                </div>
              </div>
              <div className="p-3 rounded-xl bg-white border border-slate-200 flex items-center gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <div className="min-w-0">
                  <span className="font-semibold text-slate-800 block truncate">4. Fixed Asset Register</span>
                  <span className="text-[10px] text-slate-500 block truncate">CARO (i) & Depreciation</span>
                </div>
              </div>
              <div className="p-3 rounded-xl bg-white border border-slate-200 flex items-center gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <div className="min-w-0">
                  <span className="font-semibold text-slate-800 block truncate">5. Subledger Aging (MSME)</span>
                  <span className="text-[10px] text-slate-500 block truncate">Sec 43B(h) 45-Day Overdue</span>
                </div>
              </div>
              <div className="p-3 rounded-xl bg-white border border-slate-200 flex items-center gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <div className="min-w-0">
                  <span className="font-semibold text-slate-800 block truncate">6. GSTR-2B & Purchases</span>
                  <span className="text-[10px] text-slate-500 block truncate">Rule 37 180-Day ITC Audit</span>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="mb-6 p-4 rounded-2xl bg-emerald-50 border border-emerald-300 text-emerald-950">
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-2 font-bold text-xs">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>Documents Staged for Audit: {stagedFiles.length === 1 ? stagedFiles[0]?.name : `${stagedFiles.length} Financial Files Ready`}</span>
              </div>
              <span className="px-2.5 py-0.5 rounded-full bg-emerald-200/70 text-emerald-900 text-[10px] font-bold">
                100% Ready for Pipeline Execution
              </span>
            </div>
            <p className="text-xs text-emerald-800 leading-relaxed">
              Captrix will automatically parse all documents (PDF & Excel), eliminate header/footer noise, reconcile transactions, and generate formal Schedule III Balance Sheet, P&L, CARO 2020, and Section 43B(h) audit files.
            </p>
          </div>
        )}

        {/* DROPZONE CONTAINER */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${isDragging
              ? 'border-blue-500 bg-blue-50/60'
              : 'border-slate-300 hover:border-slate-400 bg-slate-50/50 hover:bg-slate-50'
            }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".csv,.xlsx,.xls,.pdf,.png,.jpg,.jpeg,.zip"
            onChange={handleFileSelect}
            className="hidden"
          />

          <div className="w-14 h-14 rounded-2xl bg-blue-50 border border-blue-200 text-blue-600 flex items-center justify-center mx-auto mb-3">
            <CloudUpload className="w-7 h-7" />
          </div>

          <h3 className="text-base font-bold text-slate-900 mb-1">
            Drag & drop Client Financial Master Documents (.xlsx, .xls, .pdf, .zip) here
          </h3>
          <p className="text-xs text-slate-500 max-w-lg mx-auto mb-3">
            Upload your client's FY financial accounts workbook or statutory PDF statements. All records (Trial Balance, General Ledger, Bank Statements, FAR, MSME Aging, GSTR-2B) will be cleaned of noise and audited with 100% mathematical precision.
          </p>

          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white border border-slate-200 text-slate-500 text-[11px] shadow-xs">
            <span>Supports: .xlsx, .xls, .csv, .pdf, .zip</span>
            <span>•</span>
            <span>Intelligent Noise Filtering & Multi-Line OCR</span>
            <span>•</span>
            <span>Up to 250MB</span>
          </div>
        </div>

        {/* STAGED DOCUMENTS LIST */}
        {stagedFiles.length > 0 && (
          <div className="mt-6">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Staged Documents for Processing ({stagedFiles.length})</span>
              </span>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="text-xs text-blue-600 hover:text-blue-700 font-semibold flex items-center gap-1 transition cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add More Files</span>
                </button>
                <span className="text-slate-300">|</span>
                <button
                  onClick={() => setStagedFiles([])}
                  className="text-xs text-rose-600 hover:text-rose-700 font-medium transition cursor-pointer"
                >
                  Clear All
                </button>
              </div>
            </div>

            <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
              {stagedFiles.map((file, idx) => {
                const inferred = inferDocType(file.name);
                const isZip = file.name.toLowerCase().endsWith('.zip');
                return (
                  <div
                    key={`${file.name}-${idx}`}
                    className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      {isZip ? (
                        <FileArchive className="w-4 h-4 text-indigo-600 shrink-0" />
                      ) : file.name.endsWith('.pdf') ? (
                        <FileText className="w-4 h-4 text-rose-600 shrink-0" />
                      ) : (
                        <FileSpreadsheet className="w-4 h-4 text-emerald-600 shrink-0" />
                      )}
                      <span className="text-slate-900 font-medium truncate max-w-xs">{file.name}</span>
                      <span className="text-slate-500 text-[11px] shrink-0">
                        ({(file.size / 1024).toFixed(1)} KB)
                      </span>
                      <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 text-[10px] font-semibold shrink-0">
                        {(file.name.endsWith('.xlsx') || file.name.endsWith('.xls'))
                          ? 'Master Audit Workbook (All Sheets)'
                          : file.name.endsWith('.pdf')
                            ? `${inferred.label} (PDF - Auto-Filtered)`
                            : inferred.label}
                      </span>
                    </div>

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeFile(idx);
                      }}
                      className="text-slate-400 hover:text-rose-600 transition p-1 cursor-pointer"
                      title="Remove file"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* START PIPELINE ACTION BAR */}
        <div className="mt-8 pt-6 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>Files remain byte-for-byte immutable with SHA-256 integrity verification</span>
          </div>

          <button
            onClick={handleStartProcessing}
            disabled={isLoading || stagedFiles.length === 0}
            className={`w-full sm:w-auto px-6 py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition shadow-sm ${stagedFiles.length === 0 || isLoading
                ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white shadow-blue-500/20 cursor-pointer'
              }`}
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Launching 14-Stage Audit Pipeline...</span>
              </>
            ) : (
              <>
                <span>Start Automated Audit Processing</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      </div>

    </div>
  );
};

export default UploadPage;
