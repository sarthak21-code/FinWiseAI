"use client";

import React from "react";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function ShellLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-[#080D16] text-slate-100 antialiased selection:bg-emerald-500/30 selection:text-emerald-200">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col overflow-x-hidden">
        <TopBar />
        <main className="flex-1 p-4 md:p-6 lg:p-8 max-w-[1600px] w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
