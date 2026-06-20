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
