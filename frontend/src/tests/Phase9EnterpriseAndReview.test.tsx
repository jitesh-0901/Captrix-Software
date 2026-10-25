import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import React from 'react';
import { ReviewQueuePage } from '../pages/ReviewQueuePage';
import { ClientsPage } from '../pages/ClientsPage';
import { EngagementsPage } from '../pages/EngagementsPage';
import { SettingsPage } from '../pages/SettingsPage';

describe('Captrix AI — Phase 9 Enterprise & Review Queue Tests', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (url.includes('review_queue')) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                metrics: {
                  total: 4,
                  ready_for_review: 2,
                  returned_for_correction: 1,
                  approved: 1,
                  draft: 0,
                },
                items: [
                  {
                    id: 1,
                    wp_reference: 'WP-A101',
                    title: 'Cash & Bank Verification',
                    audit_area: 'Current Assets',
                    audit_objective: 'Reconcile ledger with bank statements',
                    scope_and_coverage: '100% of accounts',
                    testing_methodology: 'Third-party confirmation',
                    results_summary: 'Reconciled without variance',
                    exceptions_noted: '',
                    proposed_conclusion: 'Satisfactory',
                    status: 'READY_FOR_REVIEW',
                    evidence_verified: true,
                    preparer_name: 'Senior Associate',
                    reviewer_name: 'Partner CA',
                  },
                ],
              }),
          });
        }
        if (url.includes('engagements')) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve([
                {
                  id: 1,
                  title: 'Statutory Audit FY 2024-25',
                  engagement_type: 'STATUTORY',
                  company_name: 'Apex Infotech Private Limited',
                  fy_label: 'FY 2024-25',
                  status: 'FIELDWORK',
                  overall_materiality: '500000.00',
                  performance_materiality: '375000.00',
                  clearly_trivial_threshold: '25000.00',
                },
              ]),
          });
        }
        if (url.includes('companies')) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve([
                {
                  id: 1,
                  name: 'Apex Infotech Private Limited',
                  cin: 'U72900MH2021PTC123456',
                  pan: 'AABCA1234F',
                  gstin: '27AABCA1234F1Z5',
                  entity_type: 'PVT_LTD',
                  business_tier: 'TIER_3_MID',
                  branch_name: 'Head Office',
                  branch_code: 'HO-01',
                  industry: 'Information Technology',
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

  it('renders ReviewQueuePage with SA 220 metric cards and items', async () => {
    render(
      <BrowserRouter>
        <ReviewQueuePage />
      </BrowserRouter>
    );

    expect(screen.getByText('Review Queue & Sign-Off Controls')).toBeDefined();
    expect(await screen.findByText('WP-A101')).toBeDefined();
    expect(screen.getByText('Cash & Bank Verification')).toBeDefined();
    expect(screen.getByText('Evidence Verified')).toBeDefined();
  });

  it('renders ClientsPage with company profile and business tier badge', async () => {
    render(
      <BrowserRouter>
        <ClientsPage />
      </BrowserRouter>
    );

    expect(screen.getByText('Clients & Company Master')).toBeDefined();
    expect(await screen.findByText('Apex Infotech Private Limited')).toBeDefined();
    expect(screen.getByText('Tier 3 — Mid-Market Pvt Ltd')).toBeDefined();
  });

  it('renders EngagementsPage with SA 320 materiality cards', async () => {
    render(
      <BrowserRouter>
        <EngagementsPage />
      </BrowserRouter>
    );

    expect(screen.getByText('Audit Engagements & Scoping')).toBeDefined();
    expect(await screen.findByText('Statutory Audit FY 2024-25')).toBeDefined();
    expect(screen.getByText('Overall Materiality (SA 320)')).toBeDefined();
  });

  it('renders SettingsPage with SA 220 separation-of-duties and ICAI ethics controls', () => {
    render(
      <BrowserRouter>
        <SettingsPage />
      </BrowserRouter>
    );

    expect(screen.getByText('Settings & Access Control')).toBeDefined();
    expect(screen.getByText('ICAI Professional Sign-Off & Ethics Policy')).toBeDefined();
    expect(screen.getByText('Separation of Duties (SA 220 / SQC 1)')).toBeDefined();
  });
});
