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
api.interceptors.response.use((res) => res, (err) => {
    if (err.response?.status === 401) {
        window.location.href = "/signin";
    }
    return Promise.reject(err);
});
// Bare axios for unauthenticated calls (e.g. public branding before login).
export const publicApi = axios.create({
    baseURL: import.meta.env.VITE_API_URL || "/api/v1",
});
export const meApi = {
    get: () => api.get("/me"),
};
export const brandingApi = {
    mine: () => api.get("/branding"),
    public: (slug) => publicApi.get(`/public/branding/${slug}`),
    update: (body) => api.put("/branding", body),
};
export const filesApi = {
    list: (offset = 0, limit = 50) => api.get("/files", { params: { offset, limit } }),
    initiateUpload: (filename, content_type) => api.post("/files/upload/initiate", { filename, content_type }),
    confirmUpload: (file_id, size_bytes) => api.post(`/files/upload/${file_id}/confirm`, { size_bytes }),
    getDownloadUrl: (file_id) => api.get(`/files/${file_id}/download-url`),
    delete: (file_id) => api.delete(`/files/${file_id}`),
};
export async function uploadFileDirect(file) {
    const { data: intent } = await filesApi.initiateUpload(file.name, file.type);
    await axios.put(intent.upload_url, file, {
        headers: { "Content-Type": file.type },
    });
    const { data: record } = await filesApi.confirmUpload(intent.file_id, file.size);
    return record;
}
