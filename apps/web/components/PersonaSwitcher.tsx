"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import { api, setToken, getToken, Persona, TokenResponse } from "@/lib/api";
import { useEffect, useState } from "react";

// Persona switcher (Phase 1 acceptance): pick a seeded persona, receive a signed
// session token, and see the capabilities that RBAC will enforce server-side.
export function PersonaSwitcher() {
  const [active, setActive] = useState<Persona | null>(null);

  const personas = useQuery({
    queryKey: ["personas"],
    queryFn: () => api<Persona[]>("/v1/personas"),
  });

  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api<Persona & { user_id: string }>("/v1/me"),
    enabled: !!getToken(),
    retry: false,
  });

  useEffect(() => {
    if (me.data) {
      setActive({
        id: (me.data as any).user_id,
        email: me.data.email,
        full_name: me.data.full_name,
        role: me.data.role,
        capabilities: me.data.capabilities,
      });
    }
  }, [me.data]);

  const switchTo = useMutation({
    mutationFn: (id: string) =>
      api<TokenResponse>(`/v1/personas/${id}/session`, { method: "POST" }),
    onSuccess: (data) => {
      // Persist the new identity, then hard-reload the current page so every panel
      // refetches under the new persona. This avoids react-query `enabled`-gating edge
      // cases (a freshly logged-in page not re-running queries that were disabled while
      // logged out) and makes the switch unambiguous during a demo.
      setToken(data.access_token);
      setActive(data.persona);
      if (typeof window !== "undefined") window.location.reload();
    },
  });

  return (
    <div className="flex items-center gap-3 text-sm">
      {active && (
        <span className="hidden text-navy-50/80 sm:inline">
          {active.full_name} · <span className="text-teal-light">{active.role}</span>
        </span>
      )}
      <select
        className="rounded border border-white/20 bg-navy-700 px-2 py-1 text-white"
        value={active?.id ?? ""}
        onChange={(e) => e.target.value && switchTo.mutate(e.target.value)}
      >
        <option value="" disabled>
          {personas.isLoading ? "Loading personas…" : "Switch persona"}
        </option>
        {personas.data?.map((p) => (
          <option key={p.id} value={p.id}>
            {p.full_name}
          </option>
        ))}
      </select>
    </div>
  );
}
