/**
 * Typed fetch client for the Paperlet API.
 *
 * Response types come from `schema.ts`, generated from `docs/openapi.yaml`
 * (`npm run openapi`). The auth token (localStorage) is attached automatically
 * when present, which also covers endpoints with optional auth.
 */

import type { components } from "./schema";

type S = components["schemas"];

export type Profile = S["Profile"];
export type TokenPair = S["TokenPair"];
export type PostView = S["PostView"];
export type Feed = S["Feed"];
export type WritersList = S["WritersList"];
export type WriterDetail = S["WriterDetail"];
export type AllocationSummary = S["AllocationSummary"];
export type AllocationResult = S["AllocationResult"];
export type CreatedPost = S["CreatedPost"];
export type WriterPosts = S["WriterPosts"];

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:5000";
const TOKEN_KEY = "paperlet_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

interface CallOptions {
  method?: string;
  body?: unknown;
}

async function call<T>(path: string, options: CallOptions = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    const body = (data ?? {}) as { code?: string; message?: string; detail?: string };
    throw new ApiError(res.status, body.message ?? body.detail ?? res.statusText, body.code);
  }
  return data as T;
}

const get = <T>(path: string): Promise<T> => call<T>(path);
const post = <T>(path: string, body?: unknown): Promise<T> =>
  call<T>(path, { method: "POST", body: body ?? {} });
const patch = <T>(path: string, body?: unknown): Promise<T> =>
  call<T>(path, { method: "PATCH", body: body ?? {} });
const del = <T>(path: string): Promise<T> => call<T>(path, { method: "DELETE" });

export const api = {
  register: (
    email: string,
    password: string,
    profile?: { first_name?: string; last_name?: string; avatar_url?: string },
  ) =>
    post<S["RegisteredUser"]>("/api/v1/auth/register", {
      email,
      password,
      ...profile,
    }),
  login: (email: string, password: string) =>
    post<TokenPair>("/api/v1/auth/login", { email, password }),
  me: () => get<Profile>("/api/v1/auth/me"),

  listWriters: (q = "", limit = 20, offset = 0) =>
    get<WritersList>(
      `/api/v1/writers?q=${encodeURIComponent(q)}&limit=${limit}&offset=${offset}`,
    ),
  getWriter: (id: string) => get<WriterDetail>(`/api/v1/writers/${id}`),

  subscribe: () => post<AllocationSummary>("/api/v1/subscriptions/subscribe"),
  allocations: () => get<AllocationSummary>("/api/v1/subscriptions/allocations"),
  assign: (writer_id: string) =>
    post<AllocationResult>("/api/v1/subscriptions/allocations/assign", { writer_id }),
  swap: (current_writer_id: string, new_writer_id: string) =>
    post<AllocationResult>("/api/v1/subscriptions/allocations/swap", {
      current_writer_id,
      new_writer_id,
    }),
  release: (writer_id: string) =>
    del<AllocationResult>(`/api/v1/subscriptions/allocations/${writer_id}`),

  createPost: (input: {
    title: string;
    preview_content: string;
    subscriber_content?: string;
    scheduled_at?: string;
  }) => post<CreatedPost>("/api/v1/posts", input),
  publishPost: (id: string) => post<S["PublishedPost"]>(`/api/v1/posts/${id}/publish`),
  getPost: (id: string) => get<PostView>(`/api/v1/posts/${id}`),
  feed: (limit = 20, cursor?: string) =>
    get<Feed>(
      `/api/v1/posts/feed?limit=${limit}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
    ),
  recent: (limit = 10) => get<S["RecentPosts"]>(`/api/v1/posts/recent?limit=${limit}`),
  writerPosts: (status?: string) =>
    get<WriterPosts>(`/api/v1/posts/writer${status ? `?status=${status}` : ""}`),
  updatePost: (id: string, input: { title?: string; preview_content?: string; subscriber_content?: string }) =>
    patch<S["UpdatedPost"]>(`/api/v1/posts/${id}`, input),
};
