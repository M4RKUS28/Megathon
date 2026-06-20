import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  BadgeCheck,
  BookOpenCheck,
  ClipboardCheck,
  Database,
  FileText,
  Gauge,
  GitBranch,
  LayoutDashboard,
  Loader2,
  MonitorPlay,
  Play,
  RefreshCcw,
  ShieldCheck,
  Sparkles,
  Users
} from 'lucide-react'
import { api } from './lib/api'
import type { Chapter, Course, CourseCreate, CourseState, PreflightResult } from './types'

type Tab = 'dashboard' | 'new' | 'plan' | 'pipeline' | 'evidence' | 'preview' | 'reporting' | 'setup'

const demoCourse: CourseCreate = {
  title: 'Workplace Safety and Incident Reporting',
  description: 'Create a workplace safety onboarding course for warehouse employees.',
  target_audience: 'New warehouse employees',
  desired_duration_minutes: 45,
  language: 'English',
  difficulty: 'Beginner',
  company_context:
    'Logistics company with warehouse shifts, forklifts, picking zones, safety supervisors, incident reports, and mandatory PPE.',
  compliance_requirements: 'Every employee must pass each chapter quiz with at least 80 percent.',
  source_material: ''
}

const phaseOrder = [
  'Course Request',
  'Course Planner',
  'Approval',
  'Lastenheft',
  'Asset Manifest',
  'Devin Implementation',
  'Asset Fetching',
  'Devin Asset Integration',
  'Devin QA',
  'Hosting Output',
  'LMS Reporting',
  'Evidence Ledger'
]

function statusTone(status?: string) {
  if (!status) return 'bg-neutral-100 text-neutral-700 border-neutral-200'
  if (['ready_for_demo', 'approved', 'exit', 'ok', 'ready', 'completed'].includes(status)) return 'bg-teal-50 text-teal-800 border-teal-200'
  if (status.includes('error') || status.includes('failed')) return 'bg-red-50 text-red-800 border-red-200'
  if (status.includes('running') || status === 'queued' || status === 'created') return 'bg-amber-50 text-amber-800 border-amber-200'
  return 'bg-neutral-100 text-neutral-700 border-neutral-200'
}

function compactDate(value?: string | null) {
  if (!value) return 'pending'
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

function JsonBlock({ value }: { value: unknown }) {
  return <pre className="max-h-80 overflow-auto rounded-md bg-neutral-950 p-3 text-xs leading-relaxed text-neutral-100">{JSON.stringify(value, null, 2)}</pre>
}

function Metric({ label, value, icon: Icon }: { label: string; value: string | number; icon: typeof Gauge }) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-3 shadow-panel">
      <div className="flex items-center gap-2 text-xs font-medium uppercase text-neutral-500">
        <Icon className="h-4 w-4 text-tealcore" />
        {label}
      </div>
      <div className="mt-2 text-2xl font-semibold text-ink">{value}</div>
    </div>
  )
}

function EmptyPanel({ text }: { text: string }) {
  return <div className="rounded-lg border border-dashed border-neutral-300 bg-white p-6 text-sm text-neutral-600">{text}</div>
}

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard')
  const [courses, setCourses] = useState<Course[]>([])
  const [selectedCourseId, setSelectedCourseId] = useState<string>('')
  const [state, setState] = useState<CourseState | null>(null)
  const [preflight, setPreflight] = useState<PreflightResult | null>(null)
  const [error, setError] = useState<string>('')
  const [busy, setBusy] = useState<string>('')
  const [form, setForm] = useState<CourseCreate>(demoCourse)
  const [chapters, setChapters] = useState<Chapter[]>([])

  const selectedCourse = state?.course ?? courses.find((course) => course.id === selectedCourseId)
  const jobsByPhase = useMemo(() => new Map((state?.devin_jobs ?? []).map((job) => [job.phase, job])), [state])

  async function refresh() {
    setError('')
    const [courseList, preflightResult] = await Promise.all([api.listCourses(), api.preflight(false).catch((err) => ({ ok: false, mode: 'real' as const, checks: {}, error: err.message }))])
    setCourses(courseList)
    setPreflight(preflightResult)
    const nextSelected = selectedCourseId || courseList[0]?.id || ''
    setSelectedCourseId(nextSelected)
    if (nextSelected) {
      const fullState = await api.getCourse(nextSelected)
      setState(fullState)
      setChapters(fullState.plan?.plan.chapters ?? [])
    } else {
      setState(null)
      setChapters([])
    }
  }

  async function refreshSelected(id = selectedCourseId) {
    if (!id) return
    const fullState = await api.getCourse(id)
    setState(fullState)
    setChapters(fullState.plan?.plan.chapters ?? [])
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message))
  }, [])

  useEffect(() => {
    if (!selectedCourseId) return
    refreshSelected(selectedCourseId).catch((err) => setError(err.message))
  }, [selectedCourseId])

  async function withBusy(label: string, action: () => Promise<void>) {
    setBusy(label)
    setError('')
    try {
      await action()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy('')
    }
  }

  async function submitCourse() {
    await withBusy('course', async () => {
      const created = await api.createCourse(form)
      setSelectedCourseId(created.id)
      setActiveTab('plan')
      await refresh()
    })
  }

  async function generatePlan() {
    if (!selectedCourseId) return
    await withBusy('plan', async () => {
      await api.generatePlan(selectedCourseId)
      await refreshSelected()
      setActiveTab('plan')
    })
  }

  async function approve() {
    if (!selectedCourseId) return
    await withBusy('approve', async () => {
      await api.approve(
        selectedCourseId,
        chapters.map((chapter) => ({ id: chapter.id, title: chapter.title, duration_minutes: Number(chapter.duration_minutes) }))
      )
      await refreshSelected()
      setActiveTab('pipeline')
    })
  }

  function moveChapter(index: number, direction: -1 | 1) {
    const next = [...chapters]
    const target = index + direction
    if (target < 0 || target >= next.length) return
    ;[next[index], next[target]] = [next[target], next[index]]
    setChapters(next.map((chapter, order) => ({ ...chapter, order: order + 1 })))
  }

  const nav = [
    ['dashboard', LayoutDashboard, 'Dashboard'],
    ['new', Sparkles, 'New Course'],
    ['plan', ClipboardCheck, 'Plan Review'],
    ['pipeline', GitBranch, 'Pipeline'],
    ['evidence', ShieldCheck, 'Evidence'],
    ['preview', MonitorPlay, 'Preview'],
    ['reporting', Users, 'Reporting'],
    ['setup', Database, 'Setup']
  ] as const

  return (
    <div className="min-h-screen bg-neutral-100">
      <header className="border-b border-neutral-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <BookOpenCheck className="h-6 w-6 text-tealcore" />
              <h1 className="text-xl font-semibold tracking-normal text-ink">CourseForge Devin</h1>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-neutral-600">
              <span className={`rounded-md border px-2 py-1 text-xs font-medium ${statusTone(preflight?.ok ? 'ok' : 'failed')}`}>
                Devin preflight {preflight?.ok ? 'ready' : 'blocked'}
              </span>
              {selectedCourse && <span>{selectedCourse.title}</span>}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <select
              className="focus-ring min-w-0 rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm"
              value={selectedCourseId}
              onChange={(event) => setSelectedCourseId(event.target.value)}
            >
              <option value="">No course selected</option>
              {courses.map((course) => (
                <option key={course.id} value={course.id}>
                  {course.title}
                </option>
              ))}
            </select>
            <button className="focus-ring rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm font-medium" onClick={() => refresh()}>
              <RefreshCcw className="inline h-4 w-4" /> Refresh
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-4 px-4 py-4 sm:px-6 lg:grid-cols-[220px_1fr]">
        <nav className="rounded-lg border border-neutral-200 bg-white p-2 shadow-panel lg:sticky lg:top-4 lg:self-start">
          <div className="grid grid-cols-2 gap-1 lg:grid-cols-1">
            {nav.map(([tab, Icon, label]) => (
              <button
                key={tab}
                className={`focus-ring flex items-center gap-2 rounded-md px-3 py-2 text-left text-sm font-medium ${
                  activeTab === tab ? 'bg-tealcore text-white' : 'text-neutral-700 hover:bg-neutral-100'
                }`}
                onClick={() => setActiveTab(tab)}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="truncate">{label}</span>
              </button>
            ))}
          </div>
        </nav>

        <main className="space-y-4">
          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              <AlertTriangle className="mr-2 inline h-4 w-4" />
              {error}
            </div>
          )}
          {busy && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              <Loader2 className="mr-2 inline h-4 w-4 animate-spin" />
              {busy}
            </div>
          )}

          {activeTab === 'dashboard' && (
            <section className="space-y-4">
              <div className="grid gap-3 md:grid-cols-4">
                <Metric label="Courses" value={courses.length} icon={BookOpenCheck} />
                <Metric label="Devin Jobs" value={state?.devin_jobs.length ?? 0} icon={GitBranch} />
                <Metric label="Assets" value={state?.assets.length ?? 0} icon={FileText} />
                <Metric label="Status" value={selectedCourse?.status ?? 'none'} icon={Gauge} />
              </div>
              <Pipeline state={state} preflight={preflight} jobsByPhase={jobsByPhase} />
            </section>
          )}

          {activeTab === 'new' && (
            <section className="rounded-lg border border-neutral-200 bg-white p-4 shadow-panel">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-lg font-semibold text-ink">New Course</h2>
                <button className="focus-ring rounded-md border border-neutral-300 px-3 py-2 text-sm font-medium" onClick={() => setForm(demoCourse)}>
                  Seed Demo
                </button>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <Field label="Title" value={form.title} onChange={(value) => setForm({ ...form, title: value })} />
                <Field label="Audience" value={form.target_audience} onChange={(value) => setForm({ ...form, target_audience: value })} />
                <Field label="Language" value={form.language} onChange={(value) => setForm({ ...form, language: value })} />
                <Field label="Difficulty" value={form.difficulty} onChange={(value) => setForm({ ...form, difficulty: value })} />
                <Field
                  label="Duration"
                  type="number"
                  value={String(form.desired_duration_minutes)}
                  onChange={(value) => setForm({ ...form, desired_duration_minutes: Number(value) })}
                />
                <TextField label="Description" value={form.description} onChange={(value) => setForm({ ...form, description: value })} />
                <TextField label="Company Context" value={form.company_context} onChange={(value) => setForm({ ...form, company_context: value })} />
                <TextField
                  label="Compliance Requirements"
                  value={form.compliance_requirements}
                  onChange={(value) => setForm({ ...form, compliance_requirements: value })}
                />
                <TextField label="Source Material" value={form.source_material ?? ''} onChange={(value) => setForm({ ...form, source_material: value })} />
              </div>
              <button className="focus-ring mt-4 rounded-md bg-tealcore px-4 py-2 text-sm font-semibold text-white" onClick={submitCourse}>
                Create Course
              </button>
            </section>
          )}

          {activeTab === 'plan' && (
            <section className="space-y-4">
              {!selectedCourseId && <EmptyPanel text="Select or create a course." />}
              {selectedCourseId && !state?.plan && (
                <div className="rounded-lg border border-neutral-200 bg-white p-4 shadow-panel">
                  <h2 className="text-lg font-semibold text-ink">Plan Review</h2>
                  <button className="focus-ring mt-3 rounded-md bg-tealcore px-4 py-2 text-sm font-semibold text-white" onClick={generatePlan}>
                    Generate Plan
                  </button>
                </div>
              )}
              {state?.plan && (
                <div className="space-y-4">
                  <div className="rounded-lg border border-neutral-200 bg-white p-4 shadow-panel">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h2 className="text-lg font-semibold text-ink">Plan Review</h2>
                        <p className="mt-1 text-sm text-neutral-600">{String(state.plan.plan.course_overview.description ?? '')}</p>
                      </div>
                      <span className={`rounded-md border px-2 py-1 text-xs font-medium ${statusTone(state.plan.status)}`}>{state.plan.status}</span>
                    </div>
                    <div className="mt-4 grid gap-2">
                      {chapters.map((chapter, index) => (
                        <div key={chapter.id} className="grid gap-2 rounded-lg border border-neutral-200 p-3 md:grid-cols-[88px_1fr_110px] md:items-center">
                          <div className="flex gap-1">
                            <button className="focus-ring rounded-md border border-neutral-300 p-2" onClick={() => moveChapter(index, -1)} title="Move up">
                              <ArrowUp className="h-4 w-4" />
                            </button>
                            <button className="focus-ring rounded-md border border-neutral-300 p-2" onClick={() => moveChapter(index, 1)} title="Move down">
                              <ArrowDown className="h-4 w-4" />
                            </button>
                          </div>
                          <input
                            className="focus-ring rounded-md border border-neutral-300 px-3 py-2 text-sm"
                            value={chapter.title}
                            onChange={(event) => setChapters(chapters.map((item) => (item.id === chapter.id ? { ...item, title: event.target.value } : item)))}
                          />
                          <input
                            className="focus-ring rounded-md border border-neutral-300 px-3 py-2 text-sm"
                            type="number"
                            min={1}
                            value={chapter.duration_minutes}
                            onChange={(event) =>
                              setChapters(chapters.map((item) => (item.id === chapter.id ? { ...item, duration_minutes: Number(event.target.value) } : item)))
                            }
                          />
                        </div>
                      ))}
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <button className="focus-ring rounded-md border border-neutral-300 px-4 py-2 text-sm font-semibold" onClick={generatePlan}>
                        Regenerate
                      </button>
                      <button className="focus-ring rounded-md bg-tealcore px-4 py-2 text-sm font-semibold text-white" onClick={approve}>
                        <Play className="mr-1 inline h-4 w-4" /> Approve
                      </button>
                    </div>
                  </div>
                  <JsonBlock value={state.plan.plan} />
                </div>
              )}
            </section>
          )}

          {activeTab === 'pipeline' && <Pipeline state={state} preflight={preflight} jobsByPhase={jobsByPhase} />}

          {activeTab === 'evidence' && <Evidence state={state} />}

          {activeTab === 'preview' && (
            <section className="rounded-lg border border-neutral-200 bg-white p-4 shadow-panel">
              <h2 className="text-lg font-semibold text-ink">Generated Course Preview</h2>
              {state?.hosted_output ? (
                <div className="mt-3 space-y-3">
                  <div className="grid gap-2 text-sm md:grid-cols-2">
                    <a className="rounded-md border border-neutral-200 p-3 text-tealcore" href={state.hosted_output.course_url} target="_blank" rel="noreferrer">
                      {state.hosted_output.course_url}
                    </a>
                    <a className="rounded-md border border-neutral-200 p-3 text-tealcore" href={state.hosted_output.iframe_url} target="_blank" rel="noreferrer">
                      {state.hosted_output.iframe_url}
                    </a>
                  </div>
                  <iframe title="Generated course" src={state.hosted_output.iframe_url} className="h-[520px] w-full rounded-md border border-neutral-300" />
                </div>
              ) : (
                <EmptyPanel text="Hosting output appears after the Devin QA phase completes." />
              )}
            </section>
          )}

          {activeTab === 'reporting' && <Reporting state={state} />}

          {activeTab === 'setup' && (
            <section className="space-y-4">
              <div className="rounded-lg border border-neutral-200 bg-white p-4 shadow-panel">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 className="text-lg font-semibold text-ink">Devin Preflight</h2>
                  <button className="focus-ring rounded-md bg-tealcore px-3 py-2 text-sm font-semibold text-white" onClick={() => withBusy('preflight', async () => setPreflight(await api.preflight(true)))}>
                    Run Prepare Check
                  </button>
                </div>
                <div className={`mt-3 rounded-md border p-3 text-sm ${statusTone(preflight?.ok ? 'ok' : 'failed')}`}>
                  {preflight?.ok ? 'Real Devin path is ready.' : preflight?.error ?? 'Preflight has not passed.'}
                </div>
              </div>
              <JsonBlock value={preflight ?? {}} />
            </section>
          )}
        </main>
      </div>
    </div>
  )
}

function Field({ label, value, onChange, type = 'text' }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return (
    <label className="grid gap-1 text-sm font-medium text-neutral-700">
      {label}
      <input className="focus-ring rounded-md border border-neutral-300 px-3 py-2 font-normal" type={type} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  )
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="grid gap-1 text-sm font-medium text-neutral-700 md:col-span-2">
      {label}
      <textarea className="focus-ring min-h-24 rounded-md border border-neutral-300 px-3 py-2 font-normal" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  )
}

function Pipeline({
  state,
  preflight,
  jobsByPhase
}: {
  state: CourseState | null
  preflight: PreflightResult | null
  jobsByPhase: Map<string, CourseState['devin_jobs'][number]>
}) {
  const phaseStatus = (phase: string) => {
    if (phase === 'Course Request') return state?.course ? 'completed' : 'pending'
    if (phase === 'Course Planner') return state?.plan ? 'completed' : 'pending'
    if (phase === 'Approval') return state?.course.approved_at ? 'completed' : 'blocked'
    if (phase === 'Lastenheft') return state?.spec ? 'completed' : 'pending'
    if (phase === 'Asset Manifest') return state?.assets.length ? 'completed' : 'pending'
    if (phase === 'Asset Fetching') return state?.assets.some((asset) => asset.status === 'ready') ? 'completed' : 'pending'
    if (phase === 'Hosting Output') return state?.hosted_output ? 'completed' : 'pending'
    if (phase === 'LMS Reporting') return state?.course ? 'ready' : 'pending'
    if (phase === 'Evidence Ledger') return state?.prompts.length || state?.devin_jobs.length ? 'ready' : 'pending'
    const key = phase === 'Devin Implementation' ? 'implementation' : phase === 'Devin Asset Integration' ? 'asset_integration' : phase === 'Devin QA' ? 'qa' : ''
    return jobsByPhase.get(key)?.status ?? 'pending'
  }
  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-4 shadow-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ink">Autonomous Pipeline</h2>
          <p className="mt-1 text-sm text-neutral-600">{state?.course.title ?? 'No active course'}</p>
        </div>
        <span className={`rounded-md border px-2 py-1 text-xs font-medium ${statusTone(preflight?.ok ? 'ok' : 'failed')}`}>Devin {preflight?.ok ? 'ready' : 'blocked'}</span>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {phaseOrder.map((phase) => {
          const key = phase === 'Devin Implementation' ? 'implementation' : phase === 'Devin Asset Integration' ? 'asset_integration' : phase === 'Devin QA' ? 'qa' : ''
          const job = key ? jobsByPhase.get(key) : undefined
          const status = phaseStatus(phase)
          return (
            <div key={phase} className="rounded-lg border border-neutral-200 p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h3 className="truncate text-sm font-semibold text-ink">{phase}</h3>
                  <p className="mt-1 text-xs text-neutral-500">{job?.devin_session_id ?? compactDate(job?.updated_at)}</p>
                </div>
                <span className={`shrink-0 rounded-md border px-2 py-1 text-xs font-medium ${statusTone(status)}`}>{status}</span>
              </div>
              {job?.branch && <p className="mt-2 truncate text-xs text-neutral-600">{job.branch}</p>}
              {job?.commit_sha && <p className="mt-1 truncate text-xs font-mono text-neutral-600">{job.commit_sha}</p>}
            </div>
          )
        })}
      </div>
    </section>
  )
}

function Evidence({ state }: { state: CourseState | null }) {
  if (!state) return <EmptyPanel text="Select a course to view the ledger." />
  return (
    <section className="space-y-4">
      <div className="rounded-lg border border-neutral-200 bg-white p-4 shadow-panel">
        <h2 className="text-lg font-semibold text-ink">Evidence Ledger</h2>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <Metric label="Real Sessions" value={state.devin_jobs.filter((job) => job.devin_session_id).length} icon={GitBranch} />
          <Metric label="Prompts" value={state.prompts.length} icon={FileText} />
          <Metric label="Events" value={state.devin_events.length} icon={Database} />
        </div>
      </div>
      <LedgerSection title="Course Request" value={state.course} />
      <LedgerSection title="Approved Plan" value={state.plan?.plan ?? null} />
      <LedgerSection title="Lastenheft / Spec" value={state.spec ?? null} />
      <LedgerSection title="Assets" value={state.assets} />
      <LedgerSection title="Generated Devin Prompts" value={state.prompts} />
      <LedgerSection title="Devin Jobs" value={state.devin_jobs} />
      <LedgerSection title="Status Events" value={state.devin_events} />
      <LedgerSection title="QA Results" value={state.qa_results} />
      <LedgerSection title="Hosting Output" value={state.hosted_output ?? null} />
    </section>
  )
}

function LedgerSection({ title, value }: { title: string; value: unknown }) {
  return (
    <details open className="rounded-lg border border-neutral-200 bg-white p-4 shadow-panel">
      <summary className="cursor-pointer text-sm font-semibold text-ink">{title}</summary>
      <div className="mt-3">
        <JsonBlock value={value} />
      </div>
    </details>
  )
}

function Reporting({ state }: { state: CourseState | null }) {
  const reporting = state?.reporting as
    | {
        assigned_courses?: number
        open_courses?: number
        completed_courses?: number
        average_score?: number
        compliance_status?: string
        team_progress?: Array<Record<string, unknown>>
      }
    | undefined
  if (!state) return <EmptyPanel text="Select a course to view reporting." />
  return (
    <section className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <Metric label="Assigned" value={reporting?.assigned_courses ?? 0} icon={Users} />
        <Metric label="Open" value={reporting?.open_courses ?? 0} icon={Gauge} />
        <Metric label="Completed" value={reporting?.completed_courses ?? 0} icon={BadgeCheck} />
        <Metric label="Avg Score" value={reporting?.average_score ?? 0} icon={ClipboardCheck} />
      </div>
      <div className="rounded-lg border border-neutral-200 bg-white p-4 shadow-panel">
        <h2 className="text-lg font-semibold text-ink">Manager Reporting</h2>
        <div className={`mt-3 inline-flex rounded-md border px-2 py-1 text-xs font-medium ${statusTone(reporting?.compliance_status)}`}>{reporting?.compliance_status ?? 'pending'}</div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-neutral-200 text-left text-xs uppercase text-neutral-500">
                <th className="py-2">Learner</th>
                <th>Role</th>
                <th>Progress</th>
                <th>Score</th>
                <th>Certification</th>
              </tr>
            </thead>
            <tbody>
              {(reporting?.team_progress ?? []).map((item) => {
                const progress = item.progress as Record<string, unknown>
                const quiz = (progress.quiz_results as Array<Record<string, unknown>>)?.[0] ?? {}
                return (
                  <tr key={String(item.id)} className="border-b border-neutral-100">
                    <td className="py-2 font-medium text-ink">{String(item.learner_name)}</td>
                    <td>{String(item.role)}</td>
                    <td>{String(progress.course_progress_percent)}%</td>
                    <td>{String(quiz.score ?? 'n/a')}</td>
                    <td>{String(progress.certification_status)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
