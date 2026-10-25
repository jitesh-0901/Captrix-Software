export interface Company {
  id: number;
  name: string;
  cin: string;
  pan: string;
  gstin: string;
  entity_type: string;
  business_tier?: 'TIER_1_SMALL' | 'TIER_2_SME' | 'TIER_3_MID' | 'TIER_4_ENTERPRISE';
  parent_company?: number | null;
  branch_name?: string;
  branch_code?: string;
  registered_address: string;
  industry: string;
}

export interface FinancialYear {
  id: number;
  label: string;
  start_date: string;
  end_date: string;
  is_active: boolean;
}

export interface Engagement {
  id: number;
  company: number;
  company_name?: string;
  financial_year: number;
  fy_label?: string;
  title: string;
  engagement_type: string;
  status: string;
  overall_materiality: string;
  performance_materiality: string;
  clearly_trivial_threshold: string;
}

export interface DocumentRecord {
  id: number;
  engagement: number;
  engagement_title?: string;
  original_filename: string;
  file_hash: string;
  file_size_bytes: number;
  document_type: string;
  status: 'UPLOADED' | 'PROCESSING' | 'VERIFIED' | 'REVIEW_REQUIRED' | 'FAILED';
  extracted_summary: {
    total_rows?: number;
    valid_rows?: number;
    review_required_rows?: number;
    detected_type?: string;
    headers?: string[];
  };
  uploaded_at: string;
}

export interface ExtractedRecord {
  id: number;
  row_index: number;
  source_location: string;
  raw_data: Record<string, any>;
  normalized_data: Record<string, any>;
  validation_status: 'VALID' | 'REVIEW_REQUIRED' | 'INVALID';
  validation_notes: string;
  confidence_score: string;
}

export interface Transaction {
  id: number;
  voucher_number: string;
  voucher_type: string;
  date: string;
  ledger_account: number;
  account_name?: string;
  counterparty: string;
  narration: string;
  debit_amount: string;
  credit_amount: string;
  is_unusual: boolean;
  risk_flags: string[];
}

export interface TrialBalanceAccount {
  account_name: string;
  debit: string;
  credit: string;
  net_balance: string;
  balance_type: 'Dr' | 'Cr';
  schedule_iii_group: string;
}

export interface TrialBalanceSnapshot {
  id: number;
  as_of_date: string;
  total_debits: string;
  total_credits: string;
  difference_amount: string;
  is_balanced: boolean;
  status: string;
  accounts_snapshot: TrialBalanceAccount[];
}

export interface ReconciliationRun {
  id: number;
  recon_type: string;
  status: string;
  as_of_date: string;
  balance_per_books: string;
  balance_per_statement: string;
  timing_differences_amount: string;
  unreconciled_difference: string;
  matched_count: number;
  unmatched_count: number;
  unresolved_count?: number;
  date_tolerance_days?: number;
  summary_data: Record<string, any>;
  items?: ReconciliationItem[];
}

export interface ReconciliationItem {
  id: number;
  source_type: string;
  item_date: string;
  reference_number: string;
  description: string;
  party_name: string;
  amount: string;
  debit_amount: string;
  credit_amount: string;
  is_matched: boolean;
  timing_category: string;
  match_type: string;
  match_notes: string;
  is_approved: boolean;
}

export interface ProcedureExecution {
  id: number;
  procedure: number;
  procedure_code: string;
  procedure_title: string;
  category: string;
  status: 'NOT_STARTED' | 'RUNNING' | 'PASSED_NO_EXCEPTIONS' | 'PASSED_WITH_EXCEPTIONS' | 'BLOCKED' | 'REVIEW_REQUIRED';
  tested_records_count: number;
  exceptions_count: number;
  summary_findings: string;
  results_payload: Record<string, any>;
  executed_at: string;
}

export interface ExceptionItem {
  id: number;
  finding_reference?: string;
  title: string;
  rule_code?: string;
  category: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  assertion?: 'COMPLETENESS' | 'EXISTENCE' | 'ACCURACY' | 'CUT_OFF' | 'RIGHTS_OBLIGATIONS' | 'PRESENTATION';
  status: 'OPEN' | 'IN_REVIEW' | 'EVIDENCE_REQUESTED' | 'RESOLVED' | 'ACCEPTED_RISK';
  amount_involved: string;
  explanation: string;
  recommended_action: string;
  management_response?: string;
  resolution_notes: string;
  resolution_history?: Array<{
    timestamp: string;
    status: string;
    notes: string;
    reviewer?: string;
  }>;
  source_reference: string;
  created_at: string;
}

export interface Workpaper {
  id: number;
  wp_reference: string;
  title: string;
  audit_area: string;
  audit_objective: string;
  scope_and_coverage: string;
  testing_methodology: string;
  results_summary: string;
  exceptions_noted: string;
  proposed_conclusion: string;
  status: 'DRAFT' | 'READY_FOR_REVIEW' | 'REVIEW_REQUIRED' | 'RETURNED_FOR_CORRECTION' | 'REVIEWED' | 'APPROVED' | 'REJECTED';
  review_comments: string;
  review_notes?: string;
  return_reason?: string;
  approval_reason?: string;
  rejection_reason?: string;
  evidence_verified: boolean;
  evidence_reference?: string;
  review_required: boolean;
  preparer?: number;
  preparer_name?: string;
  reviewer?: number;
  reviewer_name?: string;
  reviewed_by_name?: string;
  version: number;
  version_history?: Array<{
    version: number;
    action: string;
    timestamp: string;
    user: string;
    notes?: string;
    return_reason?: string;
    approval_reason?: string;
    evidence_reference?: string;
  }>;
  reviewed_at?: string;
  approved_at?: string;
}

export interface ProposedAdjustment {
  id: number;
  adjustment_number: string;
  title: string;
  reason: string;
  journal_entries: Array<{
    account: string;
    debit: string;
    credit: string;
  }>;
  total_debit: string;
  total_credit: string;
  pnl_impact: string;
  status: string;
}

export interface GeneratedReport {
  id: number;
  report_type: string;
  title: string;
  file_url: string | null;
  file_format: string;
  summary_data?: Record<string, any>;
  is_stale?: boolean;
  generated_at: string;
}

export interface ChecklistItem {
  code: string;
  title: string;
  category: string;
  is_satisfied: boolean;
  is_mandatory: boolean;
  is_overridden?: boolean;
  override_note?: string;
  details: string;
  missing_items?: string[];
  pending_files?: string[];
  difference_amount?: string;
  open_material_count?: number;
  incomplete_count?: number;
  unapproved_count?: number;
  pending_count?: number;
  pending_action_count?: number;
}

export interface CompletionChecklistResult {
  engagement_id: number;
  company_name: string;
  financial_year: string;
  engagement_type: string;
  overall_status: 'COMPLETED' | 'READY_TO_FINALIZE' | 'BLOCKED';
  is_finalized: boolean;
  finalized_at: string | null;
  finalized_by: string | null;
  completion_percentage: number;
  can_finalize: boolean;
  blockers: string[];
  raw_blockers_count: number;
  permitted_exceptions: Array<{
    code: string;
    reason: string;
    authorized_by: string;
    timestamp: string;
  }>;
  checklist_items: ChecklistItem[];
}

export interface ConsolidatedAuditReport {
  report_name: string;
  engagement_id: number;
  company_name: string;
  financial_year: string;
  generated_at: string;
  section_a: {
    section_code: string;
    title: string;
    company_name: string;
    cin: string;
    pan: string;
    gstin: string;
    entity_type: string;
    registered_address: string;
    industry: string;
    financial_year: string;
    reporting_period: string;
    engagement_type: string;
    report_generation_date: string;
    report_version: string;
    source_coverage: string;
    report_status: string;
    is_finalized: boolean;
  };
  section_b: {
    section_code: string;
    title: string;
    financial_data_available: boolean;
    documents_processed_successfully: number;
    documents_requiring_review: number;
    documents_failed: number;
    trial_balance_status: string;
    trial_balance_balanced: boolean;
    trial_balance_difference: string;
    reconciliation_status: string;
    audit_procedures_executed: number;
    procedures_passed: number;
    procedures_with_exceptions: number;
    total_exceptions: number;
    critical_unresolved_exceptions: number;
    high_unresolved_exceptions: number;
    total_workpapers: number;
    unreviewed_workpapers_count: number;
    overall_materiality: string;
    performance_materiality: string;
    recommended_next_actions: string[];
  };
  section_c: {
    section_code: string;
    title: string;
    currency: string;
    data_source: string;
    calculation_basis: string;
    revenue_from_operations: string;
    total_expenses: string;
    net_profit_loss: string;
    total_assets: string;
    total_liabilities: string;
    total_equity: string;
    cash_and_bank_balances: string;
    trade_receivables: string;
    trade_payables: string;
    financial_ratios: FinancialRatio[];
  };
  section_d: {
    section_code: string;
    title: string;
    expected_documents_count: number;
    uploaded_documents_count: number;
    processed_documents_count: number;
    failed_documents_count: number;
    missing_documents_count: number;
    document_quality_assessment: string;
    blocked_analyses: string[];
  };
  section_e: {
    section_code: string;
    title: string;
    trial_balance_as_of: string;
    total_debits: string;
    total_credits: string;
    trial_balance_difference: string;
    is_balanced: boolean;
    total_accounts_count: number;
    unmapped_accounts_count: number;
    unmapped_accounts_alert: boolean;
    suspense_accounts_count: number;
    suspense_balance_total: string;
    unusual_transactions_count: number;
    ledger_to_tb_reconciliation: string;
  };
  section_f: {
    section_code: string;
    title: string;
    reconciliations_executed_count: number;
    bank_reconciliation_summary: Record<string, any>;
    cross_document_checks: Array<{
      recon_type: string;
      recon_title: string;
      status: string;
      matched_count: number;
      unmatched_count: number;
      unreconciled_variance: string;
      executed_at: string;
    }>;
  };
  section_g: {
    section_code: string;
    title: string;
    receivables_aging_total: string;
    receivables_count: number;
    payables_aging_total: string;
    payables_count: number;
    msme_overdue_section_43bh_total: string;
    msme_overdue_count: number;
    fixed_assets_count: number;
    fixed_assets_gross_block: string;
    schedule_ii_book_depreciation: string;
    section_32_tax_depreciation: string;
    depreciation_variance: string;
  };
  section_h: {
    section_code: string;
    title: string;
    schedule_iii_framework: string;
    tax_audit_form: string;
    caro_applicable: boolean;
    caro_clauses_count: number;
    caro_exempt_badge: boolean;
    form_3cd_clauses_count: number;
    section_43bh_msme_compliance: string;
    section_40a3_cash_payments: string;
  };
  section_i: {
    section_code: string;
    title: string;
    total_procedures_count: number;
    procedures: Array<{
      procedure_code: string;
      title: string;
      category: string;
      standard: string;
      rule_version: string;
      status: string;
      records_tested: number;
      exceptions_count: number;
      summary_findings: string;
      executed_at: string;
    }>;
  };
  section_j: {
    section_code: string;
    title: string;
    total_exceptions_count: number;
    critical_count: number;
    high_count: number;
    exceptions: Array<{
      exception_id: string;
      title: string;
      rule_code?: string;
      category: string;
      severity: string;
      status: string;
      amount_involved: string;
      explanation: string;
      recommended_action: string;
      source_reference: string;
      resolution_notes: string;
    }>;
  };
  section_k: {
    section_code: string;
    title: string;
    total_workpapers_count: number;
    approved_count: number;
    workpapers: Array<{
      wp_reference: string;
      title: string;
      audit_area: string;
      status: string;
      audit_objective: string;
      results_summary: string;
      proposed_conclusion: string;
      preparer: string;
      reviewer: string;
      version: number;
      approval_reason?: string;
    }>;
  };
  section_l: {
    section_code: string;
    title: string;
    total_adjustments_count: number;
    adjustments: Array<{
      adjustment_number: string;
      title: string;
      reason: string;
      status: string;
      total_debit: string;
      total_credit: string;
      is_balanced: boolean;
      pnl_impact: string;
      journal_entries: Array<{ account: string; debit: string; credit: string }>;
    }>;
  };
  section_m: {
    section_code: string;
    title: string;
    can_finalize: boolean;
    completion_percentage: number;
    outstanding_actions_count: number;
    actions: Array<{
      code: string;
      title: string;
      category: string;
      priority: string;
      details: string;
    }>;
  };
  section_n: {
    section_code: string;
    title: string;
    verified_items_summary: string[];
    statutory_auditor_disclaimer: string;
    responsible_ca_signoff_box: {
      firm_name: string;
      lead_partner: string;
      membership_number: string;
      udin: string;
      place: string;
      date: string;
    };
  };
}

export interface DocumentUploadReport {
  report_name: string;
  company_name: string;
  engagement_title: string;
  financial_year: string;
  generated_at: string;
  total_documents: number;
  total_records_processed: number;
  total_valid_records: number;
  total_review_required_records: number;
  total_failed_records: number;
  duplicate_files_detected: number;
  statutory_disclaimer: string;
  files: Array<{
    document_id: number;
    original_filename: string;
    file_format: string;
    mime_type: string;
    file_size_bytes: number;
    file_hash_sha256: string;
    document_type: string;
    detected_category: string;
    status: string;
    uploaded_at: string;
    job_id?: number;
    job_stage: string;
    total_records_processed: number;
    successfully_extracted_records: number;
    records_requiring_review: number;
    failed_or_skipped_records: number;
    is_duplicate_file: boolean;
    duplicate_warning?: string;
    error_message?: string;
    source_coverage: string;
    accounting_verification_status: string;
  }>;
}

export interface FinancialRatio {
  name: string;
  category: string;
  value: number;
  unit: string;
  benchmark: string;
  status: string;
  interpretation: string;
}

export interface EngagementWorkflowConfig {
  id?: number;
  engagement: number;
  scope_description: string;
  applicable_framework: string;
  caro_applicable: boolean;
  form_3cd_applicable: boolean;
  form_type: string;
  msmed_applicable: boolean;
  schedule_iii_division: string;
  required_documents: Array<{ title: string; status: string }>;
  milestones: Record<string, string>;
  completion_criteria: Record<string, any>;
  completion_status: string;
}

export interface FixedAssetItem {
  id: number;
  asset_id: string;
  asset_name: string;
  category: string;
  acquisition_date: string;
  put_to_use_date: string;
  original_cost: string;
  useful_life_years: string;
  sch_ii_depreciation: string;
  sec_32_rate: string;
  sec_32_depreciation: string;
  accumulated_depreciation: string;
  carrying_amount: string;
  location: string;
  is_duplicate_candidate: boolean;
}

export interface SubledgerAgingRecord {
  id: number;
  item_type: 'RECEIVABLE' | 'PAYABLE';
  party_name: string;
  party_pan: string;
  party_gstin: string;
  is_msme: boolean;
  msme_type: 'MICRO' | 'SMALL' | 'MEDIUM' | 'NON_MSME';
  invoice_number: string;
  invoice_date: string;
  due_date: string;
  total_amount: string;
  outstanding_amount: string;
  ageing_days: number;
  ageing_bucket: string;
  is_disputed: boolean;
  is_overdue_43bh: boolean;
  overdue_days_msme: number;
}

export interface RelatedPartyRecord {
  id: number;
  party_name: string;
  pan: string;
  relationship_type: string;
  applicable_standard: string;
  is_active: boolean;
  notes: string;
}

export interface StatutoryClauseAuditRecord {
  id: number;
  form_type: 'FORM_3CD' | 'CARO_2020' | 'FORM_3CA' | 'FORM_3CB';
  clause_number: string;
  clause_title: string;
  is_applicable: boolean;
  calculated_amount: string;
  evidence_status: 'AVAILABLE' | 'PARTIAL' | 'MISSING';
  compliance_status: 'COMPLIANT' | 'EXCEPTION_NOTED' | 'EXEMPT';
  auditor_remarks: string;
  statutory_citation: string;
  rule_version: string;
  verified_at?: string | null;
}

export type ProcessingRunStage =
  | 'UPLOAD_RECEIVED'
  | 'FILE_VALIDATION'
  | 'DOCUMENT_CLASSIFICATION'
  | 'DATA_EXTRACTION'
  | 'DATA_VALIDATION'
  | 'ACCOUNT_NORMALIZATION'
  | 'ACCOUNTING_CALCULATIONS'
  | 'RECONCILIATION'
  | 'AUDIT_PROCEDURES'
  | 'EXCEPTION_GENERATION'
  | 'WORKPAPER_GENERATION'
  | 'REPORT_ASSEMBLY'
  | 'OUTPUT_VALIDATION'
  | 'COMPLETED';

export type ProcessingRunStatus =
  | 'QUEUED'
  | 'RUNNING'
  | 'COMPLETED'
  | 'PARTIALLY_COMPLETED'
  | 'AWAITING_CLARIFICATION'
  | 'REVIEW_REQUIRED'
  | 'BLOCKED'
  | 'FAILED'
  | 'CANCELLED';

export interface StageStatusInfo {
  status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'BLOCKED' | 'FAILED';
  duration_ms: number;
  details: string;
  updated_at: string;
}

export interface StageLogEntry {
  time: string;
  stage: string;
  level: 'INFO' | 'WARNING' | 'ERROR';
  message: string;
}

export interface ProcessingRun {
  id: number;
  run_id: string;
  company: number | null;
  company_name?: string;
  engagement: number | null;
  engagement_title?: string;
  status: ProcessingRunStatus;
  current_stage: ProcessingRunStage;
  progress_percent: number;
  stage_statuses: Record<string, StageStatusInfo>;
  stage_logs: StageLogEntry[];
  documents: DocumentRecord[];
  generated_reports?: any[];
  zip_package?: string;
  zip_package_url?: string;
  zip_package_hash?: string;
  summary_metrics: Record<string, any>;
  blockers: any[];
  started_at: string;
  completed_at?: string;
  updated_at: string;
}


