// src/lib/api.ts
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "/api";

function getAuthHeader() {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("abs_token");
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

export async function apiGet<T>(path: string, withAuth = true): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (withAuth) {
    Object.assign(headers, getAuthHeader());
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    headers,
  });

  if (!res.ok) {
    let errorMessage = `GET ${path} failed (${res.status})`;
    try {
      const errorData = await res.json();
      errorMessage = errorData.detail || errorData.message || errorMessage;
    } catch (e) {
      // If JSON parsing fails, keep default message
    }
    throw new Error(errorMessage);
  }

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

  if (!res.ok) {
    let errorMessage = `POST ${path} failed (${res.status})`;
    try {
      const errorData = await res.json();
      errorMessage = errorData.detail || errorData.message || errorMessage;
    } catch (e) {
      // If JSON parsing fails, keep default message
    }
    throw new Error(errorMessage);
  }

  return res.json() as Promise<TRes>;
}

export async function apiPut<TReq, TRes>(path: string, body: TReq, withAuth = true): Promise<TRes> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (withAuth) Object.assign(headers, getAuthHeader());

  const res = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers,
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    let errorMessage = `PUT ${path} failed (${res.status})`;
    try {
      const errorData = await res.json();
      errorMessage = errorData.detail || errorData.message || errorMessage;
    } catch (e) {
      // If JSON parsing fails, keep default message
    }
    throw new Error(errorMessage);
  }

  return res.json() as Promise<TRes>;
}

export async function apiDelete(path: string, withAuth = true): Promise<void> {
  const headers: Record<string, string> = {};
  if (withAuth) Object.assign(headers, getAuthHeader());

  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    headers,
  });

  if (!res.ok) {
    let errorMessage = `DELETE ${path} failed (${res.status})`;
    try {
      const errorData = await res.json();
      errorMessage = errorData.detail || errorData.message || errorMessage;
    } catch (e) {
      // If JSON parsing fails, keep default message
    }
    throw new Error(errorMessage);
  }
}

// Download helpers
export async function apiGetBlob(path: string, withAuth = true): Promise<Blob> {
  const headers: Record<string, string> = {};
  if (withAuth) Object.assign(headers, getAuthHeader());

  const res = await fetch(`${API_BASE}${path}`, {
    method: 'GET',
    headers,
  });

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
