export async function studioMutation<T>(url: string, method: "POST" | "PATCH" | "DELETE", body?: unknown): Promise<T> {
  const response = await fetch(url, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = await response.json().catch(() => null) as { data?: T; detail?: string; code?: string } | null;
  if (!response.ok) throw new Error(payload?.detail || payload?.code || `Studio request failed (${response.status}).`);
  return payload?.data as T;
}
