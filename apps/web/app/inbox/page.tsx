"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, uploadInvoice, getToken } from "@/lib/api";
import { useRef, useState } from "react";
import Link from "next/link";

interface InvoiceRow {
  id: string;
  tracking_id: string;
  status: string;
  source_type: string;
  vendor: string | null;
  invoice_number: string | null;
  total: number | null;
  currency: string;
  risk_score: number;
  created_at: string;
}

const STATUS_STYLES: Record<string, string> = {
  RECEIVED: "bg-slate-100 text-slate-700",
  NEEDS_REVIEW: "bg-amber-100 text-amber-800",
  EXCEPTION: "bg-red-100 text-red-800",
  APPROVAL_PENDING: "bg-blue-100 text-blue-800",
  APPROVED: "bg-teal/10 text-teal",
  EXPORTED: "bg-emerald-100 text-emerald-800",
  PAID: "bg-emerald-100 text-emerald-800",
  RECONCILED: "bg-emerald-100 text-emerald-800",
};

export default function Inbox() {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const hasToken = typeof window !== "undefined" && !!getToken();

  const invoices = useQuery({
    queryKey: ["invoices"],
    queryFn: () => api<InvoiceRow[]>("/v1/invoices"),
    enabled: hasToken,
    retry: false,
  });

  const upload = useMutation({
    mutationFn: (file: File) => uploadInvoice(file),
    onSuccess: (r) => {
      setMsg(`Received ${r.tracking_id}${r.exact_duplicate_of ? " (exact duplicate detected)" : ""}`);
      qc.invalidateQueries({ queryKey: ["invoices"] });
    },
    onError: (e: any) => setMsg(`Upload failed: ${e.message}`),
  });

  if (!hasToken) {
    return <p className="text-navy/70">Select a persona (top-right) to view the invoice inbox.</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Invoice Inbox</h1>
          <p className="text-navy/70">Every invoice is an operational event with an audit trail.</p>
        </div>
        <div className="flex items-center gap-3">
          {msg && <span className="text-sm text-teal">{msg}</span>}
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf,image/*"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) upload.mutate(f);
              e.currentTarget.value = "";
            }}
          />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={upload.isPending}
            className="rounded-md bg-teal px-4 py-2 text-sm font-medium text-white hover:bg-teal-light disabled:opacity-50"
          >
            {upload.isPending ? "Uploading…" : "Upload invoice"}
          </button>
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-navy/10 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-navy-50 text-left text-navy/60">
            <tr>
              <th className="px-4 py-2 font-medium">Tracking</th>
              <th className="px-4 py-2 font-medium">Vendor</th>
              <th className="px-4 py-2 font-medium">Invoice #</th>
              <th className="px-4 py-2 font-medium">Total</th>
              <th className="px-4 py-2 font-medium">Source</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Received</th>
            </tr>
          </thead>
          <tbody>
            {invoices.data?.map((i) => (
              <tr key={i.id} className="border-t border-navy/5 hover:bg-navy-50/50">
                <td className="px-4 py-2 font-mono text-xs">
                  <Link href={`/invoices/${i.id}`} className="text-teal hover:underline">
                    {i.tracking_id}
                  </Link>
                </td>
                <td className="px-4 py-2">{i.vendor ?? <span className="text-navy/30">—</span>}</td>
                <td className="px-4 py-2">{i.invoice_number ?? <span className="text-navy/30">—</span>}</td>
                <td className="px-4 py-2">
                  {i.total != null ? `${i.currency} ${i.total.toFixed(2)}` : <span className="text-navy/30">—</span>}
                </td>
                <td className="px-4 py-2 text-navy/60">{i.source_type}</td>
                <td className="px-4 py-2">
                  <span className={`rounded px-2 py-0.5 text-xs ${STATUS_STYLES[i.status] ?? "bg-slate-100 text-slate-700"}`}>
                    {i.status}
                  </span>
                </td>
                <td className="px-4 py-2 text-navy/50">{new Date(i.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {invoices.data?.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-navy/40">
                  No invoices yet — upload one to begin.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
