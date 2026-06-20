import axios from "axios";
import { getValidToken } from "./auth";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api/v1",
});

api.interceptors.request.use(async (config) => {
  const token = await getValidToken();
  config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      window.location.href = "/signin";
    }
    return Promise.reject(err);
  },
);

// Bare axios for unauthenticated calls (e.g. public branding before login).
export const publicApi = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api/v1",
});

// ── Identity / tenant ──────────────────────────────────────────────────────

export type AppRole = "admin" | "course_creator" | "user";

export interface CompanySummary {
  id: string;
  name: string;
  slug: string;
  status: string;
}

export interface Me {
  id: string;
  email: string;
  display_name: string;
  role: AppRole;
  company: CompanySummary;
}

export const meApi = {
  get: () => api.get<Me>("/me"),
};

// ── Branding (white-label) ─────────────────────────────────────────────────

export interface StyleGuide {
  companyName: string;
  logoUrls: string[];
  brandColors: string[];
  fonts: string[];
  imageUrls: string[];
  websiteUrl: string;
}

export interface Branding {
  company_id: string;
  company_name: string;
  slug: string;
  primary_color: string | null;
  logo_url: string | null;
  style_guide: StyleGuide;
}

export const brandingApi = {
  mine: () => api.get<Branding>("/branding"),
  public: (slug: string) => publicApi.get<Branding>(`/public/branding/${slug}`),
  update: (body: { style_guide: StyleGuide; primary_color: string | null; logo_url: string | null }) =>
    api.put<Branding>("/branding", body),
};

// ── People / Org ───────────────────────────────────────────────────────────

export interface Department {
  id: string;
  name: string;
  parent_id: string | null;
}

export interface Person {
  id: string;
  email: string;
  display_name: string;
  role: AppRole;
  department_id: string | null;
  manager_id: string | null;
}

export const peopleApi = {
  list: () => api.get<Person[]>("/people"),
  update: (id: string, body: Partial<Pick<Person, "role" | "department_id" | "manager_id">>) =>
    api.patch<Person>(`/people/${id}`, body),
};

export const departmentApi = {
  list: () => api.get<Department[]>("/departments"),
  create: (body: { name: string; parent_id?: string | null }) =>
    api.post<Department>("/departments", body),
  remove: (id: string) => api.delete(`/departments/${id}`),
};

// ── Companies (tenant management) ──────────────────────────────────────────

export interface CompanyRecord {
  id: string;
  name: string;
  slug: string;
  status: string;
  created_at: string;
}

export const companyApi = {
  list: () => api.get<CompanyRecord[]>("/companies"),
  create: (body: { name: string; slug: string }) => api.post<CompanyRecord>("/companies", body),
};

// ── File endpoints ─────────────────────────────────────────────────────────

export interface FileRecord {
  id: string;
  user_id: string;
  filename: string;
  object_name: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
  updated_at: string;
}

export interface UploadIntent {
  file_id: string;
  upload_url: string;
  object_name: string;
}

export const filesApi = {
  list: (offset = 0, limit = 50) =>
    api.get<{ items: FileRecord[] }>("/files", { params: { offset, limit } }),

  initiateUpload: (filename: string, content_type: string) =>
    api.post<UploadIntent>("/files/upload/initiate", { filename, content_type }),

  confirmUpload: (file_id: string, size_bytes: number) =>
    api.post<FileRecord>(`/files/upload/${file_id}/confirm`, { size_bytes }),

  getDownloadUrl: (file_id: string) =>
    api.get<{ download_url: string }>(`/files/${file_id}/download-url`),

  delete: (file_id: string) => api.delete(`/files/${file_id}`),
};

export async function uploadFileDirect(file: File): Promise<FileRecord> {
  const { data: intent } = await filesApi.initiateUpload(file.name, file.type);

  await axios.put(intent.upload_url, file, {
    headers: { "Content-Type": file.type },
  });

  const { data: record } = await filesApi.confirmUpload(intent.file_id, file.size);
  return record;
}
