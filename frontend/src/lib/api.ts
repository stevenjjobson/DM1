const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type RequestOptions = {
  method?: string;
  body?: unknown;
  token?: string | null;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
  }
}

async function doFetch(path: string, method: string, body: unknown, token: string | null | undefined): Promise<Response> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return fetch(`${API_BASE}/api${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, token } = options;

  let res = await doFetch(path, method, body, token);

  // On 401, try refreshing the token and retry once
  if (res.status === 401 && token) {
    try {
      const { useAuthStore } = await import("@/stores/auth-store");
      const refreshed = await useAuthStore.getState().refresh();
      if (refreshed) {
        const newToken = useAuthStore.getState().accessToken;
        res = await doFetch(path, method, body, newToken);
      }
    } catch {
      // Refresh failed — fall through to error handling
    }
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    let detail = error.detail || res.statusText;
    if (Array.isArray(detail)) {
      detail = detail.map((e: { msg?: string }) => e.msg || "Validation error").join(". ");
    }
    throw new ApiError(res.status, String(detail));
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}
