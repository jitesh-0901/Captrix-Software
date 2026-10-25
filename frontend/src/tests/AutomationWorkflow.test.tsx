import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { UploadPage } from '../pages/UploadPage';
import { HistoryPage } from '../pages/HistoryPage';
import { ProcessingStatusPage } from '../pages/ProcessingStatusPage';
import { FinalAuditFilePage } from '../pages/FinalAuditFilePage';

describe('Captrix AI — Automation-First Workflow Tests', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (url.includes('/api/ingestion/runs/latest/')) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                id: 1,
                run_id: 'RUN-20261011-DEMO',
                company_name: 'Vanguard Industrial Automations Pvt Ltd',
                engagement_title: 'Statutory Audit FY 2024-25',
                status: 'COMPLETED',
                current_stage: 'COMPLETED',
                progress_percent: 100,
                stage_statuses: {
                  UPLOAD_RECEIVED: { status: 'COMPLETED', duration_ms: 120 },
                  COMPLETED: { status: 'COMPLETED', duration_ms: 50 },
                },
                stage_logs: [
                  { time: '2026-10-11T10:00:00Z', stage: 'UPLOAD_RECEIVED', level: 'INFO', message: 'Hashed 7 files' },
                ],
                documents: [
                  {
                    id: 101,
                    original_filename: 'trial_balance_fy24_25.csv',
                    document_type: 'TRIAL_BALANCE',
                    file_size_bytes: 1529,
                    file_hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
                  },
                ],
                summary_metrics: {
                  total_records: 42,
                  exceptions_raised: 0,
                  tb_balanced: true,
                  workpapers_created: 8,
                },
                zip_package_hash: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
                started_at: '2026-10-11T10:00:00Z',
                completed_at: '2026-10-11T10:00:05Z',
                updated_at: '2026-10-11T10:00:05Z',
              }),
          });
        }
        if (url.includes('/api/ingestion/runs/')) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve([
                {
                  id: 1,
                  run_id: 'RUN-20261011-DEMO',
                  company_name: 'Vanguard Industrial Automations Pvt Ltd',
                  engagement_title: 'Statutory Audit FY 2024-25',
                  status: 'COMPLETED',
                  current_stage: 'COMPLETED',
                  progress_percent: 100,
                  documents: [{ id: 101 }],
                  summary_metrics: { total_records: 42, exceptions_raised: 0 },
                  started_at: '2026-10-11T10:00:00Z',
                },
              ]),
          });
        }
        if (url.includes('/api/reporting/reports/consolidated_report/')) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                sections: {
                  entity_profile: {
                    company_name: 'Vanguard Industrial Automations Pvt Ltd',
                    cin: 'U29100MH2020PTC345678',
                    pan: 'AABCV9876K',
                    gstin: '27AABCV9876K1Z8',
                  },
                },
              }),
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

  it('renders UploadPage with drag & drop file staging and ICAI compliance badge', () => {
    render(
      <BrowserRouter>
        <UploadPage />
      </BrowserRouter>
    );

    expect(screen.getByText('Upload Master Financial Year Audit Workbook')).toBeDefined();
    expect(screen.getByText('ICAI SA 230 Compliant Ingestion')).toBeDefined();
    expect(screen.getByText(/Drag & drop Client Financial Master Documents/i)).toBeDefined();
  });

  it('validates file staging, rejects unsupported formats, and accepts ZIP archives, Excel, or PDF files', () => {
    const { container } = render(
      <BrowserRouter>
        <UploadPage />
      </BrowserRouter>
    );

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toBeDefined();

    // 1. Attempt non-supported file (.txt)
    const txtFile = new File(['dummy content'], 'report.txt', { type: 'text/plain' });
    fireEvent.change(fileInput, { target: { files: [txtFile] } });
    expect(screen.getByText(/Unsupported file type '\.txt'/i)).toBeDefined();

    // 2. Select valid ZIP archive
    const zipFile = new File(['fake-zip-binary'], 'Client_FY2024_Docs.zip', { type: 'application/zip' });
    fireEvent.change(fileInput, { target: { files: [zipFile] } });
    expect(screen.getByText('Client_FY2024_Docs.zip')).toBeDefined();
    expect(screen.getByText(/Client Documents Archive \(ZIP\)/i)).toBeDefined();

    // 3. Select valid PDF financial statement
    const pdfFile = new File(['fake-pdf-content'], 'Bank_Statement_FY24.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput, { target: { files: [pdfFile] } });
    expect(screen.getByText('Bank_Statement_FY24.pdf')).toBeDefined();
    expect(screen.getByText(/PDF - Auto-Filtered/i)).toBeDefined();
  });

  it('renders ProcessingStatusPage with 14-stage progression and metrics', async () => {
    render(
      <BrowserRouter>
        <ProcessingStatusPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('14-Stage Processing Pipeline')).toBeDefined();
      expect(screen.getByText('Overall Status')).toBeDefined();
      expect(screen.getByText('Documents Ingested')).toBeDefined();
    });
  });

  it('renders HistoryPage with past runs table and filters', async () => {
    render(
      <BrowserRouter>
        <HistoryPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Audit Engagement History & Versions')).toBeDefined();
      expect(screen.getByText('RUN-20261011-DEMO')).toBeDefined();
      expect(screen.getByText('Vanguard Industrial Automations Pvt Ltd')).toBeDefined();
    });
  });

  it('renders FinalAuditFilePage with 14-section dossier and CA sign-off', async () => {
    render(
      <BrowserRouter>
        <FinalAuditFilePage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('14-Section Consolidated Audit Dossier')).toBeDefined();
      expect(screen.getByText('Download .ZIP Package')).toBeDefined();
      expect(screen.getByText('Independent Auditor\'s Report Certificate')).toBeDefined();
    });
  });
});
