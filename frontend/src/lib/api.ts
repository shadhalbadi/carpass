const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8001";

export type User = {
  id: number;
  email: string;
  full_name: string;
  role: string;
  company_name: string;
  phone: string;
  is_active: boolean;
};

function authHeaders(): HeadersInit {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("carpass_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

export const api = {
  health: () => request<{ status: string }>("/api/health"),
  register: (body: Record<string, string>) =>
    request<{ access_token: string; user: User }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  login: async (email: string, password: string) => {
    const form = new URLSearchParams();
    form.set("username", email);
    form.set("password", password);
    const res = await fetch(`${API_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });
    if (!res.ok) throw new Error("Invalid credentials");
    return res.json() as Promise<{ access_token: string; user: User }>;
  },
  me: () => request<User>("/api/auth/me"),
  fetchCalculate: (url: string) =>
    request<any>("/api/calculator/fetch", { method: "POST", body: JSON.stringify({ url, save: true }) }),
  calculateFromListing: (listingId: number) =>
    request<any>(`/api/calculator/listing/${listingId}`, { method: "POST" }),
  manualCalculate: (car: any, origin_country?: string) =>
    request<any>("/api/calculator/manual", {
      method: "POST",
      body: JSON.stringify({ car, origin_country, save: true }),
    }),
  getListing: (id: number) => request<any>(`/api/listings/${id}`),
  searchListings: (params: Record<string, string | number | boolean | undefined>) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "" && v !== null) q.set(k, String(v));
    });
    return request<any>(`/api/listings/search?${q.toString()}`);
  },
  clearSeedListings: () => request<any>("/api/listings/seed", { method: "DELETE" }),  createWatch: (body: any) => request<any>("/api/watches", { method: "POST", body: JSON.stringify(body) }),
  listWatches: () => request<any[]>("/api/watches"),
  notifications: () => request<any[]>("/api/watches/notifications"),
  createShipment: (body: any) => request<any>("/api/shipments", { method: "POST", body: JSON.stringify(body) }),
  myShipments: () => request<any[]>("/api/shipments"),
  getShipment: (id: number) => request<any>(`/api/shipments/${id}`),
  track: (code: string) => request<any>(`/api/shipments/track/${code}`),
  updateMilestone: (id: number, body: any) =>
    request<any>(`/api/shipments/${id}/milestones`, { method: "POST", body: JSON.stringify(body) }),
  uploadDocument: async (id: number, file: File, doc_type: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("doc_type", doc_type);
    const token = localStorage.getItem("carpass_token");
    const res = await fetch(`${API_URL}/api/shipments/${id}/documents`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) throw new Error("Upload failed");
    return res.json();
  },
  agentShipments: () => request<any[]>("/api/agent/shipments"),
  agentClaim: (id: number) => request<any>(`/api/agent/shipments/${id}/claim`, { method: "POST" }),
  agentStatus: (id: number, body: any) =>
    request<any>(`/api/agent/shipments/${id}/status`, { method: "POST", body: JSON.stringify(body) }),
  adminFees: () => request<any[]>("/api/admin/fees"),
  adminRoutes: () => request<any[]>("/api/admin/routes"),
  adminCrawl: () => request<any>("/api/admin/crawl", { method: "POST" }),
  verifyPhotos: (id: number, listing_photo_urls: string[]) =>
    request<any>(`/api/shipments/${id}/verify-photos`, {
      method: "POST",
      body: JSON.stringify({ listing_photo_urls }),
    }),
};

export { API_URL };
