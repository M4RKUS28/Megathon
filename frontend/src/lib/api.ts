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

export function apiErrorMessage(error: unknown, fallback = "Request failed"): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((item) => item?.msg ?? String(item)).join(", ");
    return error.message || fallback;
  }
  if (error instanceof Error) return error.message;
  return fallback;
}

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

// ── Courses ────────────────────────────────────────────────────────────────

export type CourseStatus =
  | "draft"
  | "planning"
  | "plan_review"
  | "authoring"
  | "spec_ready"
  | "building"
  | "ready"
  | "published"
  | "failed";

export interface CourseSummary {
  id: string;
  title: string;
  description: string;
  status: CourseStatus;
  version: number;
  created_by: string;
  created_at: string;
  host_url: string | null;
}

// ── Phase 1 Course Plan ──────────────────────────────────────────────────────
export interface PlanChapter {
  id: string;
  title: string;
  objective: string;
  competency: string;
  estimated_minutes: number;
  key_points: string[];
  bloom_level: string;
}

export interface KnowledgeHit {
  tool: string;
  query: string;
  summary: string;
}

export interface CoursePlan {
  title: string;
  description: string;
  language: string;
  difficulty: string;
  audience: string;
  estimated_minutes: number;
  objectives: string[];
  competencies: string[];
  mandatory_topics: string[];
  compliance_requirements: string[];
  knowledge_sources: KnowledgeHit[];
  chapters: PlanChapter[];
}

// ── Phase 2 Lastenheft (spec) ───────────────────────────────────────────────
export interface AssetSpec {
  template_link: string;
  type: string;
  dimensions: string;
  description: string;
  purpose: string;
}

export interface CourseDetail extends CourseSummary {
  plan: CoursePlan | null;
  spec: Record<string, unknown> | null;
  asset_manifest: { assets: AssetSpec[] } | null;
  asset_map: Record<string, string> | null;
  course_url: string | null;
  iframe_url: string | null;
  devin_session_id: string | null;
  devin_session_url: string | null;
}

export interface GenerationJobRecord {
  id: string;
  type: string;
  status: string;
  error: string | null;
  devin_session_id: string | null;
  devin_session_url: string | null;
  result: Record<string, unknown> | null;
  created_at: string;
}

export interface CourseBriefInput {
  audience: string;
  goals: string;
  tone: string;
  duration: string;
  topics: string[];
}

export interface EditDiff {
  blocks_changed: string[];
  blocks_added: string[];
  blocks_removed: string[];
  summary: string;
}

export interface EditRecord {
  id: string;
  prompt: string;
  target_selector: string | null;
  status: string;
  preview_url: string | null;
  diff: EditDiff | null;
  devin_session_id: string | null;
  created_at: string;
}

export const coursesApi = {
  list: () => api.get<CourseSummary[]>("/courses"),
  get: (id: string) => api.get<CourseDetail>(`/courses/${id}`),
  create: (body: { title: string; description: string; brief: CourseBriefInput }) =>
    api.post<CourseDetail>("/courses", body),
  approvePlan: (id: string, plan?: CoursePlan) =>
    api.post<GenerationJobRecord>(`/courses/${id}/plan/approve`, { plan: plan ?? null }),
  jobs: (id: string) => api.get<GenerationJobRecord[]>(`/courses/${id}/jobs`),
  edits: {
    list: (id: string) => api.get<EditRecord[]>(`/courses/${id}/edits`),
    create: (id: string, body: { prompt: string; target_selector?: string; target_text?: string }) =>
      api.post<EditRecord>(`/courses/${id}/edits`, body),
    accept: (id: string, editId: string) =>
      api.post<GenerationJobRecord>(`/courses/${id}/edits/${editId}/accept`),
    reject: (id: string, editId: string) =>
      api.post<EditRecord>(`/courses/${id}/edits/${editId}/reject`),
  },
};

// ── Learning / enrollment / assignments ─────────────────────────────────────

export interface Enrollment {
  status: string;
  progress_pct: number;
  current_chapter: number | null;
  score: number | null;
  completed_at: string | null;
}

export interface LearningCourse extends CourseSummary {
  enrollment: Enrollment | null;
}

export type LearningCourseDetail = LearningCourse;

export interface ProgressUpdate {
  status?: string;
  progress_pct?: number;
  current_chapter?: number;
  current_page?: number;
  score?: number;
  time_spent_seconds?: number;
  quiz_attempts?: number;
  drop_off_point?: string;
  engagement_score?: number;
}

export interface AssignmentRecord {
  id: string;
  assignee_user_id: string | null;
  assignee_department_id: string | null;
  mandatory: boolean;
  due_date: string | null;
  created_at: string;
}

export interface CourseReportRow {
  user_id: string;
  display_name: string;
  email: string;
  status: string;
  progress_pct: number;
  score: number | null;
  time_spent_seconds: number;
  quiz_attempts: number;
  engagement_score: number;
  certified: boolean;
  completed_at: string | null;
}

// ── Phase 5 reporting & standards ───────────────────────────────────────────
export interface TeamMemberProgress {
  user_id: string;
  display_name: string;
  email: string;
  assigned: number;
  completed: number;
  in_progress: number;
  not_started: number;
  avg_score: number | null;
  compliance_pct: number;
}

export interface ManagerDashboard {
  team_size: number;
  assigned_courses: number;
  completed_courses: number;
  open_courses: number;
  avg_score: number | null;
  compliance_pct: number;
  members: TeamMemberProgress[];
}

export const reportingApi = {
  managerDashboard: () => api.get<ManagerDashboard>("/reporting/manager/dashboard"),
  xapi: (courseId: string) =>
    api.get<Record<string, unknown>[]>(`/reporting/courses/${courseId}/xapi`),
  scormUrl: (courseId: string, version: "1.2" | "2004" = "1.2") =>
    `/api/v1/reporting/courses/${courseId}/scorm?version=${version}`,
};

export const learningApi = {
  list: () => api.get<LearningCourse[]>("/learning/courses"),
  get: (id: string) => api.get<LearningCourseDetail>(`/learning/courses/${id}`),
  progress: (id: string, body: ProgressUpdate) =>
    api.post<Enrollment>(`/learning/courses/${id}/progress`, body),
};

export const assignmentsApi = {
  list: (courseId: string) => api.get<AssignmentRecord[]>(`/courses/${courseId}/assignments`),
  create: (
    courseId: string,
    body: { user_id?: string; department_id?: string; mandatory?: boolean },
  ) => api.post<AssignmentRecord>(`/courses/${courseId}/assignments`, body),
  remove: (courseId: string, id: string) =>
    api.delete(`/courses/${courseId}/assignments/${id}`),
  report: (courseId: string) => api.get<CourseReportRow[]>(`/courses/${courseId}/report`),
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

// ── Provider diagnostics (verify external API keys work) ─────────────────────

export interface ProviderCheck {
  provider: string;
  label: string;
  configured: boolean;
  ok: boolean;
  detail: string;
  status: number | null;
  latency_ms: number | null;
}

export const diagnosticsApi = {
  providers: () =>
    api.get<{ providers: ProviderCheck[] }>("/diagnostics/providers"),
};
