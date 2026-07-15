// Thin API client. The persona token is kept in localStorage for the demo; every
// request attaches it as a bearer token so the backend can enforce RBAC/ABAC.
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TOKEN_KEY = "ledgerpulse.token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers || {}),
    },
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

// Multipart upload (FormData sets its own Content-Type/boundary).
export async function uploadInvoice(file: File, vendorHint?: string): Promise<any> {
  const token = getToken();
  const fd = new FormData();
  fd.append("file", file);
  if (vendorHint) fd.append("vendor_hint", vendorHint);
  const res = await fetch(`${API_URL}/v1/invoices/intake`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: fd,
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

export async function extractInvoice(id: string): Promise<any> {
  return api(`/v1/invoices/${id}/extract`, { method: "POST" });
}

export async function submitInvoice(id: string): Promise<any> {
  return api(`/v1/invoices/${id}/submit`, { method: "POST" });
}

export async function investigateInvoice(id: string): Promise<any> {
  return api(`/v1/invoices/${id}/investigate`, { method: "POST" });
}

export async function copilotQuery(question: string): Promise<any> {
  return api(`/v1/copilot/query`, { method: "POST", body: JSON.stringify({ question }) });
}

export async function exportInvoice(id: string): Promise<any> {
  return api(`/v1/invoices/${id}/export`, { method: "POST" });
}

export async function simulatePayment(id: string, amount: number, reference = "SIM-PAYMENT"): Promise<any> {
  return api(`/v1/invoices/${id}/simulate-payment`, {
    method: "POST",
    body: JSON.stringify({ amount, reference }),
  });
}

export async function decideApproval(
  stepId: string,
  decision: "APPROVED" | "REJECTED" | "REQUEST_INFO",
  reason?: string
): Promise<any> {
  return api(`/v1/approvals/${stepId}/decision`, {
    method: "POST",
    body: JSON.stringify({ decision, reason }),
  });
}

export async function patchField(
  id: string,
  field: string,
  value: string | null,
  lockVersion: number
): Promise<{ field: string; old_value: string | null; new_value: string | null; lock_version: number }> {
  return api(`/v1/invoices/${id}/fields`, {
    method: "PATCH",
    body: JSON.stringify({ field, value, lock_version: lockVersion }),
  });
}

export interface Persona {
  id: string;
  email: string;
  full_name: string;
  role: string;
  capabilities: string[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  persona: Persona;
}
