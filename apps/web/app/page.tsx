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
        <h1 className="text-2xl font-semibold">Command Center</h1>
        <p className="text-navy/70">
          Signed in as <strong>{me.data?.full_name}</strong> ({me.data?.role}). From “Where is
          this invoice?” to “What does this cost mean?”
        </p>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="Total invoices" value={s?.total_invoices ?? "—"} href="/inbox" />
        <Kpi label="Needs review / matched" value={(s?.by_status?.["MATCHED"] ?? 0) + (s?.by_status?.["NEEDS_REVIEW"] ?? 0)} href="/inbox" />
        <Kpi label="Pending approval" value={s?.approval_pending ?? "—"} tone="text-blue-700" href="/approvals" />
        <Kpi label="Open exceptions" value={s?.open_exceptions ?? "—"} tone="text-amber-700" href="/exceptions" />
        <Kpi label="Blocking (duplicates etc.)" value={s?.blocking_exceptions ?? "—"} tone="text-red-700" href="/exceptions" />
        <Kpi label="Duplicate-risk invoices" value={s?.duplicate_risk ?? "—"} tone="text-red-700" />
        <Kpi label="Unbudgeted flags" value={s?.unbudgeted_flags ?? "—"} tone="text-amber-700" />
        <Kpi label="Open exposure" value={s ? `$${s.total_exposure.toLocaleString()}` : "—"} />
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
