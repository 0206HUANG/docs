const API_BASE = "/api/v1";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

export const api = {
  login: (email: string, password: string, tenant_id: string) =>
    request<{ access_token: string; refresh_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password, tenant_id }),
    }),

  me: () => request<{ id: string; email: string; name: string; roles: string[] }>("/auth/me"),

  emails: {
    list: (params?: { account_id?: string; email_type?: string; limit?: number; offset?: number }) => {
      const q = new URLSearchParams(Object.entries(params || {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)]));
      return request<{ total: number; items: EmailSummary[] }>(`/emails?${q}`);
    },
    get: (id: string) => request<EmailDetail>(`/emails/${id}`),
    audit: (id: string) => request<AuditEntry[]>(`/emails/${id}/audit`),
  },

  tickets: {
    list: (status?: string) => request<Ticket[]>(`/tickets${status ? `?status=${status}` : ""}`),
    get: (id: string) => request<Ticket>(`/tickets/${id}`),
    claim: (id: string) => request<Ticket>(`/tickets/${id}/claim`, { method: "POST" }),
    reply: (id: string, content: string) =>
      request(`/tickets/${id}/reply`, { method: "POST", body: JSON.stringify({ content }) }),
    resolve: (id: string) => request<Ticket>(`/tickets/${id}/resolve`, { method: "POST" }),
  },

  accounts: {
    list: () => request<Account[]>("/accounts"),
    toggle: (id: string) => request(`/accounts/${id}/toggle`, { method: "POST" }),
    test: (id: string) => request<{ success: boolean }>(`/accounts/${id}/test`, { method: "POST" }),
  },

  notifications: {
    list: () => request<Notification[]>("/notifications"),
    read: (id: string) => request(`/notifications/${id}/read`, { method: "POST" }),
    readAll: () => request("/notifications/read-all", { method: "POST" }),
  },

  stats: () => request<{ emails_today: number; open_tickets: number }>("/reports/stats"),
};

export interface EmailSummary {
  id: string;
  from_addr: string;
  from_name: string | null;
  subject: string | null;
  received_at: string | null;
  email_type: string | null;
  urgency: number | null;
  has_sensitive: boolean;
  reply_status: string | null;
}

export interface EmailDetail extends EmailSummary {
  body_text: string | null;
  language: string | null;
  reply: { id: string; draft_content: string | null; final_content: string | null; status: string; send_strategy: string } | null;
  attachments: { id: string; filename: string; content_type: string | null }[];
}

export interface AuditEntry {
  stage: string;
  status: string;
  detail: Record<string, unknown>;
  error_msg: string | null;
  created_at: string;
}

export interface Ticket {
  id: string;
  title: string;
  reason: string;
  status: string;
  priority: number;
  assigned_to: string | null;
  created_at: string;
  replies?: { id: string; content: string; created_at: string }[];
}

export interface Account {
  id: string;
  email_address: string;
  display_name: string | null;
  positioning: string;
  is_active: boolean;
  sync_status: string;
  last_synced_at: string | null;
}

export interface Notification {
  id: string;
  type: string;
  title: string;
  body: string | null;
  is_read: boolean;
  created_at: string;
}
