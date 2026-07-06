const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : "http://localhost:8000");

export type ApiState = {
  token: string | null;
  setToken: (token: string | null) => void;
};

function apiErrorMessage(error: unknown, fallback: string): string {
  if (typeof error === "string") return error;
  if (Array.isArray(error)) {
    return error
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) return String(item.msg);
        return JSON.stringify(item);
      })
      .join(", ");
  }
  if (error && typeof error === "object" && "msg" in error) return String(error.msg);
  return fallback;
}

export async function apiFetch<T>(path: string, token?: string | null, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...options, headers });
  } catch {
    throw new Error(`Cannot reach the Finlio backend at ${API_URL}. Make sure FastAPI is running on port 8000.`);
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(apiErrorMessage(error.detail, response.statusText || "Request failed"));
  }
  return response.json();
}

export const formatMoney = (value: number | string | null | undefined, currency = "EUR") =>
  new Intl.NumberFormat(
    typeof document !== "undefined" ? document.documentElement.lang || "en" : "en",
    { style: "currency", currency }
  ).format(Number(value || 0));
