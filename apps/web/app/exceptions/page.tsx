"use client";

import { useQuery } from "@tanstack/react-query";
import { api, getToken } from "@/lib/api";
import Link from "next/link";

interface ExceptionRow {
  id: string;
  invoice_id: string;
  tracking_id: string;
  category: string;
  issue_type: string;
  severity: string;
  summary: string | null;
  owner_role: string | null;
  status: string;
  due_at: string | null;
}

const SEV: Record<string, string> = {
  BLOCKING: "bg-red-100 text-red-800",
  REVIEW: "bg-amber-100 text-amber-800",
  INFO: "bg-slate-100 text-slate-700",
};

export default function Exceptions() {
  const hasToken = typeof window !== "undefined" && !!getToken();
  const q = useQuery({
    queryKey: ["exceptions"],
    queryFn: () => api<ExceptionRow[]>("/v1/exceptions"),
    enabled: hasToken,
    retry: false,
  });

  if (!hasToken) return <p className="text-navy/70">Select a persona to view exceptions.</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Exception Cockpit</h1>
        <p className="text-navy/70">Open exceptions across the portfolio, most recent first.</p>
      </div>
      <div className="overflow-hidden rounded-lg border border-navy/10 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-navy-50 text-left text-navy/60">
            <tr>
              <th className="px-4 py-2 font-medium">Invoice</th>
              <th className="px-4 py-2 font-medium">Issue</th>
              <th className="px-4 py-2 font-medium">Severity</th>
              <th className="px-4 py-2 font-medium">Category</th>
              <th className="px-4 py-2 font-medium">Owner</th>
              <th className="px-4 py-2 font-medium">Summary</th>
            </tr>
          </thead>
          <tbody>
            {q.data?.map((e) => (
              <tr key={e.id} className="border-t border-navy/5 hover:bg-navy-50/50">
                <td className="px-4 py-2 font-mono text-xs">
                  <Link href={`/invoices/${e.invoice_id}`} className="text-teal hover:underline">{e.tracking_id}</Link>
                </td>
                <td className="px-4 py-2 font-medium">{e.issue_type}</td>
                <td className="px-4 py-2">
                  <span className={`rounded px-2 py-0.5 text-xs ${SEV[e.severity] ?? SEV.INFO}`}>{e.severity}</span>
                </td>
                <td className="px-4 py-2 text-navy/60">{e.category}</td>
                <td className="px-4 py-2 text-navy/60">{e.owner_role}</td>
                <td className="px-4 py-2 text-navy/70">{e.summary}</td>
              </tr>
            ))}
            {q.data?.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-navy/40">No open exceptions.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
