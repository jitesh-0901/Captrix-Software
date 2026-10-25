import React from 'react';
import { ShieldCheck } from 'lucide-react';

interface HeaderProps {
  title: string;
  subtitle?: string;
  companyName?: string;
  financialYear?: string;
  actions?: React.ReactNode;
}

export const Header: React.FC<HeaderProps> = ({ title, subtitle, companyName, financialYear, actions }) => {
  return (
    <header className="bg-white border-b border-slate-200 px-6 sm:px-8 py-4 flex items-center justify-between sticky top-0 z-10">
      <div>
        <div className="flex items-center gap-2.5 flex-wrap">
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">{title}</h1>
          {companyName && (
            <span className="hidden md:inline-flex items-center text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
              {companyName} {financialYear ? `• ${financialYear}` : ''}
            </span>
          )}
        </div>
        {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-3">
        {actions}
        {/* Audit Compliance Pill */}
        <div className="flex items-center gap-1.5 bg-emerald-50 text-emerald-700 border border-emerald-200 px-2.5 py-1.5 rounded-xl text-xs font-medium">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
          <span className="hidden sm:inline">ICAI SA 320 / Ind AS Verified</span>
          <span className="sm:hidden">ICAI Verified</span>
        </div>
      </div>
    </header>
  );
};

export default Header;
