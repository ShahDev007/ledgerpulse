import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { PersonaSwitcher } from "@/components/PersonaSwitcher";

export const metadata: Metadata = {
  title: "LedgerPulse - Invoice Intelligence",
  description: "AI-native invoice tracking, cost governance, and portfolio intelligence.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="min-h-screen">
            <header className="bg-navy-900 text-white">
              <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
                <div className="flex items-center gap-6">
                  <span className="text-lg font-semibold tracking-tight">LedgerPulse</span>
                  <nav className="flex items-center gap-4 text-sm text-navy-50/80">
                    <a href="/" className="hover:text-white">Command Center</a>
                    <a href="/inbox" className="hover:text-white">Inbox</a>
                    <a href="/approvals" className="hover:text-white">Approvals</a>
                    <a href="/exceptions" className="hover:text-white">Exceptions</a>
                    <a href="/copilot" className="hover:text-white">Copilot</a>
                    <a href="/ai" className="hover:text-white">AI</a>
                  </nav>
                </div>
                <PersonaSwitcher />
              </div>
            </header>
            <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
