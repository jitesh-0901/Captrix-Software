import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  Menu,
  X,
  Home,
  Building2,
  Briefcase,
  CloudUpload,
  Activity,
  GitCompare,
  Scale,
  AlertTriangle,
  FileText,
  ShieldCheck,
  FileCheck2,
  History,
  UserCheck,
} from 'lucide-react';

const coreAuditorNav = [
  { name: 'Dashboard', path: '/', icon: Home },
  { name: 'Clients', path: '/clients', icon: Building2 },
  { name: 'Engagements', path: '/engagements', icon: Briefcase },
  { name: 'Upload & Analyze', path: '/upload', icon: CloudUpload, badge: 'Batch' },
  { name: 'Processing Status', path: '/processing', icon: Activity },
  { name: 'Reconciliation', path: '/reconciliation', icon: GitCompare },
  { name: 'CA Auditor Suite', path: '/auditor-suite', icon: Scale },
  { name: 'Findings & Exceptions', path: '/exceptions', icon: AlertTriangle },
  { name: 'Working Papers', path: '/workpapers', icon: FileText },
  { name: 'Review Queue', path: '/review-queue', icon: ShieldCheck, badge: 'SA 220' },
  { name: 'Final Audit File', path: '/final-audit-file', icon: FileCheck2 },
  { name: 'History', path: '/history', icon: History, badge: 'Archive' },
];

export const Sidebar: React.FC = () => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  return (
    <>
      {/* Mobile Sticky Top Header Bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 h-14 bg-[#0a0f1d] border-b border-slate-800 z-40 px-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <img
            src="/captrix-logo.png"
            alt="Captrix Logo"
            className="w-7 h-7 object-contain shrink-0"
          />
          <div className="flex items-baseline">
            <span className="text-white text-lg font-bold tracking-tight">Captrix</span>
          </div>
        </div>

        <button
          onClick={() => setIsMobileOpen(!isMobileOpen)}
          aria-label="Toggle Mobile Navigation"
          className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition cursor-pointer"
        >
          {isMobileOpen ? <X className="w-5 h-5 text-rose-400" /> : <Menu className="w-5 h-5 text-[#00e5ff]" />}
        </button>
      </div>

      {/* Mobile Backdrop Overlay */}
      {isMobileOpen && (
        <div
          onClick={() => setIsMobileOpen(false)}
          className="md:hidden fixed inset-0 bg-black/60 backdrop-blur-xs z-45 transition-opacity"
        />
      )}

      {/* Main Responsive Navigation Drawer / Sidebar */}
      <aside
        className={`fixed md:sticky top-0 left-0 h-screen overflow-y-auto transition-transform md:transition-all duration-200 z-50 md:z-30 select-none shrink-0 border-r border-slate-800/80 bg-[#0a0f1d] flex flex-col justify-between ${
          isMobileOpen ? 'translate-x-0 w-64 shadow-2xl' : '-translate-x-full md:translate-x-0'
        } ${isCollapsed ? 'md:w-20' : 'md:w-64'}`}
      >
        <div>
          {/* Brand Header & Desktop Hamburger Toggle */}
          <div className={`py-5 flex items-center justify-between ${isCollapsed ? 'md:px-3 md:flex-col md:gap-3 px-6' : 'px-6'}`}>
            <div className="flex items-center gap-3 min-w-0">
              <img
                src="/captrix-logo.png"
                alt="Captrix Logo"
                className="w-8 h-8 object-contain shrink-0"
              />
              {(!isCollapsed || isMobileOpen) && (
                <div className="flex items-baseline truncate">
                  <span className="text-white text-xl font-bold tracking-tight">Captrix</span>
                </div>
              )}
            </div>

            {/* Desktop Hamburger / Collapse Toggle */}
            <button
              onClick={() => setIsCollapsed(!isCollapsed)}
              aria-label="Toggle Navigation Sidebar"
              title={isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
              className="hidden md:flex w-8 h-8 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white items-center justify-center transition cursor-pointer shrink-0 border border-slate-700/60"
            >
              {isCollapsed ? <Menu className="w-4 h-4 text-[#00e5ff]" /> : <X className="w-4 h-4 text-slate-400" />}
            </button>

            {/* Mobile Close Button inside Drawer */}
            <button
              onClick={() => setIsMobileOpen(false)}
              aria-label="Close Navigation"
              className="md:hidden p-1.5 rounded-lg bg-slate-800 text-slate-400 hover:text-white"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className={`${isCollapsed ? 'md:px-2 px-5' : 'px-5'} pb-3`}>
            <div className="h-px bg-slate-800/70 w-full" />
          </div>

          {/* PRIMARY AUDITOR WORKFLOW */}
          {(!isCollapsed || isMobileOpen) && (
            <div className="px-5 py-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Auditor Automation Suite
              </span>
            </div>
          )}
          <nav className={`${isCollapsed ? 'md:px-2 md:space-y-1.5 px-3 space-y-1' : 'px-3 space-y-1'}`}>
            {coreAuditorNav.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  onClick={() => setIsMobileOpen(false)}
                  title={isCollapsed ? item.name : undefined}
                  className={({ isActive }) =>
                    `flex items-center ${
                      isCollapsed ? 'md:justify-center md:p-2.5 justify-between px-3.5 py-2' : 'justify-between px-3.5 py-2'
                    } rounded-xl text-xs font-medium transition-colors duration-150 ${
                      isActive
                        ? 'bg-[#1d63ed] text-white shadow-md shadow-blue-900/30 font-semibold'
                        : 'text-slate-300 hover:text-white hover:bg-slate-800/50'
                    }`
                  }
                >
                  <div className={`flex items-center ${isCollapsed ? 'md:justify-center gap-2.5' : 'gap-2.5'} min-w-0`}>
                    <Icon className="w-4 h-4 shrink-0 text-[#00e5ff]" />
                    {(!isCollapsed || isMobileOpen) && <span className="truncate">{item.name}</span>}
                  </div>
                  {(!isCollapsed || isMobileOpen) && item.badge && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-950/80 text-blue-300 border border-blue-800/60 font-semibold shrink-0">
                      {item.badge}
                    </span>
                  )}
                </NavLink>
              );
            })}
          </nav>
        </div>

      {/* Authorized Chartered Accountant Profile Card */}
      <div
        className={`${
          isCollapsed ? 'p-2 m-2 flex-col gap-2 text-center' : 'p-3 m-3'
        } bg-[#0d162f] border border-slate-800/90 rounded-2xl flex items-center justify-between`}
      >
        <div className={`flex items-center ${isCollapsed ? 'justify-center' : 'gap-2.5'} min-w-0`}>
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-purple-600 text-white font-bold flex items-center justify-center text-xs shadow-inner shrink-0">
            CA
          </div>
          {!isCollapsed && (
            <div className="min-w-0 flex-1">
              <div className="text-white text-xs font-semibold truncate">
                {localStorage.getItem('captrix_ca_partner_name') || 'Audit Partner / Firm'}
              </div>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
                <span className="text-[10px] text-slate-400 truncate">
                  {localStorage.getItem('captrix_ca_firm_title') || 'Statutory Auditor • ICAI Registered'}
                </span>
              </div>
            </div>
          )}
        </div>
        {!isCollapsed && (
          <div className="p-1 rounded-lg text-slate-500">
            <UserCheck className="w-4 h-4 text-emerald-400" />
          </div>
        )}
      </div>
    </aside>
    </>
  );
};

export default Sidebar;
