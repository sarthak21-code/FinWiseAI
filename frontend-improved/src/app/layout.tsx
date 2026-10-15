import type { Metadata } from "next";
import "./globals.css";
import { StockDataProvider } from "@/lib/stock-context";
import { ShellLayout } from "@/components/layout/ShellLayout";

export const metadata: Metadata = {
  title: "FinWiseAI — Smarter Insights. Better Investments.",
  description:
    "FinWiseAI brings transparent financial analysis, agent disagreement, and investor risk context together in one research workspace.",
  applicationName: "FinWiseAI",
  icons: { icon: "/icon.svg", shortcut: "/icon.svg" },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#080D16] text-slate-100 min-h-screen">
        <StockDataProvider>
          <ShellLayout>{children}</ShellLayout>
        </StockDataProvider>
      </body>
    </html>
  );
}
