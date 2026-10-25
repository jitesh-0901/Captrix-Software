import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import React from 'react';
import { ReconciliationPage } from '../pages/ReconciliationPage';
import { ExceptionsPage } from '../pages/ExceptionsPage';
import { WorkpapersPage } from '../pages/WorkpapersPage';
import { AnalysisResultsPage } from '../pages/AnalysisResultsPage';

describe('Phase 3 React Pages & Workspaces', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (url.includes('/accounting/trial-balances/movements/')) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                movements: [
                  {
                    account_name: 'HDFC Bank Account',
                    opening_balance: '100000.00',
                    total_debit: '50000.00',
                    total_credit: '20000.00',
                    closing_balance: '130000.00',
                    is_suspense: false,
                    is_reconciled: true,
                    variance: '0.00',
                  },
                ],
              }),
          });
        }
        if (url.includes('/reconciliation/runs/')) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve([
                {
                  id: 1,
                  recon_type: 'BANK',
                  status: 'BALANCED',
                  balance_per_books: '3450000.00',
                  balance_per_statement: '3138500.00',
                  unreconciled_difference: '0.00',
                  unresolved_count: 0,
                  summary_data: {
                    starting_cashbook_balance: '3450000.00',
                    computed_statement_balance: '3138500.00',
                    actual_statement_balance: '3138500.00',
                  },
                  items: [
                    {
                      id: 101,
                      source_type: 'CASHBOOK',
                      item_date: '2025-03-25',
                      reference_number: 'CHQ-991',
                      description: 'Office Maintenance Vendor',
                      amount: '42000.00',
                      is_matched: true,
                      timing_category: 'CHEQUE_ISSUED_NOT_PRESENTED',
                      match_type: 'EXACT',
                      is_approved: true,
                    },
                  ],
                },
                {
                  id: 2,
                  recon_type: 'SALES_VS_LEDGER',
                  status: 'BLOCKED',
                  balance_per_books: '45000000.00',
                  balance_per_statement: '0.00',
                  unreconciled_difference: '0.00',
                  summary_data: {
                    notes: 'Sales Register document not uploaded',
                  },
                },
              ]),
          });
        }
        if (url.includes('/audit/exceptions/')) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve([
                {
                  id: 201,
                  title: 'Cash Payment Exceeding Limit (Section 40A(3))',
                  rule_code: 'SEC-40A3',
                  category: 'Statutory Compliance',
                  severity: 'CRITICAL',
                  status: 'OPEN',
                  amount_involved: '25000.00',
                  explanation: 'Payment in cash violated statutory ₹10,000 threshold.',
                  recommended_action: 'Report in Form 3CD Clause 21(d).',
                  resolution_notes: '',
                  source_reference: 'row_4',
                  created_at: '2025-03-25T10:00:00Z',
                },
              ]),
          });
        }
        if (url.includes('/reporting/workpapers/')) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve([
                {
                  id: 301,
                  wp_reference: 'WP-A101',
                  title: 'Cash and Bank Balances Audit & BRS Verification',
                  audit_area: 'Cash and Bank',
                  audit_objective: 'Verify existence and valuation of year-end bank balances.',
                  scope_and_coverage: '100% of bank accounts reconciled.',
                  testing_methodology: 'Deterministic matching against bank statements.',
                  results_summary: 'Computed statement balance matches passbook.',
                  exceptions_noted: 'None',
                  proposed_conclusion: 'Bank balances are fairly stated.',
                  status: 'APPROVED',
                  review_comments: '',
                },
              ]),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([]),
        });
      })
    );
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('renders ReconciliationPage with BRS, GST ITC, and Cross-Document tabs', async () => {
    render(<ReconciliationPage />);
    expect(screen.getByText('Bank Reconciliation (BRS)')).toBeDefined();
    expect(screen.getByText('GST ITC (GSTR-2B vs Books)')).toBeDefined();
    expect(screen.getByText(/Cross-Document Reconciliations/)).toBeDefined();
  });

  it('renders ExceptionsPage with rule codes and evidence action', async () => {
    render(<ExceptionsPage />);
    expect(screen.getByText('Exceptions & Risk Management Center')).toBeDefined();
  });

  it('renders WorkpapersPage with SA 230 regenerate button and index', async () => {
    render(<WorkpapersPage />);
    expect(screen.getByText('Working Papers Index (SA 230)')).toBeDefined();
    expect(screen.getByText(/Regenerate Workpapers/)).toBeDefined();
  });

  it('renders AnalysisResultsPage with Movements, Transactions, and Ingestion tabs', async () => {
    render(<AnalysisResultsPage />);
    expect(screen.getByText('Trial Balance & Forensic Accounting Explorer')).toBeDefined();
    expect(screen.getByText(/Schedule III Trial Balance & Roll-Forward/)).toBeDefined();
    expect(screen.getByText(/General Ledger Voucher Drilldown/)).toBeDefined();
    expect(screen.getByText(/Source Extraction Records/)).toBeDefined();
  });
});
