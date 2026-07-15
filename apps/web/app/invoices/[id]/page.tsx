"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, API_URL, getToken, extractInvoice, patchField, submitInvoice, investigateInvoice, exportInvoice, simulatePayment } from "@/lib/api";
import { useEffect, useState, use } from "react";

interface Detail {
  id: string;
  tracking_id: string;
  status: string;
  source_type: string;
  lock_version: number;
  vendor: string | null;
  invoice_number: string | null;
  invoice_date: string | null;
  due_date: string | null;
  currency: string;
  subtotal: number | null;
  tax: number | null;
  total: number | null;
  document_hash: string | null;
  risk_score: number;
  risk_flags: string[];
  is_credit_memo: boolean;
  resolved_vendor: string | null;
  resolved_property: string | null;
  extraction_confidence: number | null;
  field_confidence: Record<string, number>;
  files: { id: string; content_type: string; sha256: string; is_original: boolean }[];
  lines: { line_no: number; description: string | null; quantity: number | null; unit_price: number | null; amount: number | null }[];
  model_runs: { capability: string; provider: string; model: string | null; input_tokens: number | null; output_tokens: number | null; latency_ms: number | null; cost_usd: number | null; status: string }[];
  exceptions: { id: string; category: string; issue_type: string; severity: string; summary: string | null; owner_role: string | null; status: string; evidence: any }[];
  match_results: { kind: string; outcome: string; score: number | null; reasons: any }[];
  timeline: { occurred_at: string; actor_type: string; action: string; reason: string | null; event_hash: string }[];
}

const SEV_STYLE: Record<string, string> = {
  BLOCKING: "border-red-300 bg-red-50 text-red-800",
  REVIEW: "border-amber-300 bg-amber-50 text-amber-800",
  INFO: "border-slate-300 bg-slate-50 text-slate-700",
};

const ACTOR_COLOR: Record<string, string> = {
  USER: "bg-blue-500", RULE: "bg-amber-500", MODEL: "bg-teal", INTEGRATION: "bg-purple-500", SYSTEM: "bg-slate-500",
};

function Confidence({ v }: { v?: number }) {
  if (v == null) return null;
  const pct = Math.round(v * 100);
  const cls = v >= 0.95 ? "bg-teal/10 text-teal" : v >= 0.8 ? "bg-amber-100 text-amber-800" : "bg-red-100 text-red-800";
  return <span className={`ml-2 rounded px-1.5 py-0.5 text-[10px] font-medium ${cls}`}>{pct}%</span>;
}

function useDocumentBlob(invoiceId: string) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let obj: string | null = null;
    let cancelled = false;
    (async () => {
      const res = await fetch(`${API_URL}/v1/invoices/${invoiceId}/file`, {
        headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : {},
      });
      if (!res.ok || cancelled) return;
      obj = URL.createObjectURL(await res.blob());
      setUrl(obj);
    })();
    return () => { cancelled = true; if (obj) URL.revokeObjectURL(obj); };
  }, [invoiceId]);
  return url;
}

const EDITABLE: { key: keyof Detail; label: string; provKey: string }[] = [
  { key: "vendor", label: "Vendor", provKey: "vendor_name" },
  { key: "invoice_number", label: "Invoice #", provKey: "invoice_number" },
  { key: "invoice_date", label: "Invoice date", provKey: "invoice_date" },
  { key: "due_date", label: "Due date", provKey: "due_date" },
  { key: "subtotal", label: "Subtotal", provKey: "subtotal" },
  { key: "tax", label: "Tax", provKey: "tax" },
  { key: "total", label: "Total", provKey: "total" },
];
// map display key -> backend field name
const FIELD_NAME: Record<string, string> = { vendor: "raw_vendor_name" };

export default function Workbench({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const qc = useQueryClient();
  const hasToken = typeof window !== "undefined" && !!getToken();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});
  const [note, setNote] = useState<string | null>(null);

  const q = useQuery({
    queryKey: ["invoice", id],
    queryFn: () => api<Detail>(`/v1/invoices/${id}`),
    enabled: hasToken,
    retry: false,
  });
  const docUrl = useDocumentBlob(id);

  const extract = useMutation({
    mutationFn: () => extractInvoice(id),
    onSuccess: () => { setNote("Extraction complete"); qc.invalidateQueries({ queryKey: ["invoice", id] }); },
    onError: (e: any) => setNote(`Extraction failed: ${e.message}`),
  });

  const submit = useMutation({
    mutationFn: () => submitInvoice(id),
    onSuccess: (r: any) => { setNote(`Submitted (${r.policy}) → ${r.steps.map((s: any) => s.role).join(" → ")}`); qc.invalidateQueries({ queryKey: ["invoice", id] }); },
    onError: (e: any) => setNote(`Submit blocked: ${e.message}`),
  });

  const [investigation, setInvestigation] = useState<any>(null);
  const investigate = useMutation({
    mutationFn: () => investigateInvoice(id),
    onSuccess: (r: any) => { setInvestigation(r); setNote("Investigation complete"); qc.invalidateQueries({ queryKey: ["invoice", id] }); },
    onError: (e: any) => setNote(`Investigation failed: ${e.message}`),
  });

  const exp = useMutation({
    mutationFn: () => exportInvoice(id),
    onSuccess: (r: any) => { setNote(r.ok ? `Exported → ${r.external_id}` : `Export failed (${r.retryable ? "retryable" : "permanent"})`); qc.invalidateQueries({ queryKey: ["invoice", id] }); },
    onError: (e: any) => setNote(`Export failed: ${e.message}`),
  });
  const pay = useMutation({
    mutationFn: (amount: number) => simulatePayment(id, amount),
    onSuccess: (r: any) => { setNote(r.reconciled ? "Reconciled — fully paid" : "Payment mismatch flagged"); qc.invalidateQueries({ queryKey: ["invoice", id] }); },
    onError: (e: any) => setNote(`Payment failed: ${e.message}`),
  });

  const save = useMutation({
    mutationFn: async () => {
      const d = q.data!;
      let lock = d.lock_version;
      for (const f of EDITABLE) {
        const backend = FIELD_NAME[f.key as string] ?? (f.key as string);
        const current = d[f.key];
        const next = form[f.key as string];
        if (next == null) continue;
        const cur = current == null ? "" : String(current);
        if (next === cur) continue;
        const r = await patchField(id, backend, next === "" ? null : next, lock);
        lock = r.lock_version;
      }
    },
    onSuccess: () => { setEditing(false); setNote("Saved corrections"); qc.invalidateQueries({ queryKey: ["invoice", id] }); },
    onError: (e: any) => setNote(`Save failed: ${e.message}`),
  });

  if (!hasToken) return <p className="text-navy/70">Select a persona to view this invoice.</p>;
  if (q.isLoading) return <p className="text-navy/50">Loading…</p>;
  if (q.error) return <p className="text-red-600">Failed to load invoice.</p>;
  const d = q.data!;
  const original = d.files.find((f) => f.is_original);

  const startEdit = () => {
    setForm({
      vendor: d.vendor ?? "", invoice_number: d.invoice_number ?? "",
      invoice_date: d.invoice_date ?? "", due_date: d.due_date ?? "",
      subtotal: d.subtotal?.toString() ?? "", tax: d.tax?.toString() ?? "", total: d.total?.toString() ?? "",
    });
    setEditing(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-mono text-xl font-semibold">{d.tracking_id}</h1>
          <p className="text-navy/60">{d.source_type} · {d.status}
            {d.extraction_confidence != null && <> · extraction {Math.round(d.extraction_confidence * 100)}%</>}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {note && <span className="text-sm text-teal">{note}</span>}
          <button onClick={() => extract.mutate()} disabled={extract.isPending}
            className="rounded-md border border-teal px-3 py-1.5 text-sm font-medium text-teal hover:bg-teal/5 disabled:opacity-50">
            {extract.isPending ? "Extracting…" : d.invoice_number ? "Re-extract" : "Extract with Claude"}
          </button>
          {["MATCHED", "EXCEPTION", "NEEDS_REVIEW"].includes(d.status) && (
            <button onClick={() => submit.mutate()} disabled={submit.isPending}
              className="rounded-md bg-navy px-3 py-1.5 text-sm font-medium text-white hover:bg-navy-700 disabled:opacity-50">
              {submit.isPending ? "Submitting…" : "Submit for approval"}
            </button>
          )}
          {d.status === "APPROVED" && (
            <button onClick={() => exp.mutate()} disabled={exp.isPending}
              className="rounded-md bg-navy px-3 py-1.5 text-sm font-medium text-white hover:bg-navy-700 disabled:opacity-50">
              {exp.isPending ? "Exporting…" : "Export to ERP"}
            </button>
          )}
          {d.status === "EXPORTED" && d.total != null && (
            <>
              <button onClick={() => pay.mutate(d.total!)} disabled={pay.isPending}
                className="rounded-md bg-teal px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-light disabled:opacity-50">
                Record full payment
              </button>
              <button onClick={() => pay.mutate(Math.round(d.total! * 0.97 * 100) / 100)} disabled={pay.isPending}
                className="rounded-md border border-amber-400 px-3 py-1.5 text-sm font-medium text-amber-700 hover:bg-amber-50 disabled:opacity-50">
                Record short payment
              </button>
            </>
          )}
          <a href="/inbox" className="text-sm text-teal hover:underline">← Inbox</a>
        </div>
      </div>

      {/* Issue banner + risk flags (exception cockpit preview) */}
      {(d.exceptions.length > 0 || d.risk_flags.length > 0) && (
        <div className="space-y-2">
          {d.exceptions.some((e) => e.status === "OPEN") && (
            <div className="flex justify-end">
              <button onClick={() => investigate.mutate()} disabled={investigate.isPending}
                className="rounded-md bg-teal px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-light disabled:opacity-50">
                {investigate.isPending ? "Investigating with Claude…" : "Investigate with AI"}
              </button>
            </div>
          )}
          {d.risk_flags.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="text-navy/50">Risk {Math.round(d.risk_score * 100)}% ·</span>
              {d.risk_flags.map((f) => (
                <span key={f} className="rounded bg-red-100 px-2 py-0.5 font-medium text-red-700">{f}</span>
              ))}
            </div>
          )}
          {d.exceptions.map((e) => (
            <div key={e.id} className={`rounded-lg border p-3 ${SEV_STYLE[e.severity] ?? SEV_STYLE.INFO}`}>
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold">{e.issue_type} · {e.severity}</span>
                <span className="text-xs opacity-70">{e.category} · owner {e.owner_role}</span>
              </div>
              {e.summary && <p className="mt-1 text-sm">{e.summary}</p>}
              {e.evidence && (() => {
                const { investigation, ...rest } = e.evidence; // investigation shown in its own panel
                return Object.keys(rest).length > 0 ? (
                  <pre className="mt-2 overflow-x-auto rounded bg-white/60 p-2 text-[11px] leading-tight">
                    {JSON.stringify(rest, null, 2)}
                  </pre>
                ) : null;
              })()}
            </div>
          ))}
        </div>
      )}

      {/* AI investigation result (read-only, cited) */}
      {(() => {
        const r = investigation?.result ?? d.exceptions.find((e) => e.evidence?.investigation)?.evidence?.investigation;
        if (!r) return null;
        return (
          <div className="rounded-lg border border-teal/30 bg-teal/5 p-4">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="font-semibold text-teal">AI Investigation — {r.issue_type} ({Math.round((r.confidence ?? 0) * 100)}% confidence)</h2>
              <span className="text-xs text-navy/50">
                read-only agent{investigation ? ` · ${investigation.model} · ${investigation.tokens?.in}→${investigation.tokens?.out} tok · ${(investigation.latency_ms/1000).toFixed(1)}s` : ""}
              </span>
            </div>
            {investigation?.tool_calls && (
              <div className="mb-2 flex flex-wrap gap-1 text-[11px]">
                {investigation.tool_calls.map((t: any, i: number) => (
                  <span key={i} className={`rounded px-1.5 py-0.5 ${t.allowed ? "bg-white text-navy/60" : "bg-red-100 text-red-700"}`}>{t.tool}</span>
                ))}
              </div>
            )}
            <p className="text-sm text-navy/80">{r.summary}</p>
            {r.confirmed_facts?.length > 0 && (
              <div className="mt-3">
                <div className="text-xs font-semibold text-navy/60">Confirmed facts (with evidence)</div>
                <ul className="mt-1 space-y-1 text-sm">
                  {r.confirmed_facts.map((f: string, i: number) => <li key={i} className="text-navy/80">• {f}</li>)}
                </ul>
              </div>
            )}
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <div>
                <div className="text-xs font-semibold text-navy/60">Recommended action</div>
                <p className="text-sm text-navy/80">{r.recommended_action}</p>
              </div>
              {r.requested_information?.length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-navy/60">Requested information</div>
                  <ul className="text-sm text-navy/80">{r.requested_information.map((x: string, i: number) => <li key={i}>• {x}</li>)}</ul>
                </div>
              )}
            </div>
            {r.uncertainties?.length > 0 && (
              <p className="mt-3 text-xs text-navy/50">Uncertainties: {r.uncertainties.join("; ")}</p>
            )}
            {r.evidence_ids?.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {r.evidence_ids.map((e: string) => <span key={e} className="rounded bg-navy/5 px-1.5 py-0.5 font-mono text-[10px] text-navy/50">{e}</span>)}
              </div>
            )}
          </div>
        );
      })()}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Document */}
        <div className="rounded-lg border border-navy/10 bg-white p-3 shadow-sm">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="font-semibold">Original document</h2>
            <span className="text-xs text-navy/40">immutable</span>
          </div>
          <div className="flex h-[560px] items-center justify-center overflow-auto rounded bg-navy-50">
            {!docUrl ? <span className="text-navy/40">Loading…</span> :
              original?.content_type === "application/pdf"
                ? <iframe src={docUrl} className="h-full w-full" title="doc" />
                // eslint-disable-next-line @next/next/no-img-element
                : <img src={docUrl} alt="invoice" className="max-h-full max-w-full object-contain" />}
          </div>
          {original && <p className="mt-2 break-all font-mono text-[11px] text-navy/40">sha256: {original.sha256}</p>}
        </div>

        {/* Fields + model + timeline */}
        <div className="space-y-6">
          <div className="rounded-lg border border-navy/10 bg-white p-4 shadow-sm">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-semibold">Extracted fields
                <span className="ml-2 text-xs font-normal text-navy/40">recommendation — verify before approval</span>
              </h2>
              {!editing ? (
                <button onClick={startEdit} className="text-sm text-teal hover:underline">Edit</button>
              ) : (
                <div className="flex gap-2">
                  <button onClick={() => setEditing(false)} className="text-sm text-navy/50 hover:underline">Cancel</button>
                  <button onClick={() => save.mutate()} disabled={save.isPending}
                    className="rounded bg-teal px-3 py-1 text-sm text-white hover:bg-teal-light disabled:opacity-50">
                    {save.isPending ? "Saving…" : "Save"}
                  </button>
                </div>
              )}
            </div>
            <dl className="grid grid-cols-[auto,1fr] items-center gap-x-4 gap-y-2 text-sm">
              {EDITABLE.map((f) => (
                <FieldRow
                  key={f.key as string}
                  label={f.label}
                  conf={d.field_confidence[f.provKey]}
                  editing={editing}
                  value={editing ? form[f.key as string] ?? "" : (d[f.key] == null ? null : String(d[f.key]))}
                  onChange={(v) => setForm((s) => ({ ...s, [f.key as string]: v }))}
                />
              ))}
            </dl>
          </div>

          {d.model_runs.length > 0 && (
            <div className="rounded-lg border border-navy/10 bg-white p-4 shadow-sm">
              <h2 className="mb-2 font-semibold">Model trace</h2>
              {d.model_runs.map((r, i) => (
                <div key={i} className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-navy/60">
                  <span className="font-medium text-navy">{r.capability}</span>
                  <span>{r.provider}/{r.model}</span>
                  <span>{r.input_tokens}→{r.output_tokens} tok</span>
                  <span>{r.latency_ms} ms</span>
                  {r.cost_usd != null && <span>${r.cost_usd.toFixed(4)}</span>}
                  <span className={r.status === "OK" ? "text-teal" : "text-red-600"}>{r.status}</span>
                </div>
              ))}
            </div>
          )}

          <div className="rounded-lg border border-navy/10 bg-white p-4 shadow-sm">
            <h2 className="mb-3 font-semibold">Audit timeline</h2>
            <ol className="space-y-3">
              {d.timeline.map((e, i) => (
                <li key={i} className="flex gap-3">
                  <span className={`mt-1 h-2.5 w-2.5 flex-shrink-0 rounded-full ${ACTOR_COLOR[e.actor_type] ?? "bg-slate-400"}`} />
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{e.action}</div>
                    <div className="text-xs text-navy/50">{e.actor_type} · {new Date(e.occurred_at).toLocaleString()}</div>
                    {e.reason && <div className="text-xs text-navy/60">{e.reason}</div>}
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>
    </div>
  );
}

function FieldRow({ label, conf, editing, value, onChange }: {
  label: string; conf?: number; editing: boolean; value: string | null; onChange: (v: string) => void;
}) {
  const low = conf != null && conf < 0.8;
  return (
    <>
      <dt className="text-navy/50">{label}<Confidence v={conf} /></dt>
      <dd className="text-right">
        {editing ? (
          <input value={value ?? ""} onChange={(e) => onChange(e.target.value)}
            className={`w-full rounded border px-2 py-1 text-right text-sm ${low ? "border-amber-400" : "border-navy/15"}`} />
        ) : (
          <span className={`font-medium ${low ? "text-amber-700" : ""}`}>{value ?? <span className="text-navy/30">—</span>}</span>
        )}
      </dd>
    </>
  );
}
