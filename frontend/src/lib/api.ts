// src/lib/api.ts
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "/api";

function getAuthHeader() {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("abs_token");
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

function handleUnauthorized() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("abs_token");
  localStorage.removeItem("abs_user");
  window.location.replace("/login");
}

async function parseError(res: Response, fallback: string): Promise<string> {
  try {
    const data = await res.json();
    return data.detail || data.message || fallback;
  } catch {
    return fallback;
  }
}

export async function apiGet<T>(path: string, withAuth = true): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (withAuth) Object.assign(headers, getAuthHeader());

  const res = await fetch(`${API_BASE}${path}`, { method: "GET", headers });

  if (res.status === 401) { handleUnauthorized(); throw new Error("Session expired"); }
  if (!res.ok) throw new Error(await parseError(res, `GET ${path} failed (${res.status})`));

  return res.json() as Promise<T>;
}

export async function apiPost<TReq, TRes>(
  path: string,
  body: TReq,
  withAuth = true,
): Promise<TRes> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (withAuth) {
    Object.assign(headers, getAuthHeader());
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  if (res.status === 401) { handleUnauthorized(); throw new Error("Session expired"); }
  if (!res.ok) throw new Error(await parseError(res, `POST ${path} failed (${res.status})`));

  return res.json() as Promise<TRes>;
}

export async function apiPut<TReq, TRes>(path: string, body: TReq, withAuth = true): Promise<TRes> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (withAuth) Object.assign(headers, getAuthHeader());

  const res = await fetch(`${API_BASE}${path}`, { method: "PUT", headers, body: JSON.stringify(body) });

  if (res.status === 401) { handleUnauthorized(); throw new Error("Session expired"); }
  if (!res.ok) throw new Error(await parseError(res, `PUT ${path} failed (${res.status})`));

  return res.json() as Promise<TRes>;
}

export async function apiDelete(path: string, withAuth = true): Promise<void> {
  const headers: Record<string, string> = {};
  if (withAuth) Object.assign(headers, getAuthHeader());

  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    headers,
  });

  if (res.status === 401) { handleUnauthorized(); throw new Error("Session expired"); }
  if (!res.ok) throw new Error(await parseError(res, `DELETE ${path} failed (${res.status})`));
}

// Download helpers
export async function apiGetBlob(path: string, withAuth = true): Promise<Blob> {
  const headers: Record<string, string> = {};
  if (withAuth) Object.assign(headers, getAuthHeader());

  const res = await fetch(`${API_BASE}${path}`, { method: 'GET', headers });

  if (res.status === 401) { handleUnauthorized(); throw new Error("Session expired"); }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `GET ${path} failed (${res.status})`);
  }

  return res.blob();
}

export async function apiGetText(path: string, withAuth = true): Promise<string> {
  const headers: Record<string, string> = {};
  if (withAuth) Object.assign(headers, getAuthHeader());

  const res = await fetch(`${API_BASE}${path}`, {
    method: 'GET',
    headers,
  });

  if (res.status === 401) { handleUnauthorized(); throw new Error("Session expired"); }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `GET ${path} failed (${res.status})`);
  }

  return res.text();
}

// History Backup Date Management
export async function downloadBackupDate(date: string) {
  return apiGetBlob(`/backups/download-date/${date}`);
}

export async function deleteBackupDate(date: string) {
  return apiDelete(`/backups/date/${date}`);
}

export async function downloadActiveBackups() {
  return apiGetBlob('/backups/download-active');
}
