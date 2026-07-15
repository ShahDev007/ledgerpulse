"use client";

import { useMutation } from "@tanstack/react-query";
import { copilotQuery, getToken } from "@/lib/api";
import { useState } from "react";
import Link from "next/link";

const SUGGESTIONS = [
  "Which invoices are possible duplicates or blocked, and why?",
  "How much do we owe Summit General Contractors, and is any of it unbudgeted?",
  "Which approved invoices are due in the next two weeks?",
  "Show plumbing and electricity costs at Park & Parkside.",
];

export default function Copilot() {
  const hasToken = typeof window !== "undefined" && !!getToken();
  const [q, setQ] = useState("");
  const [answer, setAnswer] = useState<any>(null);

  const ask = useMutation({
    mutationFn: (question: string) => copilotQuery(question),
    onSuccess: (r) => setAnswer(r),
  });

  if (!hasToken) return <p className="text-navy/70">Select a persona to use the copilot.</p>;

  const r = answer?.result;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Invoice Copilot</h1>
        <p className="text-navy/70">
          Natural language is a view over controlled data — answers are grounded in invoices you’re
          permitted to see, with citations.
        </p>
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); if (q.trim()) ask.mutate(q.trim()); }}
        className="flex gap-2"
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Ask about invoices, exceptions, vendors, budgets…"
          className="flex-1 rounded-md border border-navy/15 px-3 py-2 text-sm"
        />
        <button type="submit" disabled={ask.isPending}
          className="rounded-md bg-teal px-4 py-2 text-sm font-medium text-white hover:bg-teal-light disabled:opacity-50">
          {ask.isPending ? "Thinking…" : "Ask"}
        </button>
      </form>

      <div className="flex flex-wrap gap-2">
        {SUGGESTIONS.map((sug) => (
          <button key={sug} onClick={() => { setQ(sug); ask.mutate(sug); }}
            className="rounded-full border border-navy/15 px-3 py-1 text-xs text-navy/70 hover:bg-navy-50">
            {sug}
          </button>
        ))}
      </div>

      {r && (
        <div className="rounded-lg border border-teal/30 bg-teal/5 p-4">
          <div className="mb-2 flex items-center justify-between text-xs text-navy/50">
            <span>Grounded answer{r.insufficient_data ? " · insufficient data" : ""} · {Math.round((r.confidence ?? 0) * 100)}% confidence</span>
            <span>{answer.model} · {answer.tokens?.in}→{answer.tokens?.out} tok · over {answer.context_size} invoices</span>
          </div>
          <div className="whitespace-pre-wrap text-sm text-navy/85">{r.answer}</div>
          {r.cited_tracking_ids?.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1">
              <span className="text-xs text-navy/50">Citations:</span>
              {r.cited_tracking_ids.map((t: string) => (
                <span key={t} className="rounded bg-white px-1.5 py-0.5 font-mono text-[10px] text-teal">{t}</span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
