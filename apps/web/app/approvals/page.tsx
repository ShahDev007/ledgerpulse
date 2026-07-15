"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, getToken, decideApproval } from "@/lib/api";
import Link from "next/link";
import { useState } from "react";

interface QueueRow {
  step_id: string;
  invoice_id: string;
  tracking_id: string;
  vendor: string | null;
  total: number | null;
  currency: string;
  required_role: string;
  step_no: number;
  due_at: string | null;
}

export default function Approvals() {
  const qc = useQueryClient();
  const hasToken = typeof window !== "undefined" && !!getToken();
  const [msg, setMsg] = useState<string | null>(null);

  const q = useQuery({
    queryKey: ["approvals"],
    queryFn: () => api<QueueRow[]>("/v1/approvals"),
    enabled: hasToken,
    retry: false,
  });

  const decide = useMutation({
    mutationFn: ({ stepId, decision }: { stepId: string; decision: "APPROVED" | "REJECTED" }) =>
      decideApproval(stepId, decision, decision === "APPROVED" ? "Reviewed" : "Rejected on review"),
    onSuccess: (r) => {
      setMsg(`Invoice ${r.invoice_status}`);
      qc.invalidateQueries();
    },
    onError: (e: any) => setMsg(`Failed: ${e.message}`),
  });

  if (!hasToken) return <p className="text-navy/70">Select a persona to view your approval queue.</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Approval Queue</h1>
          <p className="text-navy/70">Decisions assigned to you, with the evidence that matters.</p>
        </div>
        {msg && <span className="text-sm text-teal">{msg}</span>}
      </div>

      <div className="space-y-3">
        {q.data?.map((r) => (
          <div key={r.step_id} className="flex items-center justify-between rounded-lg border border-navy/10 bg-white p-4 shadow-sm">
            <div>
              <Link href={`/invoices/${r.invoice_id}`} className="font-mono text-sm text-teal hover:underline">
                {r.tracking_id}
              </Link>
              <div className="text-sm text-navy/70">
                {r.vendor ?? "—"} · {r.total != null ? `${r.currency} ${r.total.toLocaleString()}` : "—"}
              </div>
              <div className="text-xs text-navy/40">
                As {r.required_role} · step {r.step_no}
                {r.due_at && <> · due {new Date(r.due_at).toLocaleDateString()}</>}
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => decide.mutate({ stepId: r.step_id, decision: "REJECTED" })}
                disabled={decide.isPending}
                className="rounded-md border border-red-300 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
              >
                Reject
              </button>
              <button
                onClick={() => decide.mutate({ stepId: r.step_id, decision: "APPROVED" })}
                disabled={decide.isPending}
                className="rounded-md bg-teal px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-light disabled:opacity-50"
              >
                Approve
              </button>
            </div>
          </div>
        ))}
        {q.data?.length === 0 && (
          <p className="rounded-lg border border-navy/10 bg-white p-8 text-center text-navy/40">
            Nothing awaiting your approval.
          </p>
        )}
      </div>
    </div>
  );
}
