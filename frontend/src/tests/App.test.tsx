import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import React from 'react';
import { App } from '../App';

describe('Captrix AI Frontend Application', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve([]),
        })
      )
    );
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('renders Captrix branding in sidebar', () => {
    render(<App />);
    const brandElements = screen.getAllByText('Captrix');
    expect(brandElements.length).toBeGreaterThan(0);
    expect(brandElements[0]).toBeDefined();
  }, 15000);

  it('renders primary navigation items in sidebar', () => {
    render(<App />);
    expect(screen.getAllByText('Dashboard').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Upload & Analyze').length).toBeGreaterThan(0);
    expect(screen.getAllByText('CA Auditor Suite').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Reconciliation').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Final Audit File').length).toBeGreaterThan(0);
  }, 15000);

  it('renders bottom user profile card', () => {
    render(<App />);
    const nameElements = screen.getAllByText(/Audit Partner|Firm/i);
    expect(nameElements.length).toBeGreaterThan(0);
    expect(nameElements[0]).toBeDefined();

    const roleElements = screen.getAllByText(/Statutory Auditor/i);
    expect(roleElements.length).toBeGreaterThan(0);
    expect(roleElements[0]).toBeDefined();
  });
});
