export type Course = {
  id: string
  title: string
  description: string
  target_audience: string
  language: string
  difficulty: string
  desired_duration_minutes: number
  company_context: string
  compliance_requirements: string
  source_material?: string | null
  status: string
  created_at: string
  updated_at: string
  approved_at?: string | null
}

export type Chapter = {
  id: string
  order: number
  title: string
  duration_minutes: number
  bloom_level?: string
  learning_outcome?: string
  interaction?: string[]
  quiz?: Record<string, unknown>
}

export type CoursePlan = {
  id: string
  course_id: string
  status: string
  created_at: string
  updated_at: string
  plan: {
    course_overview: Record<string, unknown>
    learning_objectives: string[]
    chapters: Chapter[]
    compliance_requirements: string[]
    practical_exercises: string[]
    assessment_strategy: Record<string, unknown>
    company_knowledge_placeholders: string[]
  }
}

export type DevinJob = {
  id: string
  course_id: string
  phase: string
  devin_session_id?: string | null
  devin_job_id?: string | null
  prompt: string
  status: string
  branch?: string | null
  commit_sha?: string | null
  pr_url?: string | null
  transcript_summary?: string | null
  error?: string | null
  created_at: string
  updated_at: string
  completed_at?: string | null
  raw_status_payload?: Record<string, unknown>
}

export type Asset = {
  id: string
  template_link: string
  type: string
  dimensions: string
  description: string
  purpose: string
  status: string
  final_url?: string | null
  validation_result?: string | null
  source?: string | null
  updated_at: string
}

export type CourseState = {
  course: Course
  plan?: CoursePlan | null
  spec?: {
    id: string
    spec_markdown: string
    spec: Record<string, unknown>
    asset_manifest: Record<string, unknown>[]
    created_at: string
  } | null
  assets: Asset[]
  devin_jobs: DevinJob[]
  devin_events: Array<Record<string, unknown>>
  prompts: Array<{ id: string; phase: string; prompt: string; created_at: string }>
  qa_results: Array<Record<string, unknown>>
  hosted_output?: { course_url: string; iframe_url: string; created_at: string } | null
  reporting?: Record<string, unknown>
}

export type PreflightResult = {
  ok: boolean
  mode: 'real' | 'testing_fake'
  checks: Record<string, unknown>
  error?: string | null
}

export type CourseCreate = {
  title: string
  description: string
  target_audience: string
  language: string
  difficulty: string
  desired_duration_minutes: number
  company_context: string
  compliance_requirements: string
  source_material?: string
}
