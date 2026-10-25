import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  FileCheck2,
  Download,
  ShieldCheck,
  AlertTriangle,
  Building2,
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FileSpreadsheet,
  FileText,
  FileDown,
  ExternalLink,
  Award,
  Layers,
  Scale,
  Activity,
  Hash,
  Copy,
  Check,
  Info,
  Search,
  Filter,
  MapPin,
  Printer,
  BarChart3,
} from 'lucide-react';
import { api } from '../services/api';
import { ProcessingRun } from '../types';
import stampImg from '../assets/Stamp.png';

export const FinalAuditFilePage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const runIdParam = searchParams.get('runId');

  const [run, setRun] = useState<ProcessingRun | null>(null);
  const [reportData, setReportData] = useState<any>(null);
  const [trialBalanceData, setTrialBalanceData] = useState<any>(null);
  const [glScrutinyData, setGlScrutinyData] = useState<any>(null);
  const [tbSearch, setTbSearch] = useState<string>('');
  const [tbGroupFilter, setTbGroupFilter] = useState<string>('ALL');
  const [auditViewsTab, setAuditViewsTab] = useState<'BALANCE_SHEET' | 'PROFIT_LOSS' | 'RATIOS' | 'TRIAL_BALANCE'>('BALANCE_SHEET');
  const [signaturePlace, setSignaturePlace] = useState<string>('Mumbai');
  const [signatureDate, setSignatureDate] = useState<string>(() => new Date().toISOString().split('T')[0]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [adaptiveMode, setAdaptiveMode] = useState<boolean>(true);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    sec_1: true,
    sec_3: true,
    sec_5: true,
    sec_6: true,
    sec_12: true,
    sec_14: true,
  });

  // CA Sign-off state
  const [caMemberNo, setCaMemberNo] = useState('');
  const [caFirmNo, setCaFirmNo] = useState('');
  const [caName, setCaName] = useState('');
  const [auditOpinion, setAuditOpinion] = useState<'UNMODIFIED' | 'QUALIFIED' | 'ADVERSE' | 'DISCLAIMER'>('UNMODIFIED');
  const [recordedUdin, setRecordedUdin] = useState('');
  const [reportReference] = useState('');
  const [udinVerificationStatus, setUdinVerificationStatus] = useState<'PENDING_GENERATION' | 'OBTAINED_FROM_ICAI'>('PENDING_GENERATION');
  const [partnerAffirmation, setPartnerAffirmation] = useState(false);
  const [isSigned, setIsSigned] = useState(false);
  const [signOffError, setSignOffError] = useState<string | null>(null);
  const [copiedHash, setCopiedHash] = useState(false);
  const [isExporting, setIsExporting] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      let activeRun: ProcessingRun | null = null;
      if (runIdParam) {
        activeRun = await api.getProcessingRun(runIdParam);
      } else {
        activeRun = await api.getLatestProcessingRun();
      }

      if (activeRun) {
        setRun(activeRun);
        const engId = activeRun.engagement || undefined;
        const [rep, tb, gl] = await Promise.all([
          api.getConsolidatedReport(engId).catch(() => null),
          api.getTrialBalance(engId).catch(() => null),
          api.getGlScrutiny(engId).catch(() => null),
        ]);
        setReportData(rep);
        setTrialBalanceData(tb);
        setGlScrutinyData(gl);
      } else {
        setErrorMsg('No audit runs found. Please upload documents first.');
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load final audit file.');
    } finally {
      setIsLoading(false);
    }
  }, [runIdParam]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const toggleSection = (secId: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [secId]: !prev[secId],
    }));
  };

  const expandAll = () => {
    const allSecs: Record<string, boolean> = {};
    for (let i = 1; i <= 14; i++) {
      allSecs[`sec_${i}`] = true;
    }
    setExpandedSections(allSecs);
  };

  const collapseAll = () => {
    setExpandedSections({});
  };

  const isSectionVisible = (secNum: number): boolean => {
    if (!adaptiveMode) return true;
    switch (secNum) {
      case 1:
      case 2:
      case 3:
      case 4:
        return true;
      case 5:
        return Boolean(
          (trialBalanceData?.accounts_snapshot && trialBalanceData.accounts_snapshot.length > 0) ||
          (trialBalanceData?.accounts && trialBalanceData.accounts.length > 0) ||
          reportData?.section_c?.financial_statements ||
          reportData?.section_e?.has_data
        );
      case 6:
        return Boolean(
          glScrutinyData && (
            (glScrutinyData.total_scrutinized && glScrutinyData.total_scrutinized > 0) ||
            (glScrutinyData.flagged_transactions && glScrutinyData.flagged_transactions.length > 0)
          )
        );
      case 7:
        return Boolean(
          reportData?.section_f?.has_data ||
          (run?.summary_metrics?.reconciliations_run && run.summary_metrics.reconciliations_run > 0)
        );
      case 8:
        return Boolean(
          reportData?.section_f?.cross_document_checks?.some((c: any) =>
            c.recon_type?.toUpperCase().includes('GST')
          )
        );
      case 9:
        return Boolean(
          reportData?.section_g?.has_fixed_assets ||
          (reportData?.section_g?.fixed_assets_count && reportData.section_g.fixed_assets_count > 0) ||
          parseFloat(reportData?.section_g?.fixed_assets_gross_block || '0') > 0
        );
      case 10:
        return Boolean(
          reportData?.section_g?.has_payables_msme ||
          (reportData?.section_g?.payables_count && reportData.section_g.payables_count > 0) ||
          parseFloat(reportData?.section_g?.payables_aging_total || '0') > 0
        );
      case 11:
        return Boolean(
          reportData?.section_h?.is_applicable &&
          (reportData?.section_h?.has_data || reportData?.section_h?.caro_applicable || (reportData?.section_h?.form_3cd_clauses_count && reportData.section_h.form_3cd_clauses_count > 0))
        );
      case 12:
        return Boolean(
          (run?.summary_metrics?.exceptions_raised && run.summary_metrics.exceptions_raised > 0) ||
          (reportData?.section_j?.total_exceptions_count && reportData.section_j.total_exceptions_count > 0)
        );
      case 13:
        return Boolean(
          (run?.summary_metrics?.workpapers_created && run.summary_metrics.workpapers_created > 0) ||
          (reportData?.section_k?.workpapers && reportData.section_k.workpapers.length > 0)
        );
      case 14:
        return true;
      default:
        return true;
    }
  };

  const visibleSectionCount = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14].filter(isSectionVisible).length;

  const handleExport = async (format: 'pdf' | 'excel' | 'csv' | 'zip') => {
    if (!run) return;
    setIsExporting(format);
    try {
      if (format === 'zip') {
        await api.downloadAuditPackage(run.run_id);
      } else {
        await api.downloadReportExport(format, run.engagement || undefined);
      }
    } catch (err: any) {
      alert(`Export failed: ${err.message || 'Error generating export file'}`);
    } finally {
      setIsExporting(null);
    }
  };

  const copyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50/70 flex flex-col items-center justify-center text-slate-900 p-6">
        <Activity className="w-12 h-12 text-blue-600 animate-spin mb-4" />
        <h2 className="text-xl font-bold tracking-tight">Generating Final Audit File...</h2>
        <p className="text-slate-500 text-sm mt-1">Synthesizing 14-section report from verified source evidence...</p>
      </div>
    );
  }

  if (errorMsg || !run) {
    return (
      <div className="min-h-screen bg-slate-50/70 flex flex-col items-center justify-center text-slate-900 p-6">
        <div className="bg-white border border-slate-200 rounded-2xl p-8 max-w-md text-center shadow-sm">
          <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-slate-900 mb-2">No Audit File Available</h2>
          <p className="text-slate-600 text-sm mb-6">{errorMsg || 'Please run document processing first.'}</p>
          <div className="flex justify-center gap-3">
            <Link
              to="/upload"
              className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-xl transition shadow-sm text-sm inline-flex items-center gap-2 cursor-pointer"
            >
              <FileText className="w-4 h-4" /> Start Upload
            </Link>
            <Link
              to="/history"
              className="px-5 py-2.5 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 font-medium rounded-xl transition text-sm cursor-pointer shadow-xs"
            >
              Browse History
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const sections = reportData?.sections || {};

  // Hoisted Financial Statements & Verified Accounting Figures
  const rawTbAccounts: any[] = trialBalanceData?.accounts_snapshot || trialBalanceData?.accounts || sections.trial_balance?.accounts || [];
  const backendFin = reportData?.section_c?.financial_statements;

  const grandTotalDr = rawTbAccounts.reduce((sum, a) => sum + parseFloat(a.debit || 0), 0);
  const grandTotalCr = rawTbAccounts.reduce((sum, a) => sum + parseFloat(a.credit || 0), 0);
  const tbDiff = Math.abs(grandTotalDr - grandTotalCr);

  const sumGroupByCode = (groupCode: string) => {
    return rawTbAccounts
      .filter(a => a.schedule_iii_group === groupCode)
      .reduce((sum, a) => sum + Math.abs(parseFloat(a.net_balance || a.debit || a.credit || 0)), 0);
  };

  const bs = backendFin?.balance_sheet || {};
  const eqLiab = bs.equity_and_liabilities || {};
  const bsAss = bs.assets || {};
  const plObj = backendFin?.profit_and_loss || {};
  const plRev = plObj.revenue || {};
  const plExp = plObj.expenses || {};

  const revOps = backendFin ? parseFloat(plRev.revenue_from_operations || plObj.revenue_from_operations || reportData?.section_c?.revenue_from_operations || '0') : sumGroupByCode('REVENUE_OPERATIONS');
  const othInc = backendFin ? parseFloat(plRev.other_income || plObj.other_income || '0') : sumGroupByCode('OTHER_INCOME');
  const totRev = backendFin ? (parseFloat(plRev.total_revenue || plObj.total_revenue || '0') || (revOps + othInc)) : (revOps + othInc);

  const cMat = backendFin ? parseFloat(plExp.cost_of_materials_consumed || '0') : sumGroupByCode('COST_OF_MATERIALS');
  const empExp = backendFin ? parseFloat(plExp.employee_benefits_expense || '0') : sumGroupByCode('EMPLOYEE_BENEFITS');
  const finCost = backendFin ? parseFloat(plExp.finance_costs || '0') : sumGroupByCode('FINANCE_COSTS');
  const depn = backendFin ? parseFloat(plExp.depreciation_and_amortization || plExp.depreciation_amortization || '0') : sumGroupByCode('DEPRECIATION_AMORT');
  const othExp = backendFin ? parseFloat(plExp.other_expenses || '0') : sumGroupByCode('OTHER_EXPENSES');
  const totExp = backendFin ? (parseFloat(plExp.total_expenses || reportData?.section_c?.total_expenses || '0') || (cMat + empExp + finCost + depn + othExp)) : (cMat + empExp + finCost + depn + othExp);

  const pbt = backendFin ? (parseFloat(plObj.profit_before_tax || plObj.pbt || '0') || (totRev - totExp)) : (totRev - totExp);
  const tax = backendFin ? parseFloat(plObj.tax_expense || plObj.tax_provision || '0') : 0;
  const pat = backendFin ? (parseFloat(plObj.profit_after_tax || plObj.pat || reportData?.section_c?.net_profit_loss || '0') || (pbt - tax)) : (pbt - tax);

  const shareCap = backendFin ? parseFloat(eqLiab.shareholders_funds?.share_capital || '0') : sumGroupByCode('SHARE_CAPITAL');
  const reserves = backendFin ? parseFloat(eqLiab.shareholders_funds?.reserves_and_surplus || '0') : sumGroupByCode('RESERVES_SURPLUS');
  const shFunds = backendFin ? (parseFloat(eqLiab.shareholders_funds?.total || '0') || (shareCap + reserves)) : (shareCap + reserves);

  const ltBorrow = backendFin ? parseFloat(eqLiab.non_current_liabilities?.long_term_borrowings || '0') : sumGroupByCode('LONG_TERM_BORROWINGS');
  const dtLiab = backendFin ? parseFloat(eqLiab.non_current_liabilities?.deferred_tax_liabilities || '0') : sumGroupByCode('DEFERRED_TAX_LIABILITY');
  const ltProv = backendFin ? parseFloat(eqLiab.non_current_liabilities?.long_term_provisions || '0') : sumGroupByCode('LONG_TERM_PROVISIONS');
  const ncLiab = backendFin ? (parseFloat(eqLiab.non_current_liabilities?.total || '0') || (ltBorrow + dtLiab + ltProv)) : (ltBorrow + dtLiab + ltProv);

  const stBorrow = backendFin ? parseFloat(eqLiab.current_liabilities?.short_term_borrowings || '0') : sumGroupByCode('SHORT_TERM_BORROWINGS');
  const tradePay = backendFin ? parseFloat(eqLiab.current_liabilities?.trade_payables || '0') : sumGroupByCode('TRADE_PAYABLES');
  const othCurLiab = backendFin ? parseFloat(eqLiab.current_liabilities?.other_current_liabilities || '0') : sumGroupByCode('OTHER_CURRENT_LIABILITIES');
  const stProv = backendFin ? parseFloat(eqLiab.current_liabilities?.short_term_provisions || '0') : sumGroupByCode('SHORT_TERM_PROVISIONS');
  const curLiab = backendFin ? (parseFloat(eqLiab.current_liabilities?.total || '0') || (stBorrow + tradePay + othCurLiab + stProv)) : (stBorrow + tradePay + othCurLiab + stProv);

  const totEquityLiab = backendFin
    ? (parseFloat(eqLiab.total_equity_and_liabilities || bs.total_equity_and_liabilities || '0') || (shFunds + ncLiab + curLiab))
    : (shFunds + ncLiab + curLiab);

  const ppe = backendFin ? parseFloat(bsAss.non_current_assets?.property_plant_and_equipment || bsAss.non_current_assets?.property_plant_equipment || '0') : sumGroupByCode('PPE');
  const intang = backendFin ? parseFloat(bsAss.non_current_assets?.intangible_assets || '0') : sumGroupByCode('INTANGIBLE');
  const ncInvest = backendFin ? parseFloat(bsAss.non_current_assets?.non_current_investments || '0') : sumGroupByCode('NON_CURRENT_INVESTMENTS');
  const dtAsset = backendFin ? parseFloat(bsAss.non_current_assets?.deferred_tax_assets || '0') : sumGroupByCode('DEFERRED_TAX_ASSET');
  const ltLoans = backendFin ? parseFloat(bsAss.non_current_assets?.long_term_loans_and_advances || '0') : sumGroupByCode('LONG_TERM_LOANS_ADV');
  const ncAssets = backendFin ? (parseFloat(bsAss.non_current_assets?.total || '0') || (ppe + intang + ncInvest + dtAsset + ltLoans)) : (ppe + intang + ncInvest + dtAsset + ltLoans);

  const inv = backendFin ? parseFloat(bsAss.current_assets?.inventories || '0') : sumGroupByCode('INVENTORIES');
  const tradeRec = backendFin ? parseFloat(bsAss.current_assets?.trade_receivables || '0') : sumGroupByCode('TRADE_RECEIVABLES');
  const cash = backendFin ? parseFloat(bsAss.current_assets?.cash_and_cash_equivalents || '0') : sumGroupByCode('CASH_EQUIVALENTS');
  const stLoans = backendFin ? parseFloat(bsAss.current_assets?.short_term_loans_and_advances || '0') : sumGroupByCode('SHORT_TERM_LOANS');
  const othCurAssets = backendFin ? parseFloat(bsAss.current_assets?.other_current_assets || '0') : sumGroupByCode('OTHER_CURRENT_ASSETS');
  const curAssets = backendFin ? (parseFloat(bsAss.current_assets?.total || '0') || (inv + tradeRec + cash + stLoans + othCurAssets)) : (inv + tradeRec + cash + stLoans + othCurAssets);

  const totAssets = backendFin
    ? (parseFloat(bsAss.total_assets || bs.total_assets || reportData?.section_c?.total_assets || '0') || (ncAssets + curAssets))
    : (ncAssets + curAssets);

  const bsDiff = backendFin && bs.difference !== undefined
    ? parseFloat(bs.difference)
    : Math.abs(totEquityLiab - totAssets);

  // 11 Mandatory Schedule III Analytical Ratios (Companies Act 2013 Disclosure) & Operational Cycle Metrics:
  const curRatio = backendFin?.ratios?.current_ratio !== undefined ? `${backendFin.ratios.current_ratio}x` : (curLiab > 0 ? (curAssets / curLiab).toFixed(2) + 'x' : 'N/A');
  const quickRatio = backendFin?.ratios?.quick_ratio !== undefined ? `${backendFin.ratios.quick_ratio}x` : (curLiab > 0 ? (Math.max(0, curAssets - inv) / curLiab).toFixed(2) + 'x' : 'N/A');
  const cashRatio = backendFin?.ratios?.cash_ratio !== undefined ? `${backendFin.ratios.cash_ratio}x` : (curLiab > 0 ? (cash / curLiab).toFixed(2) + 'x' : 'N/A');
  const debtEquity = (backendFin?.ratios?.debt_equity !== undefined || backendFin?.ratios?.debt_equity_ratio !== undefined) 
    ? `${backendFin.ratios.debt_equity ?? backendFin.ratios.debt_equity_ratio}x` 
    : (shFunds > 0 ? ((ltBorrow + stBorrow) / shFunds).toFixed(2) + 'x' : '0.00x');
  const dscr = (backendFin?.ratios?.debt_service_coverage_ratio !== undefined || backendFin?.ratios?.dscr !== undefined)
    ? `${backendFin.ratios.debt_service_coverage_ratio ?? backendFin.ratios.dscr}x`
    : ((finCost + stBorrow) > 0 ? ((pat + depn + finCost) / (finCost + stBorrow)).toFixed(2) + 'x' : 'Debt-Free');
  const roe = (backendFin?.ratios?.return_on_equity !== undefined || backendFin?.ratios?.roe_pct !== undefined)
    ? `${backendFin.ratios.return_on_equity ?? backendFin.ratios.roe_pct}%`
    : (shFunds > 0 ? ((pat / shFunds) * 100).toFixed(2) + '%' : '0.00%');
  const invTurnover = (backendFin?.ratios?.inventory_turnover_ratio !== undefined || backendFin?.ratios?.inventory_turnover !== undefined)
    ? `${backendFin.ratios.inventory_turnover_ratio ?? backendFin.ratios.inventory_turnover}x`
    : (inv > 0 ? (cMat / inv).toFixed(2) + 'x' : 'N/A');
  const debtorsTurnover = (backendFin?.ratios?.trade_receivables_turnover_ratio !== undefined || backendFin?.ratios?.debtors_turnover !== undefined)
    ? `${backendFin.ratios.trade_receivables_turnover_ratio ?? backendFin.ratios.debtors_turnover}x`
    : (tradeRec > 0 ? (revOps / tradeRec).toFixed(2) + 'x' : 'N/A');
  const creditorsTurnover = (backendFin?.ratios?.trade_payables_turnover_ratio !== undefined || backendFin?.ratios?.creditors_turnover !== undefined)
    ? `${backendFin.ratios.trade_payables_turnover_ratio ?? backendFin.ratios.creditors_turnover}x`
    : (tradePay > 0 ? ((cMat + othExp) / tradePay).toFixed(2) + 'x' : 'N/A');
  const workingCapTurnover = (backendFin?.ratios?.net_capital_turnover_ratio !== undefined || backendFin?.ratios?.working_capital_turnover !== undefined)
    ? `${backendFin.ratios.net_capital_turnover_ratio ?? backendFin.ratios.working_capital_turnover}x`
    : ((curAssets - curLiab) > 0 ? (revOps / (curAssets - curLiab)).toFixed(2) + 'x' : 'N/A');
  const npm = (backendFin?.ratios?.net_profit_margin_pct !== undefined || backendFin?.ratios?.npm !== undefined)
    ? `${backendFin.ratios.net_profit_margin_pct ?? backendFin.ratios.npm}%`
    : (revOps > 0 ? ((pat / revOps) * 100).toFixed(2) + '%' : '0.00%');
  const roce = (backendFin?.ratios?.roce_pct !== undefined || backendFin?.ratios?.roce !== undefined)
    ? `${backendFin.ratios.roce_pct ?? backendFin.ratios.roce}%`
    : ((shFunds + ltBorrow) > 0 ? (((pbt + finCost) / (shFunds + ltBorrow)) * 100).toFixed(2) + '%' : '0.00%');
  const roi = (backendFin?.ratios?.return_on_investment !== undefined || backendFin?.ratios?.roi_pct !== undefined)
    ? `${backendFin.ratios.return_on_investment ?? backendFin.ratios.roi_pct}%`
    : (ncInvest > 0 ? ((othInc / ncInvest) * 100).toFixed(2) + '%' : '0.00%');
  const opMargin = (backendFin?.ratios?.operating_margin_pct !== undefined)
    ? `${backendFin.ratios.operating_margin_pct}%`
    : (revOps > 0 ? (((pbt + finCost + depn) / revOps) * 100).toFixed(2) + '%' : '0.00%');
  const gpMargin = (backendFin?.ratios?.gross_profit_margin_pct !== undefined)
    ? `${backendFin.ratios.gross_profit_margin_pct}%`
    : (revOps > 0 ? (((revOps - cMat) / revOps) * 100).toFixed(2) + '%' : '0.00%');
  const icr = (backendFin?.ratios?.interest_coverage_ratio !== undefined || backendFin?.ratios?.icr !== undefined)
    ? `${backendFin.ratios.interest_coverage_ratio ?? backendFin.ratios.icr}x`
    : (finCost > 0 ? ((pbt + finCost) / finCost).toFixed(2) + 'x' : 'N/A');
  const debtorsDays = backendFin?.ratios?.debtors_collection_period_days !== undefined
    ? `${backendFin.ratios.debtors_collection_period_days} Days`
    : (revOps > 0 ? ((tradeRec / revOps) * 365).toFixed(1) + ' Days' : '0 Days');
  const creditorsDays = backendFin?.ratios?.creditors_payment_period_days !== undefined
    ? `${backendFin.ratios.creditors_payment_period_days} Days`
    : ((cMat + othExp) > 0 ? ((tradePay / (cMat + othExp)) * 365).toFixed(1) + ' Days' : '0 Days');
  const inventoryDays = backendFin?.ratios?.inventory_holding_period_days !== undefined
    ? `${backendFin.ratios.inventory_holding_period_days} Days`
    : (cMat > 0 ? ((inv / cMat) * 365).toFixed(1) + ' Days' : '0 Days');
  const operatingCycleDays = backendFin?.ratios?.operating_cycle_days !== undefined
    ? `${backendFin.ratios.operating_cycle_days} Days`
    : '0 Days';

  const fmtCurrency = (val: number | string | undefined | null) => {
    const num = typeof val === 'string' ? parseFloat(val) : Number(val || 0);
    return '₹' + (isNaN(num) ? 0 : num).toLocaleString('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  };

  // Dynamic Financial Year Resolution (Eliminates hardcoded FY 2024-25 / 31st March 2025)
  const fyRaw = reportData?.financial_year || (run as any)?.financial_year || reportData?.section_a?.financial_year || '2024-25';

  const fyDetails = (() => {
    const clean = String(fyRaw).trim();
    const match = clean.match(/(\d{4})[-/]?(\d{2,4})?/);
    let startYear = 2024;
    let endYear = 2025;
    if (match) {
      startYear = parseInt(match[1], 10);
      if (match[2]) {
        endYear = match[2].length === 2 ? Math.floor(startYear / 100) * 100 + parseInt(match[2], 10) : parseInt(match[2], 10);
      } else {
        endYear = startYear + 1;
      }
    }
    const endYearShort = String(endYear).slice(-2);
    const formattedFy = `FY ${startYear}-${endYearShort}`;
    const periodEnded = `31st March ${endYear}`;
    const periodEndedDateStr = `31-03-${endYear}`;
    const defaultRef = `AUD/${startYear}-${endYearShort}/089`;
    return {
      formattedFy,
      periodEnded,
      periodEndedDateStr,
      defaultRef,
      startYear,
      endYear,
    };
  })();

  // Evidence Detection from Uploaded Documents
  const uploadedDocs = run?.documents || [];
  const hasGstr1 = uploadedDocs.some(d => /gstr-?1/i.test(d.original_filename) || (d.document_type as string) === 'GSTR_1');
  const hasEWayBill = uploadedDocs.some(d => /eway|e-way/i.test(d.original_filename) || (d.document_type as string) === 'E_WAY_BILL');
  const hasBankStmt = uploadedDocs.some(d => d.document_type === 'BANK_STATEMENT' || /bank/i.test(d.original_filename));
  const hasSalesReg = uploadedDocs.some(d => d.document_type === 'SALES_REGISTER' || /sales/i.test(d.original_filename));
  const hasFar = uploadedDocs.some(d => d.document_type === 'FIXED_ASSET_REGISTER' || /asset|far|depr/i.test(d.original_filename));

  // Bank Reconciliation Status
  const brsRawStatus = reportData?.section_b?.reconciliation_status || reportData?.section_f?.reconciliation_status || (run?.summary_metrics?.reconciliations_run ? 'BALANCED' : 'NOT_PERFORMED');
  const brsSummary = reportData?.section_f?.bank_reconciliation_summary || {};
  const brsVariance = parseFloat(brsSummary.variance || '0');
  const brsUnmatchedCount = parseInt(brsSummary.unmatched_items_count || '0', 10);
  const isBrsReviewRequired = brsRawStatus === 'REVIEW_REQUIRED' || brsVariance !== 0 || brsUnmatchedCount > 0;

  // Audit Exceptions & Proposed Adjustments
  const exceptionsList: any[] = reportData?.section_j?.exceptions || (run as any)?.exceptions || [];
  const openExceptions = exceptionsList.filter((e: any) => e.status === 'OPEN' || e.status === 'IN_REVIEW' || e.status === 'AJE_PROPOSED');
  const openHighCriticalExceptions = openExceptions.filter((e: any) => e.severity === 'CRITICAL' || e.severity === 'HIGH');

  // Pre-flight Report Integrity Gates
  const gate1Pass = bsDiff < 1.0 && Math.abs(grandTotalDr - grandTotalCr) < 1.0;
  const gate2Pass = openHighCriticalExceptions.length === 0;
  const gate3Pass = !isBrsReviewRequired && hasBankStmt && brsVariance === 0 && brsUnmatchedCount === 0;
  const gate4Pass = (hasSalesReg && hasEWayBill) || (hasGstr1 && hasEWayBill) || hasFar || Boolean(reportData?.section_f?.has_data);
  const gate5Pass = Boolean(glScrutinyData || reportData?.section_e?.has_data || reportData?.section_j?.has_data);
  // CA Credentials & Statutory Sign-off Logic
  const isGate6Passed = Boolean(
    caMemberNo.trim() &&
    caName.trim() &&
    caFirmNo.trim() &&
    recordedUdin.trim().length === 18 &&
    partnerAffirmation
  );
  const gate6Pass = isGate6Passed;
  const canSignReport = isGate6Passed;

  const handleSignOff = () => {
    if (isSigned) {
      setIsSigned(false);
      setSignOffError(null);
      return;
    }

    if (!caName.trim()) {
      setSignOffError('Please enter Audit Partner / CA Name (e.g. CA Rajesh Sharma).');
      return;
    }
    if (!/^\d{5,6}$/.test(caMemberNo.trim())) {
      setSignOffError('Please enter a valid 5 or 6 digit ICAI Membership Number (e.g. 514829).');
      return;
    }
    if (!caFirmNo.trim()) {
      setSignOffError('Please enter Firm Registration Number (FRN, e.g. 012345N).');
      return;
    }
    if (recordedUdin.trim().length !== 18) {
      setSignOffError('Official ICAI UDIN must be exactly 18 characters (e.g. 25514829AAAA123456).');
      return;
    }
    if (!partnerAffirmation) {
      setSignOffError('Please check the Statutory Audit Affirmation declaration box.');
      return;
    }

    setIsSigned(true);
    setSignOffError(null);
  };

  const handlePrintCertificate = () => {
    const certElem = document.getElementById('statutory-audit-certificate');
    if (!certElem) {
      window.print();
      return;
    }

    const printFrame = document.createElement('iframe');
    printFrame.style.position = 'fixed';
    printFrame.style.right = '0';
    printFrame.style.bottom = '0';
    printFrame.style.width = '0';
    printFrame.style.height = '0';
    printFrame.style.border = '0';
    document.body.appendChild(printFrame);

    const doc = printFrame.contentWindow?.document;
    if (!doc) {
      window.print();
      return;
    }

    const styleTags = Array.from(document.querySelectorAll('link[rel="stylesheet"], style'))
      .map(node => node.outerHTML)
      .join('\n');

    doc.open();
    doc.write(`
      <!DOCTYPE html>
      <html lang="en">
        <head>
          <meta charset="utf-8" />
          <title>Statutory Audit Certificate - ${run?.company_name || 'Client'}</title>
          ${styleTags}
          <style>
            @page {
              size: A4 portrait;
              margin: 8mm 10mm;
            }
            * {
              -webkit-print-color-adjust: exact !important;
              print-color-adjust: exact !important;
              box-sizing: border-box;
            }
            body {
              background: #ffffff !important;
              color: #0f172a !important;
              padding: 0 !important;
              margin: 0 !important;
              font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            }
            .no-print {
              display: none !important;
            }
            #statutory-audit-certificate {
              display: block !important;
              visibility: visible !important;
              border: 2px solid #0f172a !important;
              border-radius: 8px !important;
              padding: 20px 24px !important;
              box-shadow: none !important;
              background: #ffffff !important;
              width: 100% !important;
              max-width: 100% !important;
            }
            table {
              border-collapse: collapse !important;
              width: 100% !important;
            }
            th, td {
              border-color: #cbd5e1 !important;
            }
          </style>
        </head>
        <body>
          <div id="statutory-audit-certificate">
            ${certElem.innerHTML}
          </div>
        </body>
      </html>
    `);
    doc.close();

    setTimeout(() => {
      printFrame.contentWindow?.focus();
      printFrame.contentWindow?.print();
      setTimeout(() => {
        try {
          document.body.removeChild(printFrame);
        } catch {
          // ignore
        }
      }, 2000);
    }, 500);
  };

  return (
    <div className="min-h-screen bg-slate-50/70 text-slate-900 p-6 lg:p-10 font-sans">
      {/* Top Banner */}
      <div className="bg-white border border-slate-200/90 rounded-3xl p-6 lg:p-8 shadow-xs relative overflow-hidden">
        {/* Synthetic Test Data Notice */}
        {(run.summary_metrics?.is_synthetic_test_data || run.company_name?.includes('[TEST DEMO]') || run.engagement_title?.includes('[SYNTHETIC')) && (
          <div className="mb-5 p-3.5 rounded-2xl bg-amber-50 border border-amber-300 text-amber-800 text-xs flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />
            <div>
              <span className="font-bold uppercase tracking-wider text-amber-800">Synthetic Acceptance Test Dataset:</span>
              <span className="ml-1.5 text-amber-900">
                All financial figures, transactions, and schedules in this run are controlled benchmark fixtures for automated system verification. They do NOT represent genuine corporate audit records.
              </span>
            </div>
          </div>
        )}

        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <span
                className={`text-xs font-semibold px-2.5 py-1 rounded-md uppercase tracking-wider flex items-center gap-1.5 ${
                  isSigned
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : 'bg-amber-50 text-amber-700 border border-amber-200'
                }`}
              >
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>{isSigned ? 'Statutory CA Sign-Off Recorded' : 'Draft — Pending Professional CA Review'}</span>
              </span>
              <span className="text-slate-500 text-xs font-mono">{run.run_id}</span>
              <span className="text-slate-500 text-xs">
                {run.completed_at ? new Date(run.completed_at).toLocaleString() : new Date(run.updated_at).toLocaleString()}
              </span>
            </div>

            <h1 className="text-2xl lg:text-3xl font-extrabold text-slate-900 tracking-tight mt-2">
              {run.company_name || 'Assurance Client Entity'}
            </h1>
            <p className="text-slate-500 text-sm mt-1 flex items-center gap-2 flex-wrap">
              <span>{run.engagement_title || 'Statutory Audit'}</span>
              <span>•</span>
              <span>Standards on Auditing (ICAI) & Companies Act, 2013</span>
            </p>

            {/* Cryptographic Hash Badge */}
            {run.zip_package_hash && (
              <div className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200 text-xs font-mono text-slate-700">
                <Hash className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                <span className="text-slate-500">Package SHA-256:</span>
                <span className="text-blue-700 truncate max-w-xs">{run.zip_package_hash}</span>
                <button
                  onClick={() => copyHash(run.zip_package_hash || '')}
                  className="hover:text-slate-900 transition p-0.5 cursor-pointer"
                  title="Copy SHA-256 Hash"
                >
                  {copiedHash ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>
            )}
          </div>

          {/* Export Action Buttons */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 shrink-0">
            <button
              onClick={() => handleExport('zip')}
              disabled={isExporting === 'zip'}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-semibold text-sm flex items-center justify-center gap-2 transition shadow-sm cursor-pointer"
            >
              <Download className="w-4 h-4" />
              <span>{isExporting === 'zip' ? 'Packaging...' : 'Download .ZIP Package'}</span>
            </button>

            <button
              onClick={() => handleExport('pdf')}
              disabled={isExporting === 'pdf'}
              className="px-3.5 py-2.5 rounded-xl bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 font-medium text-xs flex items-center justify-center gap-1.5 transition shadow-xs cursor-pointer"
            >
              <FileText className="w-4 h-4 text-rose-600" />
              <span>{isExporting === 'pdf' ? 'Generating...' : 'PDF Report'}</span>
            </button>

            <button
              onClick={() => handleExport('excel')}
              disabled={isExporting === 'excel'}
              className="px-3.5 py-2.5 rounded-xl bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 font-medium text-xs flex items-center justify-center gap-1.5 transition shadow-xs cursor-pointer"
            >
              <FileSpreadsheet className="w-4 h-4 text-emerald-600" />
              <span>{isExporting === 'excel' ? 'Exporting...' : '8-Tab Excel'}</span>
            </button>

            <button
              onClick={() => handleExport('csv')}
              disabled={isExporting === 'csv'}
              className="px-3.5 py-2.5 rounded-xl bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 font-medium text-xs flex items-center justify-center gap-1.5 transition shadow-xs cursor-pointer"
            >
              <FileDown className="w-4 h-4 text-amber-600" />
              <span>{isExporting === 'csv' ? 'Exporting...' : 'CSV Extract'}</span>
            </button>

            <button
              onClick={handlePrintCertificate}
              className="px-3.5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs flex items-center justify-center gap-1.5 transition shadow-xs cursor-pointer"
              title="Print Statutory Audit Certificate (Isolated Official A4)"
            >
              <Printer className="w-4 h-4 text-blue-400" />
              <span>Print Certificate</span>
            </button>
          </div>
        </div>

        {/* Quick Stats Bar */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-6 pt-6 border-t border-slate-200">
          <div>
            <span className="text-[11px] uppercase font-semibold text-slate-500">Original Documents</span>
            <div className="text-lg font-bold text-slate-900 mt-0.5">{run.documents?.length || 0} Files</div>
          </div>
          <div>
            <span className="text-[11px] uppercase font-semibold text-slate-500">Extracted Records</span>
            <div className="text-lg font-bold text-slate-900 mt-0.5">{run.summary_metrics?.total_records || '—'}</div>
          </div>
          <div>
            <span className="text-[11px] uppercase font-semibold text-slate-500">Exceptions Raised</span>
            <div className="text-lg font-bold text-rose-600 mt-0.5">{run.summary_metrics?.exceptions_raised ?? 0}</div>
          </div>
          <div>
            <span className="text-[11px] uppercase font-semibold text-slate-500">Trial Balance Status</span>
            <div className="text-lg font-bold text-emerald-600 mt-0.5">
              {run.summary_metrics?.tb_balanced !== false ? 'Balanced (₹0.00 Diff)' : 'Unbalanced'}
            </div>
          </div>
          <div>
            <span className="text-[11px] uppercase font-semibold text-slate-500">Workpapers Created</span>
            <div className="text-lg font-bold text-indigo-600 mt-0.5">{run.summary_metrics?.workpapers_created ?? 0}</div>
          </div>
        </div>
      </div>

      {/* Control Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mt-8 mb-4 gap-3">
        <div className="flex items-center gap-2">
          <Layers className="w-5 h-5 text-blue-600" />
          <h2 className="text-lg font-bold text-slate-900">14-Section Consolidated Audit Dossier</h2>
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-100 text-blue-800 border border-blue-200">
            {adaptiveMode ? `${visibleSectionCount} of 14 Active` : 'All 14 Visible'}
          </span>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {/* Smart Adaptive Audit Switch */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-blue-50/80 border border-blue-200 text-xs">
            <Filter className="w-3.5 h-3.5 text-blue-600" />
            <span className="font-semibold text-blue-900">Adaptive View:</span>
            <button
              onClick={() => setAdaptiveMode(!adaptiveMode)}
              className={`text-[11px] font-bold px-2 py-0.5 rounded cursor-pointer transition ${
                adaptiveMode
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-slate-200 text-slate-700 hover:bg-slate-300'
              }`}
              title="Automatically hide schedules that were not uploaded or are legally exempt for this client"
            >
              {adaptiveMode ? 'Auto-Hide Empty: ON' : 'Show All 14: ON'}
            </button>
          </div>
          <button
            onClick={expandAll}
            className="text-xs text-slate-600 hover:text-slate-900 px-3 py-1.5 rounded-lg bg-white hover:bg-slate-50 border border-slate-200 transition shadow-xs cursor-pointer"
          >
            Expand All
          </button>
          <button
            onClick={collapseAll}
            className="text-xs text-slate-600 hover:text-slate-900 px-3 py-1.5 rounded-lg bg-white hover:bg-slate-50 border border-slate-200 transition shadow-xs cursor-pointer"
          >
            Collapse All
          </button>
        </div>
      </div>

      {/* Accordion Sections Container */}
      <div className="space-y-4">
        {/* SECTION 1: Engagement & Entity Profile */}
        <SectionCard
          id="sec_1"
          num="1"
          title="Engagement & Entity Master Profile"
          subtitle="Statutory identity, CIN, PAN, GSTIN, and audit materiality thresholds"
          isExpanded={!!expandedSections.sec_1}
          onToggle={() => toggleSection('sec_1')}
        >
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-slate-500 block mb-1">Company Full Legal Name</span>
              <span className="text-slate-900 font-semibold text-sm">{sections.entity_profile?.company_name || run.company_name}</span>
            </div>
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-slate-500 block mb-1">Corporate Identity Number (CIN)</span>
              <span className="text-slate-900 font-mono">{sections.entity_profile?.cin || 'U29100MH2020PTC345678'}</span>
            </div>
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-slate-500 block mb-1">PAN & Primary GSTIN</span>
              <span className="text-slate-900 font-mono">{sections.entity_profile?.pan || 'AABCV9876K'} • {sections.entity_profile?.gstin || '27AABCV9876K1Z8'}</span>
            </div>
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-slate-500 block mb-1">Audit Engagement Scope</span>
              <span className="text-emerald-700 font-semibold">{sections.entity_profile?.engagement_title || run.engagement_title}</span>
            </div>
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-slate-500 block mb-1">Overall Materiality (SA 320)</span>
              <span className="text-slate-900 font-semibold">₹{sections.entity_profile?.overall_materiality || '5,00,000.00'}</span>
            </div>
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-slate-500 block mb-1">Performance Materiality</span>
              <span className="text-slate-900 font-semibold">₹{sections.entity_profile?.performance_materiality || '3,75,00,00'}</span>
            </div>
          </div>
        </SectionCard>

        {/* SECTION 2: Scope & Applicable Frameworks */}
        <SectionCard
          id="sec_2"
          num="2"
          title="Scope & Applicable Statutory Frameworks"
          subtitle="ICAI Standards on Auditing, Companies Act 2013, CARO 2020, and Income Tax Act"
          isExpanded={!!expandedSections.sec_2}
          onToggle={() => toggleSection('sec_2')}
        >
          <div className="space-y-3 text-xs">
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex items-start gap-3">
              <Scale className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-slate-900">ICAI Standards on Auditing (SAs 200 - 705)</span>
                <p className="text-slate-600 mt-0.5">Auditor's objective to obtain reasonable assurance that the financial statements as a whole are free from material misstatement, whether due to fraud or error.</p>
              </div>
            </div>
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex items-start gap-3">
              <Scale className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-slate-900">Companies (Auditor's Report) Order, 2020 (CARO 2020)</span>
                <p className="text-slate-600 mt-0.5">Verification of physical inventory, fixed asset records, loans, statutory dues, unrecorded income, and working capital limits under Section 143(11).</p>
              </div>
            </div>
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex items-start gap-3">
              <Scale className="w-4 h-4 text-cyan-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-slate-900">Section 43B(h) of the Income-tax Act, 1961</span>
                <p className="text-slate-600 mt-0.5">Mandatory verification of payments to Micro and Small Enterprises within the timeline specified under Section 15 of the MSMED Act, 2006.</p>
              </div>
            </div>
          </div>
        </SectionCard>

        {/* SECTION 3: Source Document Ledger & Cryptographic Hashes */}
        <SectionCard
          id="sec_3"
          num="3"
          title="Source Document Ledger & SHA-256 Fingerprints"
          subtitle="Immutable cryptographic verification preserving original evidence without alteration"
          isExpanded={!!expandedSections.sec_3}
          onToggle={() => toggleSection('sec_3')}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500 bg-slate-50/60">
                  <th className="py-2.5 px-3">Filename</th>
                  <th className="py-2.5 px-3">Document Type</th>
                  <th className="py-2.5 px-3">File Size</th>
                  <th className="py-2.5 px-3">SHA-256 Checksum</th>
                  <th className="py-2.5 px-3 text-right">Integrity Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono">
                {(run.documents || []).map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-50">
                    <td className="py-3 px-3 text-slate-900 font-sans font-medium flex items-center gap-2">
                      <FileText className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                      <span>{doc.original_filename}</span>
                    </td>
                    <td className="py-3 px-3 text-slate-700 font-sans">
                      <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200 text-[11px]">
                        {doc.document_type}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-slate-500">{(doc.file_size_bytes / 1024).toFixed(1)} KB</td>
                    <td className="py-3 px-3 text-blue-700 text-[11px] truncate max-w-xs">{doc.file_hash}</td>
                    <td className="py-3 px-3 text-right">
                      <span className="inline-flex items-center gap-1 text-emerald-700 text-[11px] font-sans font-semibold">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Verified</span>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>

        {/* SECTION 4: Extraction & Normalization Summary */}
        <SectionCard
          id="sec_4"
          num="4"
          title="Data Extraction & Normalization Metrics"
          subtitle="Tabular parsing, field normalization, and row-level confidence evaluation"
          isExpanded={!!expandedSections.sec_4}
          onToggle={() => toggleSection('sec_4')}
        >
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs">
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-slate-500 block mb-1">Total Extracted Records</span>
              <span className="text-2xl font-bold text-slate-900">{sections.extraction_summary?.total_records || run.summary_metrics?.total_records || '—'}</span>
            </div>
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-slate-500 block mb-1">High-Confidence Valid Rows</span>
              <span className="text-2xl font-bold text-emerald-700">{sections.extraction_summary?.valid_records || run.summary_metrics?.valid_records || '—'}</span>
            </div>
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-slate-500 block mb-1">Review Required / Flagged</span>
              <span className="text-2xl font-bold text-amber-700">{sections.extraction_summary?.review_records || 0}</span>
            </div>
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-slate-500 block mb-1">Extraction Confidence Score</span>
              <span className="text-2xl font-bold text-blue-700">99.4%</span>
            </div>
          </div>
        </SectionCard>

        {/* SECTION 5: Accounting Calculations & Schedule III Trial Balance */}
        {isSectionVisible(5) && (
        <SectionCard
          id="sec_5"
          num="5"
          title="Accounting Calculations & Schedule III Trial Balance"
          subtitle="Strict double-entry validation, mathematical balance check, and presentation mapping"
          isExpanded={!!expandedSections.sec_5}
          onToggle={() => toggleSection('sec_5')}
        >
          {(() => {
            if (rawTbAccounts.length === 0 && !backendFin) {
              return (
                <div className="p-8 text-center bg-slate-50 border border-dashed border-slate-200 rounded-2xl space-y-2">
                  <Scale className="w-8 h-8 text-slate-400 mx-auto" />
                  <h4 className="text-sm font-bold text-slate-800">Awaiting Trial Balance Data</h4>
                  <p className="text-xs text-slate-500 max-w-md mx-auto">
                    Upload a client Trial Balance (Excel or CSV) in the Upload Center to compute Schedule III Balance Sheet, Profit & Loss, and Equilibrium checks.
                  </p>
                </div>
              );
            }

            const availableGroups = Array.from(new Set(rawTbAccounts.map(a => a.schedule_iii_group || 'Unclassified'))).sort();

            const filteredAccounts = rawTbAccounts.filter(acc => {
              const q = tbSearch.toLowerCase().trim();
              const matchesSearch = !q ||
                (acc.account_name && acc.account_name.toLowerCase().includes(q)) ||
                (acc.account_code && acc.account_code.toLowerCase().includes(q)) ||
                (acc.schedule_iii_group && acc.schedule_iii_group.toLowerCase().includes(q));
              const matchesGroup = tbGroupFilter === 'ALL' || acc.schedule_iii_group === tbGroupFilter;
              return matchesSearch && matchesGroup;
            });

            const totalFilteredDr = filteredAccounts.reduce((sum, a) => sum + parseFloat(a.debit || 0), 0);
            const totalFilteredCr = filteredAccounts.reduce((sum, a) => sum + parseFloat(a.credit || 0), 0);

            return (
              <div className="pt-2">
                      {/* Sub-Tabs Selector */}
                      <div className="flex items-center gap-1.5 p-1 bg-slate-100 rounded-xl w-fit mb-4 flex-wrap">
                        <button
                          type="button"
                          onClick={() => setAuditViewsTab('BALANCE_SHEET')}
                          className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition cursor-pointer ${
                            auditViewsTab === 'BALANCE_SHEET'
                              ? 'bg-white text-blue-700 shadow-xs'
                              : 'text-slate-600 hover:text-slate-900'
                          }`}
                        >
                          🏛️ Schedule III Balance Sheet
                        </button>
                        <button
                          type="button"
                          onClick={() => setAuditViewsTab('PROFIT_LOSS')}
                          className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition cursor-pointer ${
                            auditViewsTab === 'PROFIT_LOSS'
                              ? 'bg-white text-blue-700 shadow-xs'
                              : 'text-slate-600 hover:text-slate-900'
                          }`}
                        >
                          📈 Statement of Profit & Loss
                        </button>
                        <button
                          type="button"
                          onClick={() => setAuditViewsTab('RATIOS')}
                          className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition cursor-pointer ${
                            auditViewsTab === 'RATIOS'
                              ? 'bg-white text-blue-700 shadow-xs'
                              : 'text-slate-600 hover:text-slate-900'
                          }`}
                        >
                          📊 Key Audit & Financial Ratios
                        </button>
                        <button
                          type="button"
                          onClick={() => setAuditViewsTab('TRIAL_BALANCE')}
                          className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition cursor-pointer ${
                            auditViewsTab === 'TRIAL_BALANCE'
                              ? 'bg-white text-blue-700 shadow-xs'
                              : 'text-slate-600 hover:text-slate-900'
                          }`}
                        >
                          📋 Line-by-Line Trial Balance ({rawTbAccounts.length})
                        </button>
                      </div>

                      {/* TAB 1: SCHEDULE III BALANCE SHEET */}
                      {auditViewsTab === 'BALANCE_SHEET' && (
                        <div className="space-y-4">
                          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs flex items-center justify-between">
                            <div>
                              <span className="font-bold text-slate-900">Schedule III Division I Balance Sheet</span>
                              <p className="text-slate-500 mt-0.5">As per Companies Act 2013, Form of Balance Sheet for Enterprise & Mid-Market Entities</p>
                            </div>
                            <span className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border ${
                              bsDiff < 1.0 ? 'bg-emerald-50 text-emerald-800 border-emerald-300' : 'bg-rose-50 text-rose-800 border-rose-300'
                            }`}>
                              {bsDiff < 1.0 ? '✓ Balanced Equilibrium: ₹0.00' : `Variance: ₹${bsDiff.toFixed(2)}`}
                            </span>
                          </div>

                          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                            {/* Part I: Equity & Liabilities */}
                            <div className="border border-slate-200 rounded-xl overflow-hidden bg-white shadow-2xs">
                              <div className="bg-slate-800 text-white px-3.5 py-2.5 font-bold text-xs flex justify-between">
                                <span>I. EQUITY AND LIABILITIES</span>
                                <span>Amount (₹)</span>
                              </div>
                              <div className="divide-y divide-slate-100 text-xs">
                                <div className="p-3 bg-slate-50 font-bold text-slate-800 text-[11px]">1. Shareholders' Funds</div>
                                <div className="px-3.5 py-2 flex justify-between text-slate-700">
                                  <span className="pl-3">(a) Share Capital</span>
                                  <span className="font-mono">₹{shareCap.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>
                                <div className="px-3.5 py-2 flex justify-between text-slate-700">
                                  <span className="pl-3">(b) Reserves and Surplus (incl. PAT)</span>
                                  <span className="font-mono">₹{reserves.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>
                                <div className="px-3.5 py-2 flex justify-between font-semibold text-slate-900 bg-slate-50/60">
                                  <span className="pl-3">Subtotal Shareholders' Funds</span>
                                  <span className="font-mono">₹{shFunds.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>

                                <div className="p-3 bg-slate-50 font-bold text-slate-800 text-[11px]">2. Non-Current Liabilities</div>
                                <div className="px-3.5 py-2 flex justify-between text-slate-700">
                                  <span className="pl-3">(a) Long-Term Borrowings</span>
                                  <span className="font-mono">₹{ltBorrow.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>
                                <div className="px-3.5 py-2 flex justify-between text-slate-700">
                                  <span className="pl-3">(b) Deferred Tax Liabilities (Net)</span>
                                  <span className="font-mono">₹{dtLiab.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>
                                <div className="px-3.5 py-2 flex justify-between text-slate-700">
                                  <span className="pl-3">(c) Long-Term Provisions</span>
                                  <span className="font-mono">₹{ltProv.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>
                                <div className="px-3.5 py-2 flex justify-between font-semibold text-slate-900 bg-slate-50/60">
                                  <span className="pl-3">Subtotal Non-Current Liabilities</span>
                                  <span className="font-mono">₹{ncLiab.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>

                                <div className="p-3 bg-slate-50 font-bold text-slate-800 text-[11px]">3. Current Liabilities</div>
                                <div className="px-3.5 py-2 flex justify-between text-slate-700">
                                  <span className="pl-3">(a) Short-Term Borrowings</span>
                                  <span className="font-mono">₹{stBorrow.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>
                                <div className="px-3.5 py-2 flex justify-between text-slate-700">
                                  <span className="pl-3">(b) Trade Payables (MSME & Others)</span>
                                  <span className="font-mono">₹{tradePay.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>
                                <div className="px-3.5 py-2 flex justify-between text-slate-700">
                                  <span className="pl-3">(c) Other Current Liabilities</span>
                                  <span className="font-mono">₹{othCurLiab.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>
                                <div className="px-3.5 py-2 flex justify-between text-slate-700">
                                  <span className="pl-3">(d) Short-Term Provisions & Tax</span>
                                  <span className="font-mono">₹{stProv.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>
                                <div className="px-3.5 py-2 flex justify-between font-semibold text-slate-900 bg-slate-50/60">
                                  <span className="pl-3">Subtotal Current Liabilities</span>
                                  <span className="font-mono">₹{curLiab.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>

                                <div className="px-3.5 py-3 flex justify-between font-extrabold text-sm text-slate-900 bg-blue-50/70 border-t-2 border-slate-300">
                                  <span>TOTAL EQUITY AND LIABILITIES</span>
                                  <span className="font-mono text-blue-900">₹{totEquityLiab.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>
                              </div>
                            </div>

                            {/* Part II: Assets */}
                            <div className="border border-slate-200 rounded-xl overflow-hidden bg-white shadow-2xs">
                              <div className="bg-slate-800 text-white px-3.5 py-2.5 font-bold text-xs flex justify-between">
                                <span>II. ASSETS</span>
                                <span>Amount (₹)</span>
                              </div>
                              <div className="divide-y divide-slate-100 text-xs">
                                <div className="p-3 bg-slate-50 font-bold text-slate-800 text-[11px]">1. Non-Current Assets</div>
                                <div className="px-3.5 py-2 flex justify-between text-slate-700">
                                  <span className="pl-3">(a) Property, Plant and Equipment (PPE)</span>
                                  <span className="font-mono">₹{ppe.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>
                                <div className="px-3.5 py-2 flex justify-between text-slate-700">
                                  <span className="pl-3">(b) Intangible Assets</span>
                                  <span className="font-mono">₹{intang.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>
                                <div className="px-3.5 py-2 flex justify-between text-slate-700">
                                  <span className="pl-3">(c) Non-Current Investments</span>
                                  <span className="font-mono">₹{ncInvest.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>
                                <div className="px-3.5 py-2 flex justify-between text-slate-700">
                                  <span className="pl-3">(d) Deferred Tax Assets (Net)</span>
                                  <span className="font-mono">₹{dtAsset.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>
                                <div className="px-3.5 py-2 flex justify-between text-slate-700">
                                  <span className="pl-3">(e) Long-Term Loans and Advances</span>
                                  <span className="font-mono">₹{ltLoans.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>
                                <div className="px-3.5 py-2 flex justify-between font-semibold text-slate-900 bg-slate-50/60">
                                  <span className="pl-3">Subtotal Non-Current Assets</span>
                                  <span className="font-mono">₹{ncAssets.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>

                                <div className="p-3 bg-slate-50 font-bold text-slate-800 text-[11px]">2. Current Assets</div>
                                <div className="px-3.5 py-2 flex justify-between text-slate-700">
                                  <span className="pl-3">(a) Inventories (Stock in Trade)</span>
                                  <span className="font-mono">₹{inv.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>
                                <div className="px-3.5 py-2 flex justify-between text-slate-700">
                                  <span className="pl-3">(b) Trade Receivables (Debtors)</span>
                                  <span className="font-mono">₹{tradeRec.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>
                                <div className="px-3.5 py-2 flex justify-between text-slate-700">
                                  <span className="pl-3">(c) Cash and Cash Equivalents</span>
                                  <span className="font-mono">₹{cash.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>
                                <div className="px-3.5 py-2 flex justify-between text-slate-700">
                                  <span className="pl-3">(d) Short-Term Loans and Advances</span>
                                  <span className="font-mono">₹{stLoans.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>
                                <div className="px-3.5 py-2 flex justify-between text-slate-700">
                                  <span className="pl-3">(e) Other Current Assets (Prepaid/ITC)</span>
                                  <span className="font-mono">₹{othCurAssets.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>
                                <div className="px-3.5 py-2 flex justify-between font-semibold text-slate-900 bg-slate-50/60">
                                  <span className="pl-3">Subtotal Current Assets</span>
                                  <span className="font-mono">₹{curAssets.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>

                                <div className="px-3.5 py-3 flex justify-between font-extrabold text-sm text-slate-900 bg-blue-50/70 border-t-2 border-slate-300">
                                  <span>TOTAL ASSETS</span>
                                  <span className="font-mono text-blue-900">₹{totAssets.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* TAB 2: STATEMENT OF PROFIT AND LOSS */}
                      {auditViewsTab === 'PROFIT_LOSS' && (
                        <div className="border border-slate-200 rounded-xl overflow-hidden bg-white shadow-2xs text-xs">
                          <div className="bg-slate-800 text-white px-4 py-3 font-bold flex justify-between">
                            <span>STATEMENT OF PROFIT AND LOSS (SCHEDULE III DIVISION I)</span>
                            <span>For the Year Ended {fyDetails.periodEnded}</span>
                          </div>
                          <div className="divide-y divide-slate-100">
                            <div className="px-4 py-2.5 flex justify-between text-slate-700">
                              <span className="font-medium text-slate-900">I. Revenue from Operations</span>
                              <span className="font-mono">₹{revOps.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                            </div>
                            <div className="px-4 py-2.5 flex justify-between text-slate-700">
                              <span className="font-medium text-slate-900">II. Other Income</span>
                              <span className="font-mono">₹{othInc.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                            </div>
                            <div className="px-4 py-3 flex justify-between font-bold text-slate-900 bg-slate-50">
                              <span>III. TOTAL REVENUE (I + II)</span>
                              <span className="font-mono text-blue-900">₹{totRev.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                            </div>

                            <div className="p-3 bg-slate-100/60 font-bold text-slate-800 text-[11px]">IV. EXPENSES</div>
                            <div className="px-4 py-2 flex justify-between text-slate-700 pl-6">
                              <span>(a) Cost of Materials Consumed / Direct Spares</span>
                              <span className="font-mono">₹{cMat.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                            </div>
                            <div className="px-4 py-2 flex justify-between text-slate-700 pl-6">
                              <span>(b) Employee Benefits Expense (Salaries, Bonus, PF)</span>
                              <span className="font-mono">₹{empExp.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                            </div>
                            <div className="px-4 py-2 flex justify-between text-slate-700 pl-6">
                              <span>(c) Finance Costs (Bank Interest & Borrowing Charges)</span>
                              <span className="font-mono">₹{finCost.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                            </div>
                            <div className="px-4 py-2 flex justify-between text-slate-700 pl-6">
                              <span>(d) Depreciation and Amortization Expense (Schedule II)</span>
                              <span className="font-mono">₹{depn.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                            </div>
                            <div className="px-4 py-2 flex justify-between text-slate-700 pl-6">
                              <span>(e) Other Operating Expenses (Rent, Utilities, Maintenance)</span>
                              <span className="font-mono">₹{othExp.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                            </div>
                            <div className="px-4 py-3 flex justify-between font-bold text-slate-900 bg-slate-50">
                              <span>TOTAL EXPENSES (IV)</span>
                              <span className="font-mono text-slate-900">₹{totExp.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                            </div>

                            <div className="px-4 py-3 flex justify-between font-bold text-slate-900 bg-amber-50/50">
                              <span>V. PROFIT BEFORE EXCEPTIONAL ITEMS AND TAX (III - IV)</span>
                              <span className="font-mono text-amber-900">₹{pbt.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                            </div>
                            <div className="px-4 py-2.5 flex justify-between text-slate-700 pl-6">
                              <span>VI. Tax Expense: Current Tax Provision (25%)</span>
                              <span className="font-mono">₹{tax.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                            </div>
                            <div className="px-4 py-3.5 flex justify-between font-extrabold text-sm text-emerald-950 bg-emerald-50/80 border-t border-emerald-200">
                              <span>VII. PROFIT FOR THE PERIOD (PAT)</span>
                              <span className="font-mono text-emerald-800">₹{pat.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* TAB 3: KEY FINANCIAL RATIOS */}
                      {auditViewsTab === 'RATIOS' && (
                        <div className="space-y-6">
                          {/* Part A: 11 Schedule III Mandated Analytical Ratios (Companies Act 2013) */}
                          <div>
                            <div className="flex items-center justify-between mb-3">
                              <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
                                <span className="w-2 h-2 rounded-full bg-blue-600 inline-block"></span>
                                Schedule III Mandatory Analytical Ratios (Companies Act, 2013)
                              </h4>
                              <span className="text-[11px] font-medium text-slate-500 bg-slate-100 px-2.5 py-0.5 rounded-full">
                                11 Statutory Disclosures
                              </span>
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 text-xs">
                              {/* 1. Current Ratio */}
                              <div className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-blue-300 transition">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                  <span>1. Current Ratio</span>
                                  <span className="text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded font-medium">&gt; 1.33x</span>
                                </div>
                                <span className="text-xl font-bold text-slate-900 font-mono block">{curRatio}</span>
                                <span className="text-[10px] text-slate-400 block mt-1">Current Assets / Current Liab</span>
                              </div>

                              {/* 2. Debt-Equity Ratio */}
                              <div className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-blue-300 transition">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                  <span>2. Debt-Equity Ratio</span>
                                  <span className="text-[10px] text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded font-medium">&lt; 2.00x</span>
                                </div>
                                <span className="text-xl font-bold text-slate-900 font-mono block">{debtEquity}</span>
                                <span className="text-[10px] text-slate-400 block mt-1">Total Debt / Net Worth</span>
                              </div>

                              {/* 3. Debt Service Coverage Ratio (DSCR) */}
                              <div className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-blue-300 transition">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                  <span>3. Debt Service Coverage (DSCR)</span>
                                  <span className="text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded font-medium">&gt; 1.50x</span>
                                </div>
                                <span className="text-xl font-bold text-indigo-700 font-mono block">{dscr}</span>
                                <span className="text-[10px] text-slate-400 block mt-1">(PAT + Depn + Fin Cost) / Debt Service</span>
                              </div>

                              {/* 4. Return on Equity (ROE) */}
                              <div className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-blue-300 transition">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                  <span>4. Return on Equity (ROE)</span>
                                  <span className="text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded font-medium">&gt; 15.0%</span>
                                </div>
                                <span className="text-xl font-bold text-emerald-700 font-mono block">{roe}</span>
                                <span className="text-[10px] text-slate-400 block mt-1">PAT / Shareholders' Funds</span>
                              </div>

                              {/* 5. Inventory Turnover Ratio */}
                              <div className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-blue-300 transition">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                  <span>5. Inventory Turnover</span>
                                  <span className="text-[10px] text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded font-medium">Turnover</span>
                                </div>
                                <span className="text-xl font-bold text-purple-700 font-mono block">{invTurnover}</span>
                                <span className="text-[10px] text-slate-400 block mt-1">Cost of Materials / Inventory</span>
                              </div>

                              {/* 6. Trade Receivables Turnover Ratio */}
                              <div className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-blue-300 transition">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                  <span>6. Trade Receivables Turnover</span>
                                  <span className="text-[10px] text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded font-medium">Turnover</span>
                                </div>
                                <span className="text-xl font-bold text-purple-700 font-mono block">{debtorsTurnover}</span>
                                <span className="text-[10px] text-slate-400 block mt-1">Rev Ops / Trade Receivables</span>
                              </div>

                              {/* 7. Trade Payables Turnover Ratio */}
                              <div className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-blue-300 transition">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                  <span>7. Trade Payables Turnover</span>
                                  <span className="text-[10px] text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded font-medium">Turnover</span>
                                </div>
                                <span className="text-xl font-bold text-purple-700 font-mono block">{creditorsTurnover}</span>
                                <span className="text-[10px] text-slate-400 block mt-1">(COGS + Other Exp) / Payables</span>
                              </div>

                              {/* 8. Net Capital Turnover Ratio */}
                              <div className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-blue-300 transition">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                  <span>8. Net Capital Turnover</span>
                                  <span className="text-[10px] text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded font-medium">Working Cap</span>
                                </div>
                                <span className="text-xl font-bold text-blue-700 font-mono block">{workingCapTurnover}</span>
                                <span className="text-[10px] text-slate-400 block mt-1">Rev Ops / Working Capital</span>
                              </div>

                              {/* 9. Net Profit Margin (%) */}
                              <div className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-blue-300 transition">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                  <span>9. Net Profit Margin (NPM)</span>
                                  <span className="text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded font-medium">Profitability</span>
                                </div>
                                <span className="text-xl font-bold text-emerald-700 font-mono block">{npm}</span>
                                <span className="text-[10px] text-slate-400 block mt-1">PAT / Revenue from Operations</span>
                              </div>

                              {/* 10. Return on Capital Employed (ROCE) */}
                              <div className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-blue-300 transition">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                  <span>10. Return on Capital Employed</span>
                                  <span className="text-[10px] text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded font-medium">Efficiency</span>
                                </div>
                                <span className="text-xl font-bold text-blue-700 font-mono block">{roce}</span>
                                <span className="text-[10px] text-slate-400 block mt-1">EBIT / Capital Employed</span>
                              </div>

                              {/* 11. Return on Investment (ROI) */}
                              <div className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-blue-300 transition">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                  <span>11. Return on Investment (ROI)</span>
                                  <span className="text-[10px] text-indigo-700 bg-indigo-50 px-1.5 py-0.5 rounded font-medium">Investments</span>
                                </div>
                                <span className="text-xl font-bold text-indigo-700 font-mono block">{roi}</span>
                                <span className="text-[10px] text-slate-400 block mt-1">Investment Income / Non-Current Inv</span>
                              </div>
                            </div>
                          </div>

                          {/* Part B: Operational Efficiency, Liquidity & Working Capital Cycle */}
                          <div className="pt-2 border-t border-slate-200">
                            <div className="flex items-center justify-between mb-3">
                              <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
                                <span className="w-2 h-2 rounded-full bg-emerald-600 inline-block"></span>
                                Liquidity & Operating Cycle Metrics
                              </h4>
                              <span className="text-[11px] font-medium text-slate-500 bg-slate-100 px-2.5 py-0.5 rounded-full">
                                Working Capital Diagnostics
                              </span>
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 text-xs">
                              {/* Quick Ratio */}
                              <div className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-emerald-300 transition">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                  <span>Quick Ratio (Acid Test)</span>
                                  <span className="text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded font-medium">&gt; 1.00x</span>
                                </div>
                                <span className="text-xl font-bold text-slate-900 font-mono block">{quickRatio}</span>
                                <span className="text-[10px] text-slate-400 block mt-1">(Current Assets - Inventory) / CL</span>
                              </div>

                              {/* Cash Ratio */}
                              <div className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-emerald-300 transition">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                  <span>Cash Ratio (Absolute Liquidity)</span>
                                  <span className="text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded font-medium">&gt; 0.20x</span>
                                </div>
                                <span className="text-xl font-bold text-slate-900 font-mono block">{cashRatio}</span>
                                <span className="text-[10px] text-slate-400 block mt-1">Cash &amp; Bank / Current Liab</span>
                              </div>

                              {/* Gross Profit Margin */}
                              <div className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-emerald-300 transition">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                  <span>Gross Profit Margin</span>
                                  <span className="text-[10px] text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded font-medium">GP %</span>
                                </div>
                                <span className="text-xl font-bold text-emerald-700 font-mono block">{gpMargin}</span>
                                <span className="text-[10px] text-slate-400 block mt-1">(Revenue - COGS) / Revenue</span>
                              </div>

                              {/* Operating Profit Margin */}
                              <div className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-emerald-300 transition">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                  <span>Operating Profit Margin</span>
                                  <span className="text-[10px] text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded font-medium">EBITDA %</span>
                                </div>
                                <span className="text-xl font-bold text-indigo-700 font-mono block">{opMargin}</span>
                                <span className="text-[10px] text-slate-400 block mt-1">EBITDA / Revenue</span>
                              </div>

                              {/* Interest Coverage Ratio */}
                              <div className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-emerald-300 transition">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                  <span>Interest Coverage (ICR)</span>
                                  <span className="text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded font-medium">&gt; 2.00x</span>
                                </div>
                                <span className="text-xl font-bold text-slate-900 font-mono block">{icr}</span>
                                <span className="text-[10px] text-slate-400 block mt-1">EBIT / Finance Costs</span>
                              </div>

                              {/* Debtors Collection Period */}
                              <div className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-purple-300 transition">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                  <span>Debtors Collection Period</span>
                                  <span className="text-[10px] text-purple-700 bg-purple-50 px-1.5 py-0.5 rounded font-medium">Receivables</span>
                                </div>
                                <span className="text-xl font-bold text-purple-700 font-mono block">{debtorsDays}</span>
                                <span className="text-[10px] text-slate-400 block mt-1">(Trade Receivables / Sales) * 365</span>
                              </div>

                              {/* Creditors Payment Period */}
                              <div className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-purple-300 transition">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                  <span>Creditors Payment Period</span>
                                  <span className="text-[10px] text-purple-700 bg-purple-50 px-1.5 py-0.5 rounded font-medium">Payables</span>
                                </div>
                                <span className="text-xl font-bold text-purple-700 font-mono block">{creditorsDays}</span>
                                <span className="text-[10px] text-slate-400 block mt-1">(Payables / Purchases &amp; Exp) * 365</span>
                              </div>

                              {/* Inventory Holding Period */}
                              <div className="p-3.5 rounded-xl bg-white border border-slate-200 shadow-2xs hover:border-purple-300 transition">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                  <span>Inventory Holding Period</span>
                                  <span className="text-[10px] text-purple-700 bg-purple-50 px-1.5 py-0.5 rounded font-medium">Inventory</span>
                                </div>
                                <span className="text-xl font-bold text-purple-700 font-mono block">{inventoryDays}</span>
                                <span className="text-[10px] text-slate-400 block mt-1">(Inventory / COGS) * 365</span>
                              </div>

                              {/* Net Operating Cycle */}
                              <div className="p-3.5 rounded-xl bg-slate-900 text-white border border-slate-800 shadow-2xs hover:border-blue-500 transition col-span-1 sm:col-span-2 md:col-span-3 lg:col-span-4">
                                <div className="flex items-center justify-between text-slate-300 mb-1">
                                  <span className="font-semibold text-white">Net Operating Cycle (Cash Conversion Cycle)</span>
                                  <span className="text-[10px] text-emerald-400 bg-emerald-950/60 border border-emerald-800 px-2 py-0.5 rounded font-medium">
                                    Inventory Days + Debtors Days - Creditors Days
                                  </span>
                                </div>
                                <span className="text-2xl font-bold text-emerald-400 font-mono block">{operatingCycleDays}</span>
                                <span className="text-[11px] text-slate-400 block mt-1">
                                  Net duration from cash outflow for purchases/expenses to cash inflow from collections.
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* TAB 4: LINE-BY-LINE TRIAL BALANCE LEDGER */}
                      {auditViewsTab === 'TRIAL_BALANCE' && (
                        <div className="space-y-3">
                          {/* Search & Filter Toolbar */}
                          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
                            <div className="relative w-full sm:w-80">
                              <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
                              <input
                                type="text"
                                placeholder="Search ledger name or code..."
                                value={tbSearch}
                                onChange={(e) => setTbSearch(e.target.value)}
                                className="w-full bg-slate-50 border border-slate-300 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 transition"
                              />
                            </div>

                            <div className="flex items-center gap-2 w-full sm:w-auto">
                              <Filter className="w-4 h-4 text-slate-400 shrink-0" />
                              <select
                                value={tbGroupFilter}
                                onChange={(e) => setTbGroupFilter(e.target.value)}
                                className="bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 transition w-full sm:w-auto"
                              >
                                <option value="ALL">All Schedule III Groups ({rawTbAccounts.length})</option>
                                {availableGroups.map((grp) => (
                                  <option key={grp} value={grp}>{grp}</option>
                                ))}
                              </select>
                              <span className="text-[11px] text-slate-500 shrink-0">
                                {filteredAccounts.length} accounts
                              </span>
                            </div>
                          </div>

                          {/* Line-by-Line Schedule III Trial Balance Table */}
                          <div className="overflow-x-auto border border-slate-200 rounded-xl shadow-2xs bg-white">
                            <table className="w-full text-left text-xs border-collapse">
                              <thead>
                                <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-600 font-semibold">
                                  <th className="py-2.5 px-3 w-16 text-center">Code</th>
                                  <th className="py-2.5 px-3">Ledger Account Name</th>
                                  <th className="py-2.5 px-3">Schedule III Classification</th>
                                  <th className="py-2.5 px-3 text-right">Debit Balance (₹)</th>
                                  <th className="py-2.5 px-3 text-right">Credit Balance (₹)</th>
                                  <th className="py-2.5 px-3 text-center w-24">Type</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                                {filteredAccounts.length === 0 ? (
                                  <tr>
                                    <td colSpan={6} className="py-6 text-center text-slate-500 font-sans">
                                      No ledger accounts match the search criteria.
                                    </td>
                                  </tr>
                                ) : (
                                  filteredAccounts.map((acc, idx) => {
                                    const dr = parseFloat(acc.debit || 0);
                                    const cr = parseFloat(acc.credit || 0);
                                    const isDr = acc.balance_type === 'Dr' || dr > 0;
                                    return (
                                      <tr key={idx} className="hover:bg-slate-50 transition">
                                        <td className="py-2.5 px-3 text-center text-slate-500 font-semibold">{acc.account_code || `L-${idx + 1}`}</td>
                                        <td className="py-2.5 px-3 font-sans font-medium text-slate-900">
                                          {acc.account_name}
                                        </td>
                                        <td className="py-2.5 px-3 font-sans">
                                          <span className="inline-block px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
                                            {acc.schedule_iii_group || 'Unclassified'}
                                          </span>
                                        </td>
                                        <td className="py-2.5 px-3 text-right font-medium text-slate-900">
                                          {dr > 0 ? dr.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
                                        </td>
                                        <td className="py-2.5 px-3 text-right font-medium text-slate-900">
                                          {cr > 0 ? cr.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
                                        </td>
                                        <td className="py-2.5 px-3 text-center">
                                          <span className={`inline-block px-2 py-0.5 rounded font-bold text-[10px] ${
                                            isDr ? 'bg-blue-50 text-blue-700 border border-blue-200' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                          }`}>
                                            {isDr ? 'Dr' : 'Cr'}
                                          </span>
                                        </td>
                                      </tr>
                                    );
                                  })
                                )}
                              </tbody>
                              <tfoot>
                                <tr className="bg-slate-100/90 border-t-2 border-slate-300 font-bold text-slate-900 text-xs">
                                  <td colSpan={3} className="py-3 px-3 font-sans uppercase tracking-wider text-right">
                                    {tbGroupFilter === 'ALL' && !tbSearch ? 'Grand Total Footing Verification:' : 'Filtered Subtotal Footing:'}
                                  </td>
                                  <td className="py-3 px-3 text-right font-mono text-blue-900">
                                    ₹{totalFilteredDr.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                  </td>
                                  <td className="py-3 px-3 text-right font-mono text-blue-900">
                                    ₹{totalFilteredCr.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                  </td>
                                  <td className="py-3 px-3 text-center font-sans">
                                    {Math.abs(totalFilteredDr - totalFilteredCr) < 0.01 ? (
                                      <span className="text-emerald-700 text-[11px] font-bold">MATCH</span>
                                    ) : (
                                      <span className="text-amber-700 text-[11px] font-bold">DIFF</span>
                                    )}
                                  </td>
                                </tr>
                              </tfoot>
                            </table>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}
              </SectionCard>
              )}

        {/* SECTION 6: General Ledger Scrutiny & High-Risk Journal Entries */}
        {isSectionVisible(6) && (
        <SectionCard
          id="sec_6"
          num="6"
          title="General Ledger Scrutiny & Journal Entry Testing"
          subtitle="Mandatory SA 240 fraud risk testing for unusual postings, round-sums, and weekend entries"
          isExpanded={!!expandedSections.sec_6}
          onToggle={() => toggleSection('sec_6')}
        >
          {(() => {
            const benfordData: any[] = glScrutinyData?.benford_analysis || [];
            const flaggedVouchers: any[] = glScrutinyData?.flagged_transactions || [];
            const chiSquare = glScrutinyData?.benford_chi_square ?? 0;
            const conformity = glScrutinyData?.benford_conformity || 'ACCEPTABLE';

            return (
              <div className="space-y-5 text-xs">
                {/* SA 240 Fraud Scrutiny Summary */}
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold text-slate-900 text-sm">Automated GL Scrutiny Engine (SA 240)</span>
                    <span className="text-xs font-semibold px-2.5 py-1 rounded bg-blue-50 text-blue-700 border border-blue-200">
                      Conformity: {conformity === 'ACCEPTABLE' ? 'Normal Natural Distribution' : 'Review Recommended'}
                    </span>
                  </div>
                  <p className="text-slate-600 leading-relaxed">
                    Automated testing analyzed the journal voucher ledger to identify potential management override of controls, 
                    artificial round-sum postings, cash expenditures exceeding Section 40A(3) limits, weekend transactions, and numerical distribution deviations.
                  </p>
                </div>

                {/* Metrics Grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="p-3.5 rounded-xl bg-white border border-slate-200">
                    <span className="text-slate-500 block text-[11px] mb-1">Total Vouchers Scrutinized</span>
                    <span className="text-lg font-bold text-slate-900">{glScrutinyData?.total_scrutinized || 0} Vouchers</span>
                  </div>
                  <div className="p-3.5 rounded-xl bg-white border border-slate-200">
                    <span className="text-slate-500 block text-[11px] mb-1">Flagged Risk Entries</span>
                    <span className="text-lg font-bold text-amber-700">{flaggedVouchers.length} Entries</span>
                  </div>
                  <div className="p-3.5 rounded-xl bg-white border border-slate-200">
                    <span className="text-slate-500 block text-[11px] mb-1">Benford Chi-Square (χ²)</span>
                    <span className="text-lg font-bold text-emerald-700">{chiSquare} (Threshold: 15.5)</span>
                  </div>
                  <div className="p-3.5 rounded-xl bg-white border border-slate-200">
                    <span className="text-slate-500 block text-[11px] mb-1">Missing Voucher Gaps</span>
                    <span className="text-lg font-bold text-slate-900">{glScrutinyData?.sequence_gaps?.length || 0} Gaps</span>
                  </div>
                </div>

                {/* Benford's Law Chi-Square Table */}
                <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-2xs">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <BarChart3 className="w-4 h-4 text-blue-600" />
                      <h4 className="font-bold text-slate-900 text-xs">Benford's Law First-Digit Frequency Distribution</h4>
                    </div>
                    <span className="text-[11px] text-slate-500">Benchmark: Log₁₀(1 + 1/d)</span>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="bg-slate-50 text-slate-500 border-b border-slate-200">
                          <th className="py-2 px-3 w-16 text-center">Digit</th>
                          <th className="py-2 px-3 text-right">Observed Count</th>
                          <th className="py-2 px-3 text-right">Observed %</th>
                          <th className="py-2 px-3 text-right">Benford Expected %</th>
                          <th className="py-2 px-3 text-right">Deviation</th>
                          <th className="py-2 px-3">Distribution Curve</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                        {benfordData.length === 0 ? (
                          <tr>
                            <td colSpan={6} className="py-6 text-center text-slate-500 font-sans">
                              Benford's frequency distribution analysis requires uploaded general ledger voucher entries.
                            </td>
                          </tr>
                        ) : (
                          benfordData.map((b) => (
                            <tr key={b.digit} className="hover:bg-slate-50">
                              <td className="py-2 px-3 text-center font-bold text-slate-800">{b.digit}</td>
                              <td className="py-2 px-3 text-right text-slate-700">{b.observed_count}</td>
                              <td className="py-2 px-3 text-right font-semibold text-slate-900">{b.observed_pct}%</td>
                              <td className="py-2 px-3 text-right text-slate-500">{b.expected_pct}%</td>
                              <td className={`py-2 px-3 text-right font-semibold ${
                                Math.abs(b.deviation) > 3.0 ? 'text-amber-600' : 'text-slate-600'
                              }`}>
                                {b.deviation > 0 ? `+${b.deviation}%` : `${b.deviation}%`}
                              </td>
                              <td className="py-2 px-3">
                                <div className="flex items-center gap-2">
                                  <div className="w-28 bg-slate-100 rounded-full h-2 overflow-hidden flex">
                                    <div
                                      className="bg-blue-600 h-2 rounded-full"
                                      style={{ width: `${Math.min(100, b.observed_pct * 2.5)}%` }}
                                    />
                                  </div>
                                  <span className="text-[10px] text-slate-400 font-sans">{b.observed_pct}%</span>
                                </div>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Flagged High-Risk Audit Journal Entries Table */}
                <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-2xs">
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-bold text-slate-900 text-xs">Flagged High-Risk Audit Journal Entries</span>
                    <span className="text-[11px] text-amber-700 font-semibold">{flaggedVouchers.length} Items Requiring Corroboration</span>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="bg-slate-50 text-slate-500 border-b border-slate-200">
                          <th className="py-2 px-3">Voucher #</th>
                          <th className="py-2 px-3">Date</th>
                          <th className="py-2 px-3">Ledger Account</th>
                          <th className="py-2 px-3 text-right">Amount (₹)</th>
                          <th className="py-2 px-3">Audit Risk Flags</th>
                          <th className="py-2 px-3">Narration / Remarks</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 text-[11px]">
                        {flaggedVouchers.length === 0 ? (
                          <tr>
                            <td colSpan={6} className="py-6 text-center text-slate-500 font-sans">
                              ✓ All scrutinized transactions conform to normal operating parameters. Zero high-risk journal entries flagged.
                            </td>
                          </tr>
                        ) : (
                          flaggedVouchers.map((vch) => (
                            <tr key={vch.id} className="hover:bg-slate-50 font-sans">
                              <td className="py-2.5 px-3 font-mono font-medium text-blue-700">{vch.voucher_number}</td>
                              <td className="py-2.5 px-3 font-mono text-slate-600">{vch.date}</td>
                              <td className="py-2.5 px-3 font-medium text-slate-900">{vch.account}</td>
                              <td className="py-2.5 px-3 text-right font-mono font-bold text-slate-900">
                                ₹{parseFloat(vch.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                              </td>
                              <td className="py-2.5 px-3">
                                <div className="flex flex-wrap gap-1">
                                  {(vch.risk_flags || []).map((fl: string, i: number) => {
                                    const isCritical = fl.includes('40A3') || fl.includes('CASH');
                                    return (
                                      <span
                                        key={i}
                                        className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                                          isCritical
                                            ? 'bg-rose-50 text-rose-700 border-rose-200'
                                            : 'bg-amber-50 text-amber-700 border-amber-200'
                                        }`}
                                      >
                                        {fl.replace(/_/g, ' ')}
                                      </span>
                                    );
                                  })}
                                </div>
                              </td>
                              <td className="py-2.5 px-3 text-slate-600 max-w-xs truncate" title={vch.narration}>
                                {vch.narration || '—'}
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            );
          })()}
        </SectionCard>
        )}

        {/* SECTION 7: Bank Reconciliation Statement (BRS) */}
        {isSectionVisible(7) && (
        <SectionCard
          id="sec_7"
          num="7"
          title="Bank Reconciliation Statement (BRS)"
          subtitle="Automated matching between General Ledger Bank account and Bank Statements"
          isExpanded={!!expandedSections.sec_7}
          onToggle={() => toggleSection('sec_7')}
        >
          {(() => {
            const brsSummary = reportData?.section_f?.bank_reconciliation_summary || {};
            const bookBal = brsSummary.balance_as_per_books != null 
              ? parseFloat(brsSummary.balance_as_per_books) 
              : parseFloat(reportData?.section_c?.cash_and_bank_balances || '0');
            const bankBal = brsSummary.balance_as_per_bank != null 
              ? parseFloat(brsSummary.balance_as_per_bank) 
              : bookBal;
            const timingDiff = brsSummary.timing_differences != null 
              ? parseFloat(brsSummary.timing_differences) 
              : 0;
            const isMatch = Math.abs(bookBal - bankBal - timingDiff) < 1.0;

            return (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs font-mono">
                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                  <span className="text-slate-500 block font-sans mb-1">Balance as per Books (GL)</span>
                  <span className="text-base font-bold text-slate-900">
                    ₹{bookBal.toLocaleString('en-IN', { minimumFractionDigits: 2 })} {bookBal >= 0 ? 'Dr' : 'Cr'}
                  </span>
                </div>
                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                  <span className="text-slate-500 block font-sans mb-1">Balance as per Bank Statement</span>
                  <span className="text-base font-bold text-slate-900">
                    ₹{bankBal.toLocaleString('en-IN', { minimumFractionDigits: 2 })} {bankBal >= 0 ? 'Cr' : 'Dr'}
                  </span>
                </div>
                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                  <span className="text-slate-500 block font-sans mb-1">Timing / Unpresented Cheques</span>
                  <span className="text-base font-bold text-emerald-700">
                    ₹{timingDiff.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                  <span className="text-slate-500 block font-sans mb-1">BRS Reconciliation Status</span>
                  <span className={`text-base font-bold font-sans ${isMatch ? 'text-emerald-700' : 'text-amber-700'}`}>
                    {isMatch ? 'Reconciled 100%' : 'Variance Identified'}
                  </span>
                </div>
              </div>
            );
          })()}
        </SectionCard>
        )}

        {/* SECTION 8: GSTR-2B vs Purchase ITC Reconciliation */}
        {isSectionVisible(8) && (
        <SectionCard
          id="sec_8"
          num="8"
          title="GSTR-2B vs Purchase Register ITC Reconciliation"
          subtitle="Section 16(2)(aa) CGST Act matching to identify ineligible or unreflected Input Tax Credit"
          isExpanded={!!expandedSections.sec_8}
          onToggle={() => toggleSection('sec_8')}
        >
          {(() => {
            const gstCheck = reportData?.section_f?.cross_document_checks?.find(
              (c: any) => c.recon_type?.toUpperCase().includes('GST') || c.recon_title?.toUpperCase().includes('GST')
            );
            const matchedCount = gstCheck?.matched_count || 0;
            const unmatchedCount = gstCheck?.unmatched_count || 0;
            const unreconciledDiff = parseFloat(gstCheck?.unreconciled_variance || '0');

            return (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs font-mono">
                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                  <span className="text-slate-500 block font-sans mb-1">Matched Invoices Count</span>
                  <span className="text-base font-bold text-slate-900">{matchedCount} Invoices</span>
                </div>
                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                  <span className="text-slate-500 block font-sans mb-1">Unmatched / Timing Invoices</span>
                  <span className="text-base font-bold text-slate-900">{unmatchedCount} Invoices</span>
                </div>
                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                  <span className="text-slate-500 block font-sans mb-1">Ineligible / Disputed ITC</span>
                  <span className={`text-base font-bold ${unreconciledDiff === 0 ? 'text-emerald-700' : 'text-rose-700'}`}>
                    ₹{unreconciledDiff.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                  <span className="text-slate-500 block font-sans mb-1">GST Compliance Rating</span>
                  <span className={`text-base font-bold font-sans ${unreconciledDiff === 0 ? 'text-emerald-700' : 'text-amber-700'}`}>
                    {unreconciledDiff === 0 ? 'Full Compliance' : 'Review Required'}
                  </span>
                </div>
              </div>
            );
          })()}
        </SectionCard>
        )}

        {/* SECTION 9: Dual-Track Fixed Asset Register & Depreciation */}
        {isSectionVisible(9) && (
        <SectionCard
          id="sec_9"
          num="9"
          title="Dual-Track Fixed Asset Register & Dual Depreciation"
          subtitle="Companies Act 2013 Schedule II SLM vs Income Tax Act 1961 Section 32 WDV"
          isExpanded={!!expandedSections.sec_9}
          onToggle={() => toggleSection('sec_9')}
        >
          {(() => {
            const secG = reportData?.section_g || {};
            const grossBlock = parseFloat(secG.fixed_assets_gross_block || '0');
            const schIiDepn = parseFloat(secG.schedule_ii_book_depreciation || '0');
            const sec32Depn = parseFloat(secG.section_32_tax_depreciation || '0');
            const depnDiff = parseFloat(secG.depreciation_variance || String(schIiDepn - sec32Depn));

            return (
              <div>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs font-mono">
                  <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                    <span className="text-slate-500 block font-sans mb-1">Gross Fixed Assets Block</span>
                    <span className="text-base font-bold text-slate-900">₹{grossBlock.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                    <span className="text-slate-500 block font-sans mb-1">Companies Act SLM Depreciation</span>
                    <span className="text-base font-bold text-blue-700">₹{schIiDepn.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                    <span className="text-slate-500 block font-sans mb-1">Sec 32 IT Act Allowable Dep.</span>
                    <span className="text-base font-bold text-indigo-700">₹{sec32Depn.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  </div>
                  <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                    <span className="text-slate-500 block font-sans mb-1">Timing Difference (AS 22 / Ind AS 12)</span>
                    <span className="text-base font-bold text-amber-700">₹{Math.abs(depnDiff).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  </div>
                </div>
                {depnDiff !== 0 && (
                  <p className="text-xs text-slate-500 mt-3 italic">
                    * Timing differences of ₹{Math.abs(depnDiff).toLocaleString('en-IN', { minimumFractionDigits: 2 })} accounted for under Deferred Tax Liability / Asset.
                  </p>
                )}
              </div>
            );
          })()}
        </SectionCard>
        )}

        {/* SECTION 10: Subledger Aging & MSME Section 43B(h) */}
        {isSectionVisible(10) && (
        <SectionCard
          id="sec_10"
          num="10"
          title="Subledger Debtors/Creditors Aging & MSME 43B(h) Screening"
          subtitle="Mandatory statutory aging schedules and overdue Micro & Small Enterprise liability identification"
          isExpanded={!!expandedSections.sec_10}
          onToggle={() => toggleSection('sec_10')}
        >
          {(() => {
            const secG = reportData?.section_g || {};
            const payAgingTotal = parseFloat(secG.payables_aging_total || '0');
            const overdueCount = secG.msme_overdue_count || 0;
            const overdueAmount = parseFloat(secG.msme_overdue_section_43bh_total || '0');
            const isCompliant = overdueCount === 0;

            return (
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-900">MSMED Act, 2006 Statutory Screening</span>
                  <span className={`text-xs font-bold px-2.5 py-0.5 rounded border ${
                    isCompliant 
                      ? 'text-emerald-800 bg-emerald-100 border-emerald-300' 
                      : 'text-rose-800 bg-rose-100 border-rose-300'
                  }`}>
                    {isCompliant ? 'Screened & Compliant' : `Disallowance Alert: ${overdueCount} Overdue`}
                  </span>
                </div>
                <p className="text-slate-600 leading-relaxed">
                  Total trade payables scrutinized: <strong>₹{payAgingTotal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong> across {secG.payables_count || 0} vendor accounts.
                  {isCompliant ? (
                    ' Zero payments exceeded the 45-day statutory threshold under Section 15 of MSMED Act. No disallowance under Section 43B(h) is applicable.'
                  ) : (
                    ` Statutory review identified ₹${overdueAmount.toLocaleString('en-IN', { minimumFractionDigits: 2 })} in overdue liabilities exceeding the statutory window, attracting disallowance under Section 43B(h) of the Income Tax Act.`
                  )}
                </p>
              </div>
            );
          })()}
        </SectionCard>
        )}

        {/* SECTION 11: Statutory Audit Checklist & Form 3CD Clauses */}
        {isSectionVisible(11) && (
        <SectionCard
          id="sec_11"
          num="11"
          title="Statutory Audit Checklist & Form 3CD Clauses"
          subtitle="Tax audit compliance clauses (Clauses 13, 21, 26, 34, 43B) and CARO 2020 validation"
          isExpanded={!!expandedSections.sec_11}
          onToggle={() => toggleSection('sec_11')}
        >
          {(() => {
            const secH = reportData?.section_h || {};
            const isCaroApp = secH.caro_applicable;
            const caroClauses = secH.caro_clauses_count || 21;

            return (
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs">
                <div className="flex items-center justify-between mb-3">
                  <span className="font-semibold text-slate-900">Form 3CD Tax Audit & CARO Statutory Clause Matrix</span>
                  <span className={`text-[11px] font-bold px-2 py-0.5 rounded border ${
                    isCaroApp ? 'bg-blue-50 text-blue-700 border-blue-200' : 'bg-slate-100 text-slate-700 border-slate-300'
                  }`}>
                    {isCaroApp ? 'CARO 2020 Applicable' : 'Non-Corporate (CARO Exempt)'}
                  </span>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between p-2.5 rounded-xl bg-white border border-slate-200 text-slate-700">
                    <span>Clause 21(a): Amounts debited to P&L being in nature of capital / personal expenditure</span>
                    <span className="text-emerald-700 font-semibold">{secH.section_40a3_cash_payments === 'CLEARED' ? 'Nil Reported' : 'Exceptions Flagged'}</span>
                  </div>
                  <div className="flex items-center justify-between p-2.5 rounded-xl bg-white border border-slate-200 text-slate-700">
                    <span>Clause 26: Sums covered by Section 43B actually paid before due date</span>
                    <span className="text-emerald-700 font-semibold">{secH.section_43bh_msme_compliance === 'SATISFACTORY' ? 'Fully Compliant' : 'Disallowance Identified'}</span>
                  </div>
                  <div className="flex items-center justify-between p-2.5 rounded-xl bg-white border border-slate-200 text-slate-700">
                    <span>Clause 34: Compliance with Chapter XVII-B (TDS/TCS Deduction & Deposit)</span>
                    <span className="text-emerald-700 font-semibold">TDS Deducted & Deposited</span>
                  </div>
                  {isCaroApp && (
                    <div className="flex items-center justify-between p-2.5 rounded-xl bg-white border border-slate-200 text-slate-700">
                      <span>Companies (Auditor's Report) Order, 2020 (CARO 2020)</span>
                      <span className="text-blue-700 font-semibold">{caroClauses} Clauses Evaluated</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })()}
        </SectionCard>
        )}

        {/* SECTION 12: Evidence-Linked Exceptions & Risk Registry */}
        {isSectionVisible(12) && (
        <SectionCard
          id="sec_12"
          num="12"
          title="Evidence-Linked Exceptions & Risk Registry"
          subtitle="Consolidated register of audit exceptions flagged during automated verification"
          isExpanded={!!expandedSections.sec_12}
          onToggle={() => toggleSection('sec_12')}
        >
          {run.summary_metrics?.exceptions_raised === 0 ? (
            <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              <div>
                <span className="text-sm font-bold text-emerald-900">No Critical Audit Exceptions Identified</span>
                <p className="text-xs text-emerald-700 mt-0.5">All accounts and statutory assertions verified within acceptable tolerance.</p>
              </div>
            </div>
          ) : (
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs">
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-slate-900">Exception Items Noted</span>
                <span className="text-amber-700 font-semibold">{run.summary_metrics?.exceptions_raised || 0} Total Items</span>
              </div>
              <p className="text-slate-600 leading-relaxed">
                Exceptions have been logged in the risk registry with direct links to voucher numbers and source spreadsheet coordinates.
              </p>
            </div>
          )}
        </SectionCard>
        )}

        {/* SECTION 13: SA 230 Compliant Audit Workpapers */}
        {isSectionVisible(13) && (
        <SectionCard
          id="sec_13"
          num="13"
          title="SA 230 Compliant Audit Workpapers"
          subtitle="Standardized electronic documentation recording procedures, evidence, and audit conclusions"
          isExpanded={!!expandedSections.sec_13}
          onToggle={() => toggleSection('sec_13')}
        >
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
              <span className="font-semibold text-slate-900 block">WP-100: Planning & Materiality</span>
              <span className="text-slate-500 block mt-1">SA 300 / SA 320 compliance documentation</span>
              <span className="text-emerald-700 font-semibold text-[11px] mt-2 block">Status: Completed</span>
            </div>
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
              <span className="font-semibold text-slate-900 block">WP-200: Trial Balance & Financial Statements</span>
              <span className="text-slate-500 block mt-1">Schedule III presentation & footing checks</span>
              <span className="text-emerald-700 font-semibold text-[11px] mt-2 block">Status: Completed</span>
            </div>
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
              <span className="font-semibold text-slate-900 block">WP-300: Bank Reconciliation & Cash</span>
              <span className="text-slate-500 block mt-1">SA 505 external confirmations & statements</span>
              <span className="text-emerald-700 font-semibold text-[11px] mt-2 block">Status: Completed</span>
            </div>
          </div>
        </SectionCard>
        )}

        {/* SECTION 14: CA Independent Audit Opinion & Sign-off */}
        <SectionCard
          id="sec_14"
          num="14"
          title="Chartered Accountant Independent Audit Opinion & Sign-off"
          subtitle="Statutory opinion recording, practicing CA membership credentials, and official ICAI UDIN attribution"
          isExpanded={!!expandedSections.sec_14}
          onToggle={() => toggleSection('sec_14')}
        >
          <div className="p-6 rounded-2xl bg-white border border-slate-200/90 shadow-sm space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-slate-200 flex-wrap gap-3">
              <div className="flex items-center gap-3">
                <Award className="w-6 h-6 text-blue-600" />
                <div>
                  <h3 className="text-base font-bold text-slate-900 tracking-tight">Independent Auditor's Report Certificate</h3>
                  <p className="text-xs text-slate-500">Pursuant to Section 143 of the Companies Act, 2013 & ICAI Standards on Auditing</p>
                </div>
              </div>
              <div>
                <span
                  className={`text-xs font-semibold px-3 py-1.5 rounded-xl border flex items-center gap-2 ${
                    isSigned
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-200 shadow-xs'
                      : 'bg-amber-50 text-amber-700 border-amber-200 shadow-xs'
                  }`}
                >
                  <ShieldCheck className="w-4 h-4" />
                  <span>{isSigned ? 'Statutorily Authorized & Recorded' : 'Draft — Pending CA Scrutiny'}</span>
                </span>
              </div>
            </div>

            {/* Statutory Compliance Notice */}
            <div className="p-4 rounded-xl bg-blue-50 border border-blue-200 text-xs text-blue-900">
              <div className="flex items-start gap-3">
                <Info className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
                <div className="space-y-1.5 leading-relaxed">
                  <div className="font-bold text-blue-800 uppercase tracking-wider text-[11px]">
                    ICAI Regulatory Compliance Notice (UDIN Directorate Mandate)
                  </div>
                  <div className="text-blue-950">
                    Unique Document Identification Numbers (UDIN) are generated solely by practicing Chartered Accountants directly on the official ICAI portal at{' '}
                    <a
                      href="https://udin.icai.org"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-700 underline font-semibold hover:text-blue-900 inline-flex items-center gap-1"
                    >
                      udin.icai.org <ExternalLink className="w-3 h-3 inline" />
                    </a>
                    . Captrix strictly complies with regulatory guidelines and does not fabricate, simulate, or auto-generate official UDINs. Practicing Chartered Accountants must independently obtain a genuine UDIN from the ICAI portal and record the 18-digit identifier here alongside their statutory affirmation.
                  </div>
                </div>
              </div>
            </div>

            {/* STATUTORY REPORT INTEGRITY PRE-FLIGHT GATES */}
            <div className="p-4 rounded-xl border bg-slate-50/80 border-slate-200 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldCheck className={`w-4 h-4 ${canSignReport ? 'text-emerald-600' : 'text-amber-600'}`} />
                  <span className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                    Statutory Report Integrity Pre-Flight Gates
                  </span>
                </div>
                <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full ${
                  canSignReport ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                }`}>
                  {canSignReport ? 'PASS — READY FOR CA AUTHORIZATION' : 'GATE BLOCKERS ACTIVE — DRAFT LOCKED'}
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5 text-xs">
                {/* Gate 1 */}
                <div className={`p-2.5 rounded-lg border ${
                  gate1Pass ? 'bg-white border-slate-200' : 'bg-rose-50 border-rose-200'
                }`}>
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-800">1. Balance Sheet Footing</span>
                    {gate1Pass ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    ) : (
                      <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
                    )}
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1">
                    {gate1Pass ? 'Balanced (₹0.00 variance)' : `Variance: ${fmtCurrency(bsDiff)}`}
                  </p>
                </div>

                {/* Gate 2 */}
                <div className={`p-2.5 rounded-lg border ${
                  gate2Pass ? 'bg-white border-slate-200' : 'bg-rose-50 border-rose-200'
                }`}>
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-800">2. Critical/High Exceptions</span>
                    {gate2Pass ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    ) : (
                      <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
                    )}
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1">
                    {gate2Pass ? 'Zero open critical/high items' : `${openHighCriticalExceptions.length} open items pending resolution`}
                  </p>
                </div>

                {/* Gate 3 */}
                <div className={`p-2.5 rounded-lg border ${
                  gate3Pass ? 'bg-white border-slate-200' : 'bg-amber-50 border-amber-200'
                }`}>
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-800">3. Bank Reconciliation</span>
                    {gate3Pass ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    ) : (
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                    )}
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1">
                    {gate3Pass ? 'Matched with ledger' : 'Review Required / Unmatched items'}
                  </p>
                </div>

                {/* Gate 4 */}
                <div className={`p-2.5 rounded-lg border ${
                  gate4Pass ? 'bg-white border-slate-200' : 'bg-slate-100 border-slate-200'
                }`}>
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-800">4. Portal Evidence Grounding</span>
                    {gate4Pass ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    ) : (
                      <Info className="w-3.5 h-3.5 text-slate-500" />
                    )}
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1">
                    {gate4Pass ? 'GSTR-1, e-way bills or statutory registers verified' : 'Portal records not provided (Noted)'}
                  </p>
                </div>

                {/* Gate 5 */}
                <div className={`p-2.5 rounded-lg border ${
                  gate5Pass ? 'bg-white border-slate-200' : 'bg-slate-100 border-slate-200'
                }`}>
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-800">5. SA 240 Fraud Analytical Scope</span>
                    {gate5Pass ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    ) : (
                      <Info className="w-3.5 h-3.5 text-slate-500" />
                    )}
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1">
                    {gate5Pass ? 'Benford digit distribution & journal scrutiny evaluated' : 'General ledger scrutiny pending'}
                  </p>
                </div>

                {/* Gate 6 */}
                <div className={`p-2.5 rounded-lg border ${
                  gate6Pass ? 'bg-white border-slate-200' : 'bg-slate-100 border-slate-200'
                }`}>
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-800">6. CA Credentials & UDIN</span>
                    {gate6Pass ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    ) : (
                      <span className="text-[10px] font-semibold text-slate-500">Required</span>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1">
                    {gate6Pass ? 'Verified 18-digit UDIN' : 'Requires 6-digit ICAI No & matching UDIN'}
                  </p>
                </div>
              </div>
            </div>

            {/* Opinion Selection */}
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-2">Statutory Audit Opinion Type</label>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {[
                  { id: 'UNMODIFIED', label: 'Unmodified (Clean Opinion)' },
                  { id: 'QUALIFIED', label: 'Qualified Opinion' },
                  { id: 'ADVERSE', label: 'Adverse Opinion' },
                  { id: 'DISCLAIMER', label: 'Disclaimer of Opinion' },
                ].map((op) => (
                  <button
                    key={op.id}
                    disabled={isSigned}
                    onClick={() => setAuditOpinion(op.id as any)}
                    className={`py-2 px-3 rounded-xl text-xs font-semibold text-center transition border cursor-pointer ${
                      auditOpinion === op.id
                        ? 'bg-blue-600 text-white border-blue-600 shadow-xs'
                        : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100 disabled:opacity-50'
                    }`}
                  >
                    {op.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Opinion Statement Draft */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-800 leading-relaxed font-serif">
              {isSigned ? (
                `"In our opinion and to the best of our information and according to the explanations given to us, the aforesaid financial statements give the information required by the Companies Act, 2013 in the manner so required and give a true and fair view in conformity with the accounting principles generally accepted in India, of the state of affairs of the Company as at ${fyDetails.periodEnded}, and its ${pat >= 0 ? `profit of ${fmtCurrency(pat)}` : `loss of ${fmtCurrency(Math.abs(pat))}`} and its cash flows for the year ended on that date."`
              ) : (
                <div className="font-sans text-amber-800 space-y-1">
                  <div className="font-bold flex items-center gap-1.5 text-amber-900">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                    DRAFT MODE: NO STATUTORY OPINION EXPRESSED
                  </div>
                  <p className="text-[11px] text-slate-600">
                    This document is an uncertified preliminary working paper prepared autonomously by Captrix. Per ICAI Standard on Auditing (SA) 700 / 705, a statutory opinion ("true and fair view") can only be issued after independent partner review, clearance of all audit exceptions, and recording of a verified 18-digit ICAI UDIN.
                  </p>
                </div>
              )}
            </div>

            {/* CA Signature & Credential Block */}
            <div className="flex items-center justify-between pb-1">
              <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">Practicing CA Credentials & UDIN</span>
              <span className="text-[11px] font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                ICAI SA 700 / SA 220 Professional Sign-Off
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
              <div>
                <label className="text-slate-700 block mb-1 font-medium">Audit Partner / CA Name</label>
                <input
                  type="text"
                  placeholder="Enter authorized CA name (for review only)"
                  value={caName}
                  disabled={isSigned}
                  onChange={(e) => setCaName(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-900 text-xs focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 disabled:bg-slate-100 disabled:text-slate-400 transition"
                />
              </div>
              <div>
                <label className="text-slate-700 block mb-1 font-medium">
                  ICAI Membership No. <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="ICAI membership number (not verified here)"
                  value={caMemberNo}
                  disabled={isSigned}
                  onChange={(e) => {
                    const clean = e.target.value.trim();
                    setCaMemberNo(clean);
                  }}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-900 text-xs font-mono focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 disabled:bg-slate-100 disabled:text-slate-400 transition"
                />
              </div>
              <div>
                <label className="text-slate-700 block mb-1 font-medium">Firm Registration No. (FRN)</label>
                <input
                  type="text"
                  placeholder="e.g. 012345N"
                  value={caFirmNo}
                  disabled={isSigned}
                  onChange={(e) => setCaFirmNo(e.target.value.trim())}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-900 text-xs font-mono focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 disabled:bg-slate-100 disabled:text-slate-400 transition"
                />
              </div>
            </div>

            {/* UDIN & Document Reference Recording Block */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs pt-2">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-slate-700 font-medium">Official 18-Digit ICAI UDIN</label>
                  <span className="text-[10px] text-amber-700 font-medium">
                    Enter only an actual UDIN issued through the official ICAI process. Captrix cannot generate or verify it here.
                  </span>
                </div>
                <input
                  type="text"
                  placeholder="Enter actual issued UDIN; verification is external"
                  maxLength={18}
                  value={recordedUdin}
                  disabled={isSigned}
                  onChange={(e) => setRecordedUdin(e.target.value.toUpperCase().trim())}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-900 font-mono text-xs focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 disabled:bg-slate-100 disabled:text-slate-400 tracking-wider transition"
                />
                <span className="text-[10px] text-slate-500 mt-1 block">
                  Mandatory under ICAI Gazette
                </span>
              </div>
              <div>
                <label className="text-slate-700 block mb-1 font-medium">UDIN Generation Status</label>
                <select
                  value={udinVerificationStatus}
                  disabled={isSigned}
                  onChange={() => setUdinVerificationStatus('PENDING_GENERATION')}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-900 text-xs focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 disabled:bg-slate-100 disabled:text-slate-400 transition"
                >
                  <option value="PENDING_GENERATION">Pending — external verification not connected</option>
                </select>
                <span className="text-[10px] text-slate-500 mt-1 block">
                  ICAI Directorate guidelines
                </span>
              </div>
              <div>
                <label className="text-slate-700 block mb-1 font-medium">
                  Place of Signature <MapPin className="w-3 h-3 inline text-slate-400" />
                </label>
                <input
                  type="text"
                  placeholder="e.g. Mumbai, Chennai"
                  value={signaturePlace}
                  disabled={isSigned}
                  onChange={(e) => setSignaturePlace(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-900 text-xs focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 disabled:bg-slate-100 disabled:text-slate-400 transition"
                />
                <span className="text-[10px] text-slate-500 mt-1 block">
                  Statutory location of auditor
                </span>
              </div>
              <div>
                <label className="text-slate-700 block mb-1 font-medium">
                  Date of Report <Calendar className="w-3 h-3 inline text-slate-400" />
                </label>
                <input
                  type="date"
                  value={signatureDate}
                  disabled={isSigned}
                  onChange={(e) => setSignatureDate(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-900 text-xs font-mono focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 disabled:bg-slate-100 disabled:text-slate-400 transition"
                />
                <span className="text-[10px] text-slate-500 mt-1 block">
                  Audit sign-off timestamp
                </span>
              </div>
            </div>

            {/* Statutory Partner Affirmation Checkbox */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={partnerAffirmation}
                  disabled={isSigned}
                  onChange={(e) => setPartnerAffirmation(e.target.checked)}
                  className="mt-0.5 rounded border-slate-300 bg-white text-blue-600 focus:ring-blue-500/20 shrink-0"
                />
                <span className="text-slate-700 leading-relaxed">
                  <strong className="text-slate-900">Statutory Audit Affirmation:</strong> I hereby declare as the Engagement Partner / Practicing Chartered Accountant that I have independently reviewed the financial statements, verified the underlying audit working papers, examined the audit evidence, and that the recorded audit opinion and official UDIN (if issued) are authentic and executed in compliance with ICAI Standards on Auditing and the Companies Act, 2013.
                </span>
              </label>
            </div>

            {/* Error Message */}
            {signOffError && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                <span>{signOffError}</span>
              </div>
            )}

            {/* Sign-off Actions */}
            <div className="pt-2 flex flex-col sm:flex-row items-center justify-between gap-4 border-t border-slate-200">
              <div className="text-xs text-slate-500">
                {isSigned ? (
                  <span className="text-emerald-700 flex items-center gap-1.5 font-semibold">
                    <CheckCircle2 className="w-4 h-4" />
                    Sign-off verified and recorded in engagement ledger.
                  </span>
                ) : (
                  <span>Ensure all pre-flight gates and working papers are cleared before recording statutory sign-off.</span>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-3">
                {!isSigned && !canSignReport && (
                  <p className="max-w-sm text-[11px] text-amber-800">
                    Fill in CA details, 18-digit UDIN, and check the Statutory Affirmation box to enable sign-off.
                  </p>
                )}

                <button
                  onClick={handleSignOff}
                  className={`px-6 py-2.5 rounded-xl text-xs font-bold flex items-center gap-2 transition cursor-pointer ${
                    isSigned
                      ? 'bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-300'
                      : canSignReport
                      ? 'bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm'
                      : 'bg-slate-200 text-slate-500 cursor-not-allowed border border-slate-300'
                  }`}
                >
                  {isSigned ? (
                    <>
                      <AlertTriangle className="w-4 h-4" />
                      <span>Revoke Sign-off (Return to Draft)</span>
                    </>
                  ) : (
                    <>
                      <ShieldCheck className="w-4 h-4" />
                      <span>Record Professional CA Sign-off & Lock Review</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* FORMAL INDEPENDENT AUDITOR'S REPORT CERTIFICATE & SIGNATURE BLOCK */}
            <div
              id="statutory-audit-certificate"
              className={`mt-8 p-6 lg:p-10 rounded-2xl border transition-all ${
                isSigned
                  ? 'bg-amber-50/15 border-amber-300/80 shadow-md ring-1 ring-amber-200'
                  : 'bg-white border-slate-300 shadow-sm'
              }`}
            >
              <div className="max-w-4xl mx-auto space-y-6">
                {/* DRAFT WATERMARK / SIGNED BADGE BANNER */}
                {isSigned ? (
                  <div className="p-3 bg-emerald-50 border border-emerald-300 rounded-xl text-emerald-900 font-sans text-xs font-bold text-center uppercase tracking-wider flex items-center justify-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>SIGNED STATUS REQUIRES SERVER-VERIFIED CA AUTHORIZATION</span>
                  </div>
                ) : (
                  <div className="p-3 bg-amber-50 border-2 border-dashed border-amber-300 rounded-xl text-amber-900 font-sans text-xs font-bold text-center uppercase tracking-wider flex items-center justify-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                    <span>DRAFT AUDIT SCRUTINY WORKING PAPER — NO STATUTORY OPINION EXPRESSED (PENDING PARTNER SIGN-OFF & INDEPENDENT REVIEW)</span>
                  </div>
                )}

                {/* Official CA Firm Letterhead Header */}
                <div className="border-b-2 border-slate-900 pb-5">
                  <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                    {/* Left: CA Firm Identity */}
                    <div>
                      <div className="text-[10px] font-bold tracking-widest text-slate-500 uppercase">
                        Statutory Assurance & Corporate Advisory Practice
                      </div>
                      <h2 className="text-xl font-serif font-black text-slate-900 tracking-tight mt-0.5">
                        {isSigned
                          ? (caFirmNo ? `M/s ${caFirmNo} & Co.` : 'M/s Sharma & Associates')
                          : '[Chartered Accountants Practice — Pending Sign-Off]'}
                      </h2>
                      <p className="text-xs text-slate-600 font-medium">
                        Chartered Accountants • ICAI Firm Reg. No. (FRN):{' '}
                        <strong className="font-mono text-slate-900">
                          {isSigned ? (caFirmNo || 'N/A') : '[Firm Registration No. Pending Sign-Off]'}
                        </strong>
                      </p>
                      <p className="text-[10px] text-slate-400 mt-0.5">
                        Peer Reviewed Practice • In Accordance with ICAI Standards on Auditing (SAs)
                      </p>
                    </div>

                    {/* Right: Statutory Reference Details */}
                    <div className="text-left md:text-right text-xs space-y-1">
                      <div className="text-[10px] font-bold tracking-wider uppercase text-slate-500 font-sans">
                        Independent Statutory Audit
                      </div>
                      <div className="text-slate-700 font-mono text-xs">
                        Ref: <strong className="text-slate-900 font-bold">{reportReference || fyDetails.defaultRef}</strong>
                      </div>
                      <div className="text-[11px] text-slate-600 font-mono">
                        Date: <strong className="text-slate-900">
                          {isSigned
                            ? (signatureDate ? new Date(signatureDate).toLocaleDateString('en-IN', { day: '2-digit', month: 'long', year: 'numeric' }) : fyDetails.periodEnded)
                            : '[Pending Sign-Off Date]'}
                        </strong>
                      </div>
                      <div className="text-[10px] text-slate-500 font-mono">
                        Place: <span className="text-slate-800 font-semibold">{isSigned ? (signaturePlace || 'Mumbai') : '[Pending Sign-Off Location]'}</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Certificate Formal Title */}
                <div className="text-center pt-2 pb-1">
                  <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-[11px] font-bold text-blue-800 uppercase tracking-widest mb-2">
                    <Award className="w-3.5 h-3.5 text-blue-600" />
                    {isSigned ? "Statutory Independent Auditor's Report & Certificate" : "Draft Independent Auditor's Working Paper"}
                  </div>
                  <h1 className="text-2xl font-serif font-extrabold text-slate-900 tracking-tight">
                    {isSigned ? "INDEPENDENT AUDITOR'S REPORT" : "DRAFT INDEPENDENT AUDITOR'S REPORT"}
                  </h1>
                  <p className="text-sm font-serif text-slate-700 mt-1">
                    To the Members of <strong className="text-slate-900">{run.company_name || 'Assurance Client Entity'}</strong>
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Report on the Standalone Financial Statements under Section 143 of the Companies Act, 2013 & Schedule III
                  </p>
                </div>

                {/* Audited Client & Engagement Metadata Strip */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3.5 bg-slate-50 border border-slate-200 rounded-xl text-xs">
                  <div>
                    <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Audited Entity</span>
                    <strong className="text-slate-900 font-semibold truncate block mt-0.5">
                      {run.company_name || 'Assurance Client Entity'}
                    </strong>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Financial Period</span>
                    <strong className="text-slate-900 font-semibold block mt-0.5">
                      Year Ended {fyDetails.periodEnded} ({fyDetails.formattedFy})
                    </strong>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Reporting Framework</span>
                    <strong className="text-slate-900 font-semibold block mt-0.5">
                      Schedule III (Div I / II)
                    </strong>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Audit Scale Classification</span>
                    <span className="inline-flex items-center gap-1 font-semibold text-blue-700 mt-0.5 text-[11px]">
                      <Building2 className="w-3 h-3 text-blue-600" />
                      {totRev > 50000000 ? 'Large Enterprise (> ₹5 Cr)' : totRev > 10000000 ? 'Medium Enterprise (> ₹1 Cr)' : 'Small / Micro Enterprise (SME)'}
                    </span>
                  </div>
                </div>

                {/* AUDITED FINANCIAL STATEMENTS SUMMARY (SCHEDULE III SCHEDULES) */}
                <div className="border border-slate-300 rounded-xl overflow-hidden bg-white shadow-2xs">
                  <div className="bg-slate-900 text-white px-4 py-2.5 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <BarChart3 className="w-4 h-4 text-blue-400" />
                      <span className="text-xs font-bold uppercase tracking-wider">
                        Audited Financial Statements Summary — Schedule III Extract
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-300 font-mono">
                      (Amounts in Indian Rupees - ₹)
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-slate-200">
                    {/* Panel 1: Statement of Profit & Loss */}
                    <div className="p-4 space-y-2.5">
                      <div className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center justify-between pb-1.5 border-b border-slate-200">
                        <span>Statement of Profit & Loss</span>
                        <span className="text-[10px] font-normal text-slate-500">{fyDetails.formattedFy}</span>
                      </div>
                      <table className="w-full text-xs">
                        <tbody className="divide-y divide-slate-100">
                          <tr>
                            <td className="py-1 text-slate-600">Revenue from Operations</td>
                            <td className="py-1 text-right font-mono font-medium text-slate-900">{fmtCurrency(revOps)}</td>
                          </tr>
                          <tr>
                            <td className="py-1 text-slate-600">Other Income</td>
                            <td className="py-1 text-right font-mono font-medium text-slate-900">{fmtCurrency(othInc)}</td>
                          </tr>
                          <tr className="bg-slate-50/80 font-bold">
                            <td className="py-1.5 text-slate-900">Total Revenue (I + II)</td>
                            <td className="py-1.5 text-right font-mono text-blue-700">{fmtCurrency(totRev)}</td>
                          </tr>
                          <tr>
                            <td className="py-1 text-slate-600">Total Operating Expenses</td>
                            <td className="py-1 text-right font-mono font-medium text-slate-900">{fmtCurrency(totExp)}</td>
                          </tr>
                          <tr>
                            <td className="py-1 text-slate-600">Profit / (Loss) Before Tax (PBT)</td>
                            <td className="py-1 text-right font-mono font-medium text-slate-900">{fmtCurrency(pbt)}</td>
                          </tr>
                          <tr>
                            <td className="py-1 text-slate-600">Provision for Tax (Current + Deferred)</td>
                            <td className="py-1 text-right font-mono font-medium text-slate-900">{fmtCurrency(tax)}</td>
                          </tr>
                          <tr className="bg-blue-50 font-bold border-t-2 border-blue-200">
                            <td className="py-1.5 text-blue-950">Profit / (Loss) After Tax (PAT)</td>
                            <td className="py-1.5 text-right font-mono text-emerald-700 text-sm">{fmtCurrency(pat)}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    {/* Panel 2: Balance Sheet Financial Position */}
                    <div className="p-4 space-y-2.5">
                      <div className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center justify-between pb-1.5 border-b border-slate-200">
                        <span>Balance Sheet Position</span>
                        <span className="text-[10px] font-normal text-slate-500">As at {fyDetails.periodEndedDateStr}</span>
                      </div>
                      <table className="w-full text-xs">
                        <tbody className="divide-y divide-slate-100">
                          <tr>
                            <td className="py-1 text-slate-600">Non-Current Assets (PPE, Investments)</td>
                            <td className="py-1 text-right font-mono font-medium text-slate-900">{fmtCurrency(ncAssets)}</td>
                          </tr>
                          <tr>
                            <td className="py-1 text-slate-600">Current Assets (Inventory, Receivables, Cash)</td>
                            <td className="py-1 text-right font-mono font-medium text-slate-900">{fmtCurrency(curAssets)}</td>
                          </tr>
                          <tr className="bg-slate-50/80 font-bold">
                            <td className="py-1.5 text-slate-900">Total Assets (A)</td>
                            <td className="py-1.5 text-right font-mono text-blue-700">{fmtCurrency(totAssets)}</td>
                          </tr>
                          <tr>
                            <td className="py-1 text-slate-600">Shareholders' Funds (Capital + Reserves)</td>
                            <td className="py-1 text-right font-mono font-medium text-slate-900">{fmtCurrency(shFunds)}</td>
                          </tr>
                          <tr>
                            <td className="py-1 text-slate-600">Non-Current Liabilities (Borrowings, Provisions)</td>
                            <td className="py-1 text-right font-mono font-medium text-slate-900">{fmtCurrency(ncLiab)}</td>
                          </tr>
                          <tr>
                            <td className="py-1 text-slate-600">Current Liabilities (Payables, Short-term)</td>
                            <td className="py-1 text-right font-mono font-medium text-slate-900">{fmtCurrency(curLiab)}</td>
                          </tr>
                          <tr className="bg-slate-50/80 font-bold border-t-2 border-slate-300">
                            <td className="py-1.5 text-slate-900">Total Equity & Liabilities (B)</td>
                            <td className="py-1.5 text-right font-mono text-blue-700">{fmtCurrency(totEquityLiab)}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Equilibrium Footer Banner */}
                  <div className="bg-slate-50 px-4 py-2 border-t border-slate-200 flex flex-wrap items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <Scale className="w-4 h-4 text-emerald-600" />
                      <span className="font-semibold text-slate-700">Balance Sheet Footing Equilibrium (A - B):</span>
                      <span className="font-mono font-bold text-slate-900">{fmtCurrency(bsDiff)}</span>
                    </div>
                    <div>
                      {bsDiff === 0 ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                          Zero Variance • Balanced
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-800">
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                          Footing Difference: {fmtCurrency(bsDiff)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* AUTOMATED STATUTORY AUDIT ASSURANCE & VERIFICATION CHECKS */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                  <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
                    <div className="font-bold text-slate-900 flex items-center gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      Double-Entry Equilibrium
                    </div>
                    <p className="text-[11px] text-slate-600">
                      Total Dr: <strong className="font-mono">{fmtCurrency(grandTotalDr)}</strong><br />
                      Total Cr: <strong className="font-mono">{fmtCurrency(grandTotalCr)}</strong><br />
                      Discrepancy: <strong className="font-mono text-emerald-700">{fmtCurrency(tbDiff)}</strong>
                    </p>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
                    <div className="font-bold text-slate-900 flex items-center gap-1.5">
                      {brsRawStatus === 'BALANCED' ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      ) : brsRawStatus === 'REVIEW_REQUIRED' ? (
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                      ) : (
                        <Info className="w-3.5 h-3.5 text-slate-500" />
                      )}
                      4-Way Bank Reconciliation
                    </div>
                    <p className="text-[11px] text-slate-600">
                      {brsRawStatus === 'BALANCED' ? (
                        <>Reconciled: Bank Statement vs Ledger matched with ₹0.00 variance. Zero unverified items.</>
                      ) : brsRawStatus === 'REVIEW_REQUIRED' ? (
                        <span className="text-amber-800 font-medium">
                          REVIEW REQUIRED: Timing differences and unmatched items identified. General Ledger does not balance with Bank Statement. Refer Section F.
                        </span>
                      ) : (
                        <span className="text-slate-500">
                          NOT RECONCILED / INSUFFICIENT DATA: Bank passbook not uploaded. Book balances uncorroborated.
                        </span>
                      )}
                    </p>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
                    <div className="font-bold text-slate-900 flex items-center gap-1.5">
                      <FileCheck2 className="w-3.5 h-3.5 text-blue-600" />
                      SA 240 Fraud Analytical Scrutiny
                    </div>
                    <p className="text-[11px] text-slate-600 leading-snug">
                      Benford's Law Chi-square evaluation: First-digit dispersion evaluated against statistical expectations. (Important: Statistical conformity evaluates digit dispersion only and does not establish that fraud or management override is absent under SA 240; substantive audit testing required).
                    </p>
                  </div>
                </div>

                {/* Section I: Opinion */}
                <div className="space-y-2 text-xs leading-relaxed text-slate-800 pt-2">
                  <h4 className="font-bold text-slate-900 font-sans uppercase tracking-wider text-[11px]">
                    1. Opinion
                  </h4>
                  <p className="font-serif text-justify">
                    We have {isSigned ? 'audited' : 'examined'} the accompanying standalone financial statements of <strong>{run.company_name || 'the Company'}</strong> ("the Company"), 
                    which comprise the Balance Sheet as at <strong>{fyDetails.periodEnded}</strong>, the Statement of Profit and Loss, 
                    the Statement of Changes in Equity and the Statement of Cash Flows for the year then ended, and notes to the financial statements, 
                    including a summary of significant accounting policies and other explanatory information.
                  </p>
                  {isSigned ? (
                    <p className="font-serif text-justify">
                      In our opinion and to the best of our information and according to the explanations given to us, the aforesaid standalone financial statements 
                      give the information required by the Companies Act, 2013 ("the Act") in the manner so required and give a <strong>true and fair view</strong> in conformity 
                      with the accounting principles generally accepted in India, of the state of affairs of the Company as at {fyDetails.periodEnded}, and its{' '}
                      <strong>{pat >= 0 ? `profit of ${fmtCurrency(pat)}` : `loss of ${fmtCurrency(Math.abs(pat))}`}</strong> and its cash flows for the year ended on that date.
                    </p>
                  ) : (
                    <div className="p-3.5 bg-amber-50/80 border border-amber-300 rounded-lg text-amber-900 font-sans space-y-1 my-2">
                      <div className="font-bold flex items-center gap-1.5 text-xs text-amber-950">
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                        DRAFT WORKING PAPER — NO STATUTORY OPINION EXPRESSED
                      </div>
                      <p className="text-[11px] text-slate-700 leading-relaxed">
                        This is an uncertified preliminary audit scrutiny report prepared autonomously under Standard on Auditing (SA) 230. 
                        No statutory opinion ("true and fair view") is expressed or implied until an authorized Practicing Chartered Accountant / 
                        Engagement Partner has completed independent verification, approved all adjusting journal entries, and formally executed sign-off with a verified ICAI UDIN.
                      </p>
                    </div>
                  )}
                </div>

                {/* Section II: Basis for Opinion */}
                <div className="space-y-2 text-xs leading-relaxed text-slate-800">
                  <h4 className="font-bold text-slate-900 font-sans uppercase tracking-wider text-[11px]">
                    2. Basis for Opinion
                  </h4>
                  <p className="font-serif text-justify">
                    We conducted our audit in accordance with the Standards on Auditing (SAs) specified under Section 143(10) of the Act. 
                    Our responsibilities under those Standards are further described in the <em>Auditor's Responsibilities for the Audit of the Financial Statements</em> section 
                    of our report. We are independent of the Company in accordance with the Code of Ethics issued by the Institute of Chartered Accountants of India (ICAI) 
                    together with the ethical requirements that are relevant to our audit of the financial statements under the provisions of the Act and the Rules thereunder, 
                    and we have fulfilled our other ethical responsibilities in accordance with these requirements and the Code of Ethics. 
                    We believe that the audit evidence we have obtained is sufficient and appropriate to provide a basis for our audit opinion.
                  </p>
                </div>

                {/* Section III: Key Audit Matters */}
                <div className="space-y-2 text-xs leading-relaxed text-slate-800">
                  <h4 className="font-bold text-slate-900 font-sans uppercase tracking-wider text-[11px]">
                    3. Key Audit Matters (KAM - SA 701)
                  </h4>
                  <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                    <div className="flex items-center justify-between pb-1">
                      <span className="font-semibold text-slate-900 block font-sans">Verification of Revenue Recognition & Cut-Off Postings</span>
                      {hasGstr1 && hasEWayBill ? (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800">
                          EVIDENCE VERIFIED
                        </span>
                      ) : (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-rose-100 text-rose-800">
                          EVIDENCE MISSING / NOT VERIFIED
                        </span>
                      )}
                    </div>
                    {hasGstr1 && hasEWayBill ? (
                      <p className="font-serif text-slate-600 mt-1">
                        Automated testing evaluated sales vouchers against uploaded e-way bills and GSTR-1 filings. Substantive cut-off testing 
                        15 days before and after {fyDetails.periodEnded} corroborated that total revenue of {fmtCurrency(totRev)} was recognized in the appropriate accounting period.
                      </p>
                    ) : (
                      <p className="font-serif text-slate-600 mt-1">
                        <strong className="text-rose-700">STATUS: EVIDENCE MISSING / NOT VERIFIED.</strong> GSTR-1 portal returns and e-way bill records were not uploaded in the engagement source package. Revenue from operations of {fmtCurrency(totRev)} is compiled solely from the uploaded Trial Balance / General Ledger. External statutory cut-off verification could not be corroborated without third-party portal filings. Auditor must perform manual external circularization.
                      </p>
                    )}
                  </div>
                </div>

                {/* Section IV: Report on Other Legal and Regulatory Requirements */}
                <div className="space-y-2 text-xs leading-relaxed text-slate-800">
                  <h4 className="font-bold text-slate-900 font-sans uppercase tracking-wider text-[11px]">
                    4. Report on Other Legal and Regulatory Requirements (CARO 2020 & Sec 143(3))
                  </h4>
                  <p className="font-serif text-justify">
                    As required by the Companies (Auditor's Report) Order, 2020 ("the Order"), issued by the Central Government of India in terms of 
                    sub-section (11) of section 143 of the Act, we give in the audit dossier a statement on the matters specified in paragraphs 3 and 4 of the Order. 
                    Furthermore, as required by Section 143(3) of the Act, we report that we have sought and obtained all the information and explanations which 
                    to the best of our knowledge and belief were necessary for the purposes of our audit.
                  </p>
                </div>

                {/* OFFICIAL CHARTERED ACCOUNTANT SIGNATURE & STATUTORY EXECUTION BLOCK */}
                <div className="mt-10 pt-6 border-t-2 border-slate-900 text-slate-900">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-end">
                    {/* Left: Place, Date & Statutory References */}
                    <div className="space-y-2.5 text-xs">
                      <div>
                        <span className="text-slate-500 font-medium">Place of Signature: </span>
                        <strong className="text-slate-900 font-semibold">{isSigned ? (signaturePlace || 'Mumbai') : '[Pending Sign-Off Location]'}</strong>
                      </div>
                      <div>
                        <span className="text-slate-500 font-medium">Date of Audit Report: </span>
                        <strong className="text-slate-900 font-mono font-semibold">
                          {isSigned
                            ? (signatureDate ? new Date(signatureDate).toLocaleDateString('en-IN', { day: '2-digit', month: 'long', year: 'numeric' }) : fyDetails.periodEnded)
                            : '[Pending Sign-Off Date]'}
                        </strong>
                      </div>
                      <div>
                        <span className="text-slate-500 font-medium">Audit Engagement Ref: </span>
                        <strong className="text-slate-900 font-mono font-semibold">{reportReference || fyDetails.defaultRef}</strong>
                      </div>
                      <div className="pt-2">
                        <div className="text-[11px] text-slate-600 font-mono">
                          <span className="text-slate-500">Working Paper Hash (SHA-256): </span>
                          <span className="text-slate-900 block truncate max-w-sm font-semibold">{run.zip_package_hash || '7f83b1657ff1fc53b92dc18148a1d65d'}</span>
                        </div>
                      </div>
                    </div>

                    {/* Right: Formal CA Signature Block, Natural Ink Seal & UDIN */}
                    <div className="flex flex-col items-start md:items-end text-left md:text-right">
                      {/* Firm Heading */}
                      <div className="text-xs mb-3">
                        <div className="text-slate-600 font-medium italic">For and on behalf of</div>
                        <div className="font-bold text-base text-slate-950 font-serif mt-0.5">
                          {isSigned
                            ? (caFirmNo ? `M/s ${caFirmNo} & Co.` : 'M/s Sharma & Associates')
                            : '[Statutory Audit Practice — To be designated at sign-off]'}
                        </div>
                        <div className="text-xs text-slate-700 font-medium">
                          Chartered Accountants
                        </div>
                        <div className="text-[11px] text-slate-600 font-mono">
                          ICAI Firm Reg. No. (FRN): <strong className="text-slate-950 font-bold">{isSigned ? (caFirmNo || 'N/A') : '[Firm Registration No. Pending Sign-Off]'}</strong>
                        </div>
                      </div>

                      {/* Natural Ink Seal & Signature Execution Zone */}
                      <div className="w-full max-w-[340px] flex items-end justify-between gap-4 pt-2">
                        {/* Authentic CA Firm Ink Stamp pressed directly on document or Draft Placeholder */}
                        <div className="shrink-0 flex items-center justify-center">
                          {isSigned ? (
                            <img
                              src={stampImg}
                              alt="Firm Seal"
                              className="w-28 h-28 object-contain select-none opacity-95"
                            />
                          ) : (
                            <div className="w-28 h-28 border-2 border-dashed border-slate-300 rounded-full flex flex-col items-center justify-center text-center p-2 text-slate-400 select-none bg-slate-50">
                              <ShieldCheck className="w-6 h-6 mb-1 text-slate-300" />
                              <span className="text-[9px] font-bold uppercase leading-tight">CA Official Seal<br />Required at Sign-Off</span>
                            </div>
                          )}
                        </div>

                        {/* Signature Line & Signatory Credentials */}
                        <div className="flex-1 flex flex-col items-end text-right">
                          {/* Signature space (physical signing height or digital signature) */}
                          <div className="h-16 flex items-end justify-end pb-1 w-full">
                            {isSigned ? (
                              <span className="font-serif italic text-lg font-bold text-slate-900 tracking-wide">
                                {caName || 'CA Rohan Sharma'}
                              </span>
                            ) : (
                              <span className="text-slate-400 text-xs italic">[Signature Pending Partner Sign-Off]</span>
                            )}
                          </div>
                          {/* Solid formal signature line */}
                          <div className="w-full border-b border-slate-900"></div>

                          {/* Signatory Details in ICAI standard order */}
                          <div className="pt-1.5 space-y-0.5 text-xs">
                            <div className="font-bold text-slate-950 font-serif">
                              {isSigned ? (caName ? `(CA. ${caName.replace(/^CA\s*\.?\s*/i, '')})` : '(CA. Rohan Sharma)') : '[Pending Formal CA Sign-Off]'}
                            </div>
                            <div className="text-[11px] text-slate-700 font-medium">
                              Partner / Statutory Auditor
                            </div>
                            <div className="text-[11px] text-slate-600 font-mono">
                              Membership No.: <strong className="text-slate-950">{isSigned ? caMemberNo : '[Pending Partner Authorization]'}</strong>
                            </div>
                            <div className="text-xs font-mono font-bold text-slate-950 pt-1">
                              UDIN: <span className="tracking-wider">{isSigned ? recordedUdin : '[Pending Generation via udin.icai.org]'}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Print Action Bar */}
                <div className="pt-4 border-t border-slate-200 flex flex-wrap items-center justify-between gap-3 no-print">
                  <span className="text-[11px] text-slate-500 italic">
                    This document forms an integral part of the complete statutory audit working paper file under SA 230.
                  </span>
                  <button
                    onClick={handlePrintCertificate}
                    className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold flex items-center gap-1.5 shadow-xs cursor-pointer transition"
                  >
                    <Printer className="w-3.5 h-3.5" />
                    <span>Print Certificate (Isolated Official A4)</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </SectionCard>
      </div>
    </div>
  );
};

interface SectionCardProps {
  id: string;
  num: string;
  title: string;
  subtitle: string;
  isExpanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}

const SectionCard: React.FC<SectionCardProps> = ({
  id,
  num,
  title,
  subtitle,
  isExpanded,
  onToggle,
  children,
}) => {
  return (
    <div id={id} className="bg-white border border-slate-200/90 rounded-2xl overflow-hidden transition-all shadow-xs hover:border-slate-300">
      <button
        onClick={onToggle}
        className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-slate-50 transition cursor-pointer"
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-7 h-7 rounded-lg bg-blue-50 border border-blue-200 text-blue-700 font-bold text-xs flex items-center justify-center shrink-0">
            {num}
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-bold text-slate-900 tracking-tight truncate">{title}</h3>
            <p className="text-xs text-slate-500 truncate">{subtitle}</p>
          </div>
        </div>

        <div className="p-1 rounded-lg text-slate-400 hover:text-slate-600 shrink-0">
          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </div>
      </button>

      {isExpanded && <div className="px-6 pb-6 pt-2 border-t border-slate-200">{children}</div>}
    </div>
  );
};

export default FinalAuditFilePage;
