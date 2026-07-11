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
    // Session expired / not authenticated → clear tokens and bounce to login
    if (res.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

export const api = {
  tenantByDomain: (domain: string) =>
    request<{ tenant_id: string; name: string }>(`/auth/tenant?domain=${encodeURIComponent(domain)}`),

  login: (email: string, password: string, tenant_id: string) =>
    request<{ access_token: string; refresh_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password, tenant_id }),
    }),

  me: () => request<{ id: string; email: string; name: string; tenant_id: string; roles: string[] }>("/auth/me"),

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

  stats: () => request<{
    emails_today: number;
    emails_week: number;
    open_tickets: number;
    auto_sent_week: number;
    high_risk_week: number;
  }>("/reports/stats"),

  kb: {
    groups: () => request<KBGroup[]>("/kb/groups"),
    createGroup: (data: { name: string; category: string; positioning: string[]; email_types: string[] }) =>
      request<KBGroup>("/kb/groups", { method: "POST", body: JSON.stringify(data) }),
    addManual: (data: { group_id: string; title: string; content: string }) =>
      request("/kb/documents/manual", { method: "POST", body: JSON.stringify(data) }),
    docs: (group_id: string) => request<KBDocument[]>(`/kb/documents?group_id=${group_id}`),
  },

  settings: {
    getSensitiveWords: () => request<SensitiveWord[]>("/settings/sensitive-words"),
    addSensitiveWord: (word: string, category: string) =>
      request("/settings/sensitive-words", { method: "POST", body: JSON.stringify({ word, category }) }),
    deleteSensitiveWord: (id: string) =>
      request(`/settings/sensitive-words/${id}`, { method: "DELETE" }),
    getStrategies: () => request<EmailStrategy[]>("/settings/strategies"),
    updateStrategy: (email_type: string, data: { send_strategy: string; tone: string }) =>
      request(`/settings/strategies/${email_type}`, { method: "PUT", body: JSON.stringify(data) }),
    getLLM: () => request<{ provider: string; model: string }>("/settings/llm"),
    saveLLM: (data: { provider: string; api_key_enc: string; model: string }) =>
      request("/settings/llm", { method: "PUT", body: JSON.stringify(data) }),
  },

  createAccount: (data: {
    email_address: string; display_name: string; provider: string;
    imap_host: string; imap_port: number; smtp_host: string; smtp_port: number;
    username: string; password: string; positioning: string;
  }) => request<Account>("/accounts", { method: "POST", body: JSON.stringify(data) }),
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

export interface KBGroup {
  id: string;
  name: string;
  category: string;
  positioning: string[];
  email_types: string[];
  is_active: boolean;
  created_at: string;
}

export interface KBDocument {
  id: string;
  title: string;
  source_type: string;
  status: string;
  chunk_count: number;
  created_at: string;
}

export interface SensitiveWord {
  id: string;
  word: string;
  category: string;
  is_active: boolean;
}

export interface EmailStrategy {
  email_type: string;
  send_strategy: string;
  tone: string;
  is_active: boolean;
}
