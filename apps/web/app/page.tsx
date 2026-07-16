"use client";

import { useQuery } from "@tanstack/react-query";
import { api, getToken } from "@/lib/api";
import Link from "next/link";

interface Me { full_name: string; role: string; capabilities: string[] }
interface Stats {
  total_invoices: number;
  by_status: Record<string, number>;
  open_exceptions: number;
  blocking_exceptions: number;
  approval_pending: number;
  duplicate_risk: number;
  total_exposure: number;
  unbudgeted_flags: number;
}

function Kpi({ label, value, tone, href }: { label: string; value: string | number; tone?: string; href?: string }) {
  const body = (
    <div className="rounded-lg border border-navy/10 bg-white p-4 shadow-sm transition hover:shadow">
      <div className="text-sm text-navy/60">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${tone ?? "text-navy"}`}>{value}</div>
    </div>
  );
  return href ? <Link href={href}>{body}</Link> : body;
}

export default function CommandCenter() {
  const hasToken = typeof window !== "undefined" && !!getToken();
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/v1/me"), enabled: hasToken, retry: false });
  const stats = useQuery({ queryKey: ["stats"], queryFn: () => api<Stats>("/v1/stats"), enabled: hasToken, retry: false });

  if (!hasToken) {
    return (
      <div className="rounded-lg border border-navy/10 bg-white p-8 text-center shadow-sm">
        <h1 className="text-xl font-semibold">Welcome to LedgerPulse</h1>
        <p className="mt-2 text-navy/70">Select a persona in the top-right to sign in.</p>
      </div>
    );
  }

  const s = stats.data;
  return (
    <div className="space-y-6">
      <section>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">Command Center</h1>
          {/* Fancy hover explainer for non-technical stakeholders */}
          <div className="group relative">
            <button
              type="button"
              className="inline-flex items-center gap-1.5 rounded-full border border-teal/40 bg-teal/5 px-3 py-1 text-xs font-semibold text-teal transition hover:bg-teal hover:text-white"
            >
              <span aria-hidden>💡</span> What is this?
            </button>
            <div className="invisible absolute left-0 top-full z-30 mt-2 w-[22rem] translate-y-1 opacity-0 transition-all duration-150 group-hover:visible group-hover:translate-y-0 group-hover:opacity-100 sm:w-[26rem]">
              <div className="overflow-hidden rounded-2xl border border-navy/10 bg-white shadow-xl">
                <div className="bg-gradient-to-br from-navy-900 via-navy to-teal p-4 text-white">
                  <p className="text-[11px] font-medium uppercase tracking-widest text-teal-light">
                    LedgerPulse in plain English
                  </p>
                  <p className="mt-1 text-sm font-semibold leading-snug">
                    A smart assistant that reads and checks the bills for a company that owns lots
                    of buildings.
                  </p>
                </div>
                <ul className="space-y-2 p-4 text-sm text-navy/80">
                  <li><span aria-hidden>📄</span> <strong>Reads each bill</strong> automatically, using real AI on the real document.</li>
                  <li><span aria-hidden>🕵️</span> <strong>Catches mistakes</strong> and double-charges before anyone pays twice.</li>
                  <li><span aria-hidden>🧠</span> <strong>Explains itself</strong> with evidence when something looks wrong.</li>
                  <li><span aria-hidden>👤</span> <strong>Shows the right bills</strong> to the right people.</li>
                </ul>
                <div className="border-t border-navy/10 bg-navy-50 px-4 py-2.5 text-xs text-navy/70">
                  <span aria-hidden>🔒</span> The AI only advises. A human always approves or pays.
                </div>
              </div>
            </div>
          </div>
        </div>
        <p className="mt-1 text-navy/70">
          Signed in as <strong>{me.data?.full_name}</strong> ({me.data?.role}). From “Where is
          this invoice?” to “What does this cost mean?”
        </p>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="Total invoices" value={s?.total_invoices ?? "-"} href="/inbox" />
        <Kpi label="Needs review / matched" value={(s?.by_status?.["MATCHED"] ?? 0) + (s?.by_status?.["NEEDS_REVIEW"] ?? 0)} href="/inbox" />
        <Kpi label="Pending approval" value={s?.approval_pending ?? "-"} tone="text-blue-700" href="/approvals" />
        <Kpi label="Open exceptions" value={s?.open_exceptions ?? "-"} tone="text-amber-700" href="/exceptions" />
        <Kpi label="Blocking (duplicates etc.)" value={s?.blocking_exceptions ?? "-"} tone="text-red-700" href="/exceptions" />
        <Kpi label="Duplicate-risk invoices" value={s?.duplicate_risk ?? "-"} tone="text-red-700" />
        <Kpi label="Unbudgeted flags" value={s?.unbudgeted_flags ?? "-"} tone="text-amber-700" />
        <Kpi label="Open exposure" value={s ? `$${s.total_exposure.toLocaleString()}` : "-"} />
      </section>

      <section className="rounded-lg border border-navy/10 bg-white p-4 shadow-sm">
        <h2 className="mb-3 font-semibold">Lifecycle</h2>
        <div className="flex flex-wrap gap-2 text-xs">
          {s && Object.entries(s.by_status).map(([k, v]) => (
            <span key={k} className="rounded bg-navy-50 px-2 py-1 text-navy/70">
              {k}: <strong>{v}</strong>
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}
