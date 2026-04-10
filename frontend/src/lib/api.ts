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

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, token } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}/api${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    let detail = error.detail || res.statusText;
    // FastAPI 422 returns detail as an array of validation errors
    if (Array.isArray(detail)) {
      detail = detail.map((e: { msg?: string }) => e.msg || "Validation error").join(". ");
    }
    throw new ApiError(res.status, String(detail));
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}
