"use client";

import { useQuery } from "@tanstack/react-query";
import { api, getToken } from "@/lib/api";

interface CapRow {
  capability: string;
  runs: number;
  input_tokens: number;
  output_tokens: number;
  avg_latency_ms: number;
  cost_usd: number;
  errors: number;
  models: string[];
}
interface ModelRuns {
  by_capability: CapRow[];
  total_runs: number;
  total_cost_usd: number;
}

export default function AIDashboard() {
  const hasToken = typeof window !== "undefined" && !!getToken();
  const q = useQuery({
    queryKey: ["model-runs"],
    queryFn: () => api<ModelRuns>("/v1/model-runs"),
    enabled: hasToken,
    retry: false,
  });

  if (!hasToken) return <p className="text-navy/70">Select a persona to view the AI dashboard.</p>;
  if (q.error) return <p className="text-navy/60">You need the view_model_trace capability to see model traces.</p>;
  const d = q.data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">AI Model Dashboard</h1>
        <p className="text-navy/70">
          Every model call is logged with provider, tokens, latency, and cost — governance and
          evaluation, not a black box.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-lg border border-navy/10 bg-white p-4 shadow-sm">
          <div className="text-sm text-navy/60">Total model runs</div>
          <div className="mt-1 text-2xl font-semibold">{d?.total_runs ?? "—"}</div>
        </div>
        <div className="rounded-lg border border-navy/10 bg-white p-4 shadow-sm">
          <div className="text-sm text-navy/60">Total cost (est.)</div>
          <div className="mt-1 text-2xl font-semibold">${d?.total_cost_usd?.toFixed(4) ?? "—"}</div>
        </div>
        <div className="rounded-lg border border-navy/10 bg-white p-4 shadow-sm">
          <div className="text-sm text-navy/60">Capabilities in use</div>
          <div className="mt-1 text-2xl font-semibold">{d?.by_capability.length ?? "—"}</div>
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-navy/10 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-navy-50 text-left text-navy/60">
            <tr>
              <th className="px-4 py-2 font-medium">Capability</th>
              <th className="px-4 py-2 font-medium">Model(s)</th>
              <th className="px-4 py-2 font-medium">Runs</th>
              <th className="px-4 py-2 font-medium">Tokens in→out</th>
              <th className="px-4 py-2 font-medium">Avg latency</th>
              <th className="px-4 py-2 font-medium">Cost</th>
              <th className="px-4 py-2 font-medium">Errors</th>
            </tr>
          </thead>
          <tbody>
            {d?.by_capability.map((c) => (
              <tr key={c.capability} className="border-t border-navy/5">
                <td className="px-4 py-2 font-medium">{c.capability}</td>
                <td className="px-4 py-2 font-mono text-xs text-navy/60">{c.models.join(", ")}</td>
                <td className="px-4 py-2">{c.runs}</td>
                <td className="px-4 py-2">{c.input_tokens.toLocaleString()}→{c.output_tokens.toLocaleString()}</td>
                <td className="px-4 py-2">{(c.avg_latency_ms / 1000).toFixed(1)}s</td>
                <td className="px-4 py-2">${c.cost_usd.toFixed(4)}</td>
                <td className={`px-4 py-2 ${c.errors ? "text-red-600" : "text-navy/40"}`}>{c.errors}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
