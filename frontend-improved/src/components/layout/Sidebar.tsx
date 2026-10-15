"use client";

import React, { useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import Image from "next/image";
import {
  LayoutDashboard,
  Activity,
  Building2,
  Brain,
  Newspaper,
  BookOpen,
  Briefcase,
  BarChart3,
  Menu,
  X,
  ShieldAlert,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/technical", label: "Technical Analysis", icon: Activity },
  { href: "/fundamentals", label: "Fundamentals", icon: Building2 },
  { href: "/intelligence", label: "Agent Intelligence", icon: Brain },
  { href: "/news", label: "News & Filings (RAG)", icon: Newspaper },
  { href: "/portfolio", label: "Portfolio & Risk", icon: Briefcase },
  { href: "/evaluation", label: "System Evaluation", icon: BarChart3 },
  { href: "/methodology", label: "Data & Methodology", icon: BookOpen },
];

export function Sidebar() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [mobileOpen, setMobileOpen] = useState(false);

  const ticker = searchParams.get("ticker");
  const queryStr = ticker ? `?ticker=${encodeURIComponent(ticker)}` : "";

  return (
    <>
      {/* Mobile Menu Toggle Button */}
      <div className="fixed bottom-4 right-4 z-50 md:hidden">
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500 text-slate-950 shadow-lg shadow-emerald-500/20 focus:outline-none"
          aria-label="Toggle Navigation"
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Mobile Drawer Overlay */}
      {mobileOpen && (
        <div
          onClick={() => setMobileOpen(false)}
          className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm md:hidden"
        />
      )}

      {/* Persistent Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-800/80 bg-[#080D16] transition-transform duration-200 md:static md:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Brand / Logo */}
        <div className="flex h-16 shrink-0 items-center justify-center border-b border-slate-800/80 px-3">
          <Image
            src="/finwiseai-logo.png"
            alt="FinWiseAI — Smarter Insights. Better Investments."
            className="h-auto w-full max-w-[214px]"
            width={675}
            height={207}
          />
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 space-y-1.5 px-3 py-4">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            const fullHref = `${item.href}${queryStr}`;

            return (
              <a
                key={item.href}
                href={fullHref}
                onClick={() => setMobileOpen(false)}
                className={`flex items-center gap-3 rounded-lg px-3.5 py-2.5 text-xs font-semibold tracking-wide transition ${
                  isActive
                    ? "bg-emerald-500/10 text-emerald-300 border border-emerald-500/20"
                    : "text-slate-400 hover:bg-slate-900/80 hover:text-slate-200"
                }`}
              >
                <Icon
                  size={16}
                  className={isActive ? "text-emerald-400" : "text-slate-500"}
                />
                <span>{item.label}</span>
              </a>
            );
          })}
        </nav>

        {/* Bottom Disclaimers & Engine Info */}
        <div className="border-t border-slate-800/80 p-4">
          <div className="rounded-lg border border-slate-800/90 bg-slate-950/60 p-3 text-[11px] leading-relaxed text-slate-400">
            <div className="flex items-center gap-1.5 text-amber-400 font-semibold mb-1">
              <ShieldAlert size={13} />
              <span>Research Purpose Only</span>
            </div>
            <p className="text-slate-500 text-[10px]">
              FinWiseAI provides multi-agent evidence synthesis, not personalized financial advice or execution.
            </p>
          </div>
          <div className="mt-3 flex items-center justify-between text-[10px] font-mono text-slate-600">
            <span>Terminal v2.4</span>
            <span className="flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              Engine Online
            </span>
          </div>
        </div>
      </aside>
    </>
  );
}
