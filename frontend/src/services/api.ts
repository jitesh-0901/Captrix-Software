const API_BASE = '/api';

export const api = {
  // Core & Auth
  async getCurrentUser() {
    const res = await fetch(`${API_BASE}/core/me/`);
    return res.json();
  },

  // Companies & Engagements
  async getCompanies() {
    try {
      const res = await fetch(`${API_BASE}/companies/companies/`);
      if (!res.ok) return [];
      const data = await res.json();
      return data.results || data;
    } catch (e) {
      console.warn('Failed to load companies:', e);
      return [];
    }
  },
  async getEngagements(companyId?: number) {
    try {
      const url = companyId ? `${API_BASE}/companies/engagements/?company=${companyId}` : `${API_BASE}/companies/engagements/`;
      const res = await fetch(url);
      if (!res.ok) return [];
      const data = await res.json();
      return data.results || data;
    } catch (e) {
      console.warn('Failed to load engagements:', e);
      return [];
    }
  },
  async deleteCompany(companyId: number) {
    const res = await fetch(`${API_BASE}/companies/companies/${companyId}/`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to delete client' }));
      throw new Error(err.detail || `Server returned ${res.status}`);
    }
    return true;
  },
  async clearAllCompanies() {
    const res = await fetch(`${API_BASE}/companies/companies/clear_all/`, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to clear all clients' }));
      throw new Error(err.detail || `Server returned ${res.status}`);
    }
    return res.json();
  },

  // Documents & Ingestion
  async uploadDocument(formData: FormData) {
    const res = await fetch(`${API_BASE}/ingestion/documents/`, {
      method: 'POST',
      body: formData,
    });
    return res.json();
  },
  async getDocuments(engagementId?: number) {
    const url = engagementId ? `${API_BASE}/ingestion/documents/?engagement=${engagementId}` : `${API_BASE}/ingestion/documents/`;
    const res = await fetch(url);
    const data = await res.json();
    return data.results || data;
  },
  async getDocumentRecords(docId: number) {
    const res = await fetch(`${API_BASE}/ingestion/documents/${docId}/records/`);
    const data = await res.json();
    return data.results || data;
  },

  // Accounting & GL Scrutiny
  async getTrialBalance(engagementId?: number) {
    const url = engagementId ? `${API_BASE}/accounting/trial-balances/latest/?engagement=${engagementId}` : `${API_BASE}/accounting/trial-balances/latest/`;
    const res = await fetch(url);
    if (!res.ok) return null;
    return res.json();
  },
  async getTbMovements(engagementId?: number) {
    const url = engagementId ? `${API_BASE}/accounting/trial-balances/movements/?engagement=${engagementId}` : `${API_BASE}/accounting/trial-balances/movements/`;
    const res = await fetch(url);
    if (!res.ok) return null;
    return res.json();
  },
  async getTransactions(engagementId?: number, isUnusual?: boolean, accountId?: number, search?: string) {
    let url = `${API_BASE}/accounting/transactions/?`;
    if (engagementId) url += `engagement=${engagementId}&`;
    if (isUnusual !== undefined) url += `is_unusual=${isUnusual}&`;
    if (accountId) url += `account=${accountId}&`;
    if (search) url += `search=${encodeURIComponent(search)}&`;
    const res = await fetch(url);
    const data = await res.json();
    return data.results || data;
  },
  async getTransactionEvidence(txnId: number) {
    const res = await fetch(`${API_BASE}/accounting/transactions/${txnId}/evidence/`);
    return res.json();
  },
  async getGlScrutiny(engagementId?: number) {
    const url = engagementId ? `${API_BASE}/accounting/transactions/scrutiny/?engagement=${engagementId}` : `${API_BASE}/accounting/transactions/scrutiny/`;
    const res = await fetch(url);
    return res.json();
  },

  // Reconciliation
  async getReconciliationRuns(engagementId?: number, type?: string) {
    let url = `${API_BASE}/reconciliation/runs/?`;
    if (engagementId) url += `engagement=${engagementId}&`;
    if (type) url += `type=${type}&`;
    const res = await fetch(url);
    const data = await res.json();
    return data.results || data;
  },
  async approveMatch(runId: number, itemId: number, notes: string) {
    const res = await fetch(`${API_BASE}/reconciliation/runs/${runId}/approve_match/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ item_id: itemId, notes }),
    });
    return res.json();
  },
  async runCrossDocumentReconciliation(engagementId?: number) {
    const res = await fetch(`${API_BASE}/reconciliation/runs/run_cross_document/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ engagement: engagementId }),
    });
    return res.json();
  },

  // Audit Procedures & Ratios
  async getProcedureExecutions(engagementId?: number) {
    const url = engagementId ? `${API_BASE}/audit/executions/?engagement=${engagementId}` : `${API_BASE}/audit/executions/`;
    const res = await fetch(url);
    const data = await res.json();
    return data.results || data;
  },
  async runAllProcedures(engagementId?: number) {
    const res = await fetch(`${API_BASE}/audit/executions/run_all/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ engagement: engagementId }),
    });
    return res.json();
  },
  async getRatios(engagementId?: number) {
    const url = engagementId ? `${API_BASE}/audit/executions/ratios/?engagement=${engagementId}` : `${API_BASE}/audit/executions/ratios/`;
    const res = await fetch(url);
    return res.json();
  },

  // Exceptions Center
  async getExceptions(engagementId?: number, severity?: string, statusFilter?: string) {
    let url = `${API_BASE}/audit/exceptions/?`;
    if (engagementId) url += `engagement=${engagementId}&`;
    if (severity) url += `severity=${severity}&`;
    if (statusFilter) url += `status=${statusFilter}&`;
    const res = await fetch(url);
    const data = await res.json();
    return data.results || data;
  },
  async resolveException(id: number, newStatus: string, notes: string) {
    const res = await fetch(`${API_BASE}/audit/exceptions/${id}/resolve/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus, resolution_notes: notes }),
    });
    return res.json();
  },
  async getExceptionEvidence(excId: number) {
    const res = await fetch(`${API_BASE}/audit/exceptions/${excId}/evidence/`);
    return res.json();
  },

  // Workpapers & Adjustments
  async getWorkpapers(engagementId?: number) {
    const url = engagementId ? `${API_BASE}/reporting/workpapers/?engagement=${engagementId}` : `${API_BASE}/reporting/workpapers/`;
    const res = await fetch(url);
    const data = await res.json();
    return data.results || data;
  },
  async getReviewQueue(engagementId?: number) {
    const url = engagementId ? `${API_BASE}/reporting/workpapers/review_queue/?engagement=${engagementId}` : `${API_BASE}/reporting/workpapers/review_queue/`;
    const res = await fetch(url);
    return res.json();
  },
  async performWorkpaperReviewAction(id: number, actionType: string, payload: {
    notes?: string;
    reason?: string;
    reviewer_name?: string;
    verify_evidence?: boolean;
    evidence_reference?: string;
    override_separation_of_duties?: boolean;
  }) {
    const res = await fetch(`${API_BASE}/reporting/workpapers/${id}/review_action/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action_type: actionType, ...payload }),
    });
    return res.json();
  },
  async updateWorkpaperStatus(id: number, newStatus: string, comments: string) {
    const res = await fetch(`${API_BASE}/reporting/workpapers/${id}/update_status/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus, comments }),
    });
    return res.json();
  },
  async regenerateWorkpapers(engagementId?: number) {
    const res = await fetch(`${API_BASE}/reporting/workpapers/regenerate/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ engagement: engagementId }),
    });
    return res.json();
  },
  async getAdjustments(engagementId?: number) {
    const url = engagementId ? `${API_BASE}/reporting/adjustments/?engagement=${engagementId}` : `${API_BASE}/reporting/adjustments/`;
    const res = await fetch(url);
    const data = await res.json();
    return data.results || data;
  },

  // Reports & Instant Demo
  async getReports(engagementId?: number) {
    const url = engagementId ? `${API_BASE}/reporting/reports/?engagement=${engagementId}` : `${API_BASE}/reporting/reports/`;
    const res = await fetch(url);
    const data = await res.json();
    return data.results || data;
  },
  async generateReport(engagementId?: number) {
    const res = await fetch(`${API_BASE}/reporting/reports/generate/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ engagement: engagementId }),
    });
    return res.json();
  },

  // --- Phase 4: India-Specific Audit Intelligence ---

  // Workflow Config & Scope
  async getWorkflowConfig(engagementId?: number | string) {
    if (!engagementId) return null;
    const res = await fetch(`${API_BASE}/companies/engagements/${engagementId}/workflow_config/`);
    if (!res.ok) return null;
    return res.json();
  },
  async getDocumentMatrix(engagementId?: number | string) {
    if (!engagementId) return null;
    const res = await fetch(`${API_BASE}/companies/engagements/${engagementId}/document_matrix/`);
    if (!res.ok) return null;
    return res.json();
  },
  async updateWorkflowConfig(engagementId?: number | string, data?: any) {
    if (!engagementId) return null;
    const res = await fetch(`${API_BASE}/companies/engagements/${engagementId}/workflow_config/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return res.json();
  },

  // Schedule III & Adjusted Balances
  async getUnmappedAccounts(companyId?: number) {
    const url = companyId ? `${API_BASE}/accounting/ledgers/unmapped/?company=${companyId}` : `${API_BASE}/accounting/ledgers/unmapped/`;
    const res = await fetch(url);
    return res.json();
  },
  async approveAccountMapping(accountId: number, data: { schedule_iii_group: string; schedule_iii_division?: string; mapping_notes?: string }) {
    const res = await fetch(`${API_BASE}/accounting/ledgers/${accountId}/approve_mapping/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return res.json();
  },
  async getAdjustedBalances(engagementId?: number) {
    const url = engagementId ? `${API_BASE}/accounting/ledgers/adjusted_balances/?engagement=${engagementId}` : `${API_BASE}/accounting/ledgers/adjusted_balances/`;
    const res = await fetch(url);
    return res.json();
  },

  // Fixed Assets & Dual Depreciation
  async getFixedAssets(engagementId?: number) {
    const url = engagementId ? `${API_BASE}/audit/fixed-assets/?engagement=${engagementId}` : `${API_BASE}/audit/fixed-assets/`;
    const res = await fetch(url);
    const data = await res.json();
    return data.results || data;
  },
  async runFarAudit(engagementId: number, farRecords?: any[]) {
    const res = await fetch(`${API_BASE}/audit/fixed-assets/audit/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ engagement: engagementId, far_records: farRecords || [] }),
    });
    return res.json();
  },

  // Subledger Ageing & MSMED Act Section 43B(h)
  async getSubledgerAging(engagementId?: number, itemType?: string, isOverdue43bh?: boolean) {
    let url = `${API_BASE}/audit/subledger-aging/?`;
    if (engagementId) url += `engagement=${engagementId}&`;
    if (itemType) url += `item_type=${itemType}&`;
    if (isOverdue43bh !== undefined) url += `is_overdue_43bh=${isOverdue43bh}&`;
    const res = await fetch(url);
    const data = await res.json();
    return data.results || data;
  },
  async runSubledgerAging(engagementId: number, records: any[], asOfDate?: string) {
    const res = await fetch(`${API_BASE}/audit/subledger-aging/process/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ engagement: engagementId, records, as_of_date: asOfDate }),
    });
    return res.json();
  },
  async runInventoryAudit(engagementId: number, stockItems: any[]) {
    const res = await fetch(`${API_BASE}/audit/subledger-aging/inventory_audit/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ engagement: engagementId, stock_items: stockItems }),
    });
    return res.json();
  },

  // Related Parties & Forensic Journal Scrutiny (SA 240)
  async getRelatedParties(engagementId?: number) {
    const url = engagementId ? `${API_BASE}/audit/related-parties/?engagement=${engagementId}` : `${API_BASE}/audit/related-parties/`;
    const res = await fetch(url);
    const data = await res.json();
    return data.results || data;
  },
  async runRelatedPartyScrutiny(engagementId: number, partiesData?: any[]) {
    const res = await fetch(`${API_BASE}/audit/related-parties/scrutinize/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ engagement: engagementId, parties_data: partiesData }),
    });
    return res.json();
  },
  async runForensicJournals(engagementId?: number) {
    const url = engagementId ? `${API_BASE}/audit/executions/forensic_journals/?engagement=${engagementId}` : `${API_BASE}/audit/executions/forensic_journals/`;
    const res = await fetch(url);
    return res.json();
  },

  // Statutory Matrices: CARO 2020 & Form 3CD
  async getStatutoryApplicability(engagementId?: number) {
    const url = engagementId ? `${API_BASE}/audit/statutory-clauses/applicability/?engagement=${engagementId}` : `${API_BASE}/audit/statutory-clauses/applicability/`;
    const res = await fetch(url);
    return res.json();
  },
  async getStatutoryClauses(engagementId?: number, formType?: string) {
    let url = `${API_BASE}/audit/statutory-clauses/?`;
    if (engagementId) url += `engagement=${engagementId}&`;
    if (formType) url += `form_type=${formType}&`;
    const res = await fetch(url);
    const data = await res.json();
    return data.results || data;
  },
  async initializeStatutoryClauses(engagementId: number | string) {
    const res = await fetch(`${API_BASE}/audit/statutory-clauses/initialize/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ engagement: engagementId }),
    });
    return res.json();
  },
  async updateStatutoryClause(clauseId: number, data: any) {
    const res = await fetch(`${API_BASE}/audit/statutory-clauses/${clauseId}/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json();
      throw err;
    }
    return res.json();
  },

  // --- Phase 5 & 6: Governance, Completion Checklist & Reports ---

  // Workpaper Review & Approval
  async reviewWorkpaper(wpId: number, data: { action_type: string; notes?: string; reason?: string; evidence_reference?: string; override_separation_of_duties?: boolean; verify_evidence?: boolean }) {
    const res = await fetch(`${API_BASE}/reporting/workpapers/${wpId}/review_action/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json();
      throw err;
    }
    return res.json();
  },
  async getOutstandingReviews(engagementId?: number) {
    const url = engagementId ? `${API_BASE}/reporting/workpapers/outstanding_reviews/?engagement=${engagementId}` : `${API_BASE}/reporting/workpapers/outstanding_reviews/`;
    const res = await fetch(url);
    return res.json();
  },

  // Completion Checklist & Finalization
  async getCompletionChecklist(engagementId?: number | string) {
    if (!engagementId) return null;
    const res = await fetch(`${API_BASE}/companies/engagements/${engagementId}/completion_checklist/`);
    if (!res.ok) return null;
    return res.json();
  },
  async finalizeEngagement(engagementId?: number | string, justification?: string, caCredentials?: Record<string, any>) {
    if (!engagementId) return { success: false, error: 'No active engagement selected' };
    const res = await fetch(`${API_BASE}/companies/engagements/${engagementId}/finalize/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        justification,
        ...(caCredentials || {})
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw err;
    }
    return res.json();
  },
  async overrideChecklistException(engagementId?: number | string, code: string = '', reason: string = '') {
    if (!engagementId) return { error: 'No active engagement selected' };
    const res = await fetch(`${API_BASE}/companies/engagements/${engagementId}/override_exception/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, reason }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw err;
    }
    return res.json();
  },

  // Consolidated & Document Processing Reports
  async getConsolidatedReport(engagementId?: number) {
    const url = engagementId ? `${API_BASE}/reporting/reports/consolidated_report/?engagement=${engagementId}` : `${API_BASE}/reporting/reports/consolidated_report/`;
    const res = await fetch(url);
    return res.json();
  },
  async getDocumentProcessingReport(engagementId?: number) {
    const url = engagementId ? `${API_BASE}/reporting/reports/document_processing_report/?engagement=${engagementId}` : `${API_BASE}/reporting/reports/document_processing_report/`;
    const res = await fetch(url);
    return res.json();
  },
  async downloadReportExport(format: 'pdf' | 'excel' | 'csv', engagementId?: number) {
    const endpoint = format === 'pdf' ? 'export_pdf' : format === 'excel' ? 'export_excel' : 'export_csv';
    const url = engagementId ? `${API_BASE}/reporting/reports/${endpoint}/?engagement=${engagementId}` : `${API_BASE}/reporting/reports/${endpoint}/`;
    const res = await fetch(url);
    if (!res.ok) {
      let errorMsg = `Export failed with status ${res.status}`;
      try {
        const errJson = await res.json();
        errorMsg = errJson.error || errJson.detail || errorMsg;
      } catch {
        // Fallback to text status
      }
      throw new Error(errorMsg);
    }
    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition');
    let filename = `audit_report_${format}.${format === 'excel' ? 'xlsx' : format}`;
    if (disposition && disposition.indexOf('filename=') !== -1) {
      const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition);
      if (matches && matches[1]) {
        filename = matches[1].replace(/['"]/g, '');
      }
    }
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(downloadUrl);
    return { filename };
  },

  // Automation Pipeline & Processing Runs
  async startProcessingRun(formData: FormData) {
    const res = await fetch(`${API_BASE}/ingestion/runs/`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Failed to start processing run' }));
      throw err;
    }
    return res.json();
  },
  async getProcessingRuns() {
    const res = await fetch(`${API_BASE}/ingestion/runs/`);
    const data = await res.json();
    return data.results || data;
  },
  async getProcessingRun(idOrRunId: string | number) {
    const res = await fetch(`${API_BASE}/ingestion/runs/${idOrRunId}/`);
    if (!res.ok) {
      throw new Error(`Processing run ${idOrRunId} not found`);
    }
    return res.json();
  },
  async retryProcessingRun(idOrRunId: string | number) {
    const res = await fetch(`${API_BASE}/ingestion/runs/${idOrRunId}/retry/`, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Failed to retry processing run' }));
      throw err;
    }
    return res.json();
  },
  async getLatestProcessingRun() {
    const res = await fetch(`${API_BASE}/ingestion/runs/latest/`);
    if (!res.ok) return null;
    return res.json();
  },
  async runSyntheticDemo() {
    const res = await fetch(`${API_BASE}/ingestion/runs/run_synthetic_demo/`, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Failed to run synthetic demo' }));
      throw err;
    }
    return res.json();
  },
  async downloadAuditPackage(idOrRunId: string | number) {
    const res = await fetch(`${API_BASE}/ingestion/runs/${idOrRunId}/download_package/`);
    if (!res.ok) {
      throw new Error('Failed to download audit package');
    }
    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition');
    let filename = `Captrix_Audit_Package_${idOrRunId}.zip`;
    if (disposition && disposition.indexOf('filename=') !== -1) {
      const matches = /filename="([^"]*)"/.exec(disposition);
      if (matches && matches[1]) filename = matches[1];
    }
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(downloadUrl);
    return { filename };
  },
};


