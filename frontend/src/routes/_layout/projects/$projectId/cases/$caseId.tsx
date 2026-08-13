import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft, Check, Paperclip, Play, X } from "lucide-react"
import { useEffect, useState, type ChangeEvent } from "react"

export const Route = createFileRoute("/_layout/projects/$projectId/cases/$caseId")({
  component: TestCaseExecutionPage,
  head: () => ({ meta: [{ title: "Test case - Vexa" }] }),
})

type Case = { id: string; test_case_id: string; title: string; payload: Record<string, any> }
type Step = { id: string; step_number: number; action: string; expected_result: string; evidence_required: string; status: string; observed_result?: string | null }
type Execution = { id: string; status: string; observed_result?: string | null; deviation_reference?: string | null }
type Review = { id: string; status: string; comment?: string | null }

async function request(path: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers); const token = localStorage.getItem("access_token")
  if (token) headers.set("Authorization", `Bearer ${token}`)
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json")
  const response = await fetch(`/api/v1${path}`, { ...options, headers })
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || "Request failed")
  return response.json()
}

function TestCaseExecutionPage() {
  const { projectId, caseId } = Route.useParams()
  const [testCase, setTestCase] = useState<Case | null>(null)
  const [steps, setSteps] = useState<Step[]>([])
  const [executions, setExecutions] = useState<Record<string, Execution>>({})
  const [reviews, setReviews] = useState<Review[]>([])
  const [comment, setComment] = useState("")
  const [results, setResults] = useState<Record<string, string>>({})
  const [editingSteps, setEditingSteps] = useState<Record<string, boolean>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")

  async function load() {
    try {
      const [caseResult, stepResult, reviewResult] = await Promise.all([request(`/projects/${projectId}/test-cases/${caseId}`), request(`/projects/${projectId}/test-cases/${caseId}/steps`), request(`/projects/${projectId}/test-cases/${caseId}/reviews`)]); setTestCase(caseResult); setSteps(stepResult); setReviews(reviewResult)
      const executionPairs = await Promise.all(stepResult.map(async (step: Step) => [step.id, (await request(`/projects/${projectId}/test-cases/${caseId}/steps/${step.id}/executions`))[0]] as const))
      setExecutions(Object.fromEntries(executionPairs.filter(([, execution]) => execution)))
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to load test case") }
  }

  async function saveReview(status: string) {
    setBusy(true); setError(""); setNotice("")
    try { await request(`/projects/${projectId}/test-cases/${caseId}/reviews`, { method: "POST", body: JSON.stringify({ status, comment: comment || null }) }); setComment(""); await load(); setNotice(`Review marked ${status.replace("_", " ")}`) }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to save review") } finally { setBusy(false) }
  }
  useEffect(() => { void load() }, [projectId, caseId])

  async function start(step: Step) {
    setBusy(true); setError("")
    try { const execution = await request(`/projects/${projectId}/test-cases/${caseId}/steps/${step.id}/executions`, { method: "POST" }); setExecutions((current) => ({ ...current, [step.id]: execution })); setSteps((current) => current.map((item) => item.id === step.id ? { ...item, status: "in_progress" } : item)); setNotice(`Step ${step.step_number} started`) }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to start step") } finally { setBusy(false) }
  }

  async function finish(step: Step, status: "passed" | "failed") {
    const execution = executions[step.id]; if (!execution) return
    setBusy(true); setError("")
    try { const updated = await request(`/projects/${projectId}/test-cases/${caseId}/steps/${step.id}/executions/${execution.id}`, { method: "PATCH", body: JSON.stringify({ status, observed_result: results[step.id] || null }) }); setExecutions((current) => ({ ...current, [step.id]: updated })); setSteps((current) => current.map((item) => item.id === step.id ? { ...item, status: status === "passed" ? "completed" : "blocked", observed_result: results[step.id] } : item)); setEditingSteps((current) => ({ ...current, [step.id]: false })); setNotice(`Step ${step.step_number} marked ${status}`) }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to save step") } finally { setBusy(false) }
  }

  async function evidence(step: Step, event: ChangeEvent<HTMLInputElement>) {
    const execution = executions[step.id]; const file = event.target.files?.[0]; if (!execution || !file) return
    const body = new FormData(); body.append("evidence_type", step.evidence_required); body.append("file", file); setBusy(true); setError("")
    try { await request(`/projects/${projectId}/test-cases/${caseId}/steps/${step.id}/executions/${execution.id}/evidence`, { method: "POST", body }); setNotice(`Evidence added to step ${step.step_number}`) }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to upload evidence") } finally { setBusy(false); event.target.value = "" }
  }

  if (!testCase) return <p className="text-sm text-muted-foreground">{error || "Loading test case…"}</p>
  const payload = testCase.payload
  const completed = steps.filter((step) => step.status === "completed").length
  const editing = (step: Step) => editingSteps[step.id] || !executions[step.id] || !["completed", "blocked"].includes(step.status)
  return <div className="mx-auto flex max-w-6xl flex-col gap-5">
    <Link to="/projects/$projectId" params={{ projectId }} className="inline-flex w-fit items-center gap-2 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="size-4" /> Back to workflow</Link>
    <header className="border-b border-border pb-5"><p className="text-sm text-muted-foreground">{testCase.test_case_id} · {payload.qualification_stage || "Test case"}</p><h1 className="mt-1 text-2xl font-semibold tracking-tight">{testCase.title}</h1><p className="mt-2 max-w-3xl text-sm text-muted-foreground">{payload.objective}</p><p className="mt-4 text-xs text-muted-foreground">{completed} of {steps.length} steps completed</p></header>
    {error && <p className="text-sm text-destructive" role="alert">{error}</p>}{notice && <p className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-300" role="status">{notice}</p>}
    <section className="overflow-hidden rounded-lg border border-border bg-card"><div className="divide-y divide-border">{steps.map((step) => { const execution = executions[step.id]; const isEditing = editing(step); return <article key={step.id} className={`grid gap-4 p-5 transition-colors ${step.status === "completed" ? "bg-emerald-500/5" : step.status === "blocked" ? "bg-red-500/5" : ""} lg:grid-cols-[42px_minmax(0,1fr)_260px]`}><div className={`flex size-8 items-center justify-center rounded-full border text-sm ${step.status === "completed" ? "border-emerald-500/50 text-emerald-600" : step.status === "blocked" ? "border-red-500/50 text-red-600" : "border-border"}`}>{step.status === "completed" ? <Check className="size-4" /> : step.status === "blocked" ? <X className="size-4" /> : step.step_number}</div><div className="grid gap-3"><div><p className="text-xs text-muted-foreground">Step {step.step_number} · <span className={step.status === "completed" ? "text-emerald-600" : step.status === "blocked" ? "text-red-600" : ""}>{step.status.replace("_", " ")}</span></p><p className="mt-1 font-medium">{step.action}</p></div><div className="rounded-md bg-muted/50 p-3 text-sm"><p className="font-medium">Expected result</p><p className="mt-1 text-muted-foreground">{step.expected_result}</p></div><p className="text-xs text-muted-foreground">Evidence: {step.evidence_required}</p>{!isEditing && execution?.observed_result && <div className="rounded-md border border-border bg-background p-3 text-sm"><p className="font-medium">Recorded result</p><p className="mt-1 text-muted-foreground">{execution.observed_result}</p></div>}</div><div className="grid content-start gap-2">{!execution ? <button type="button" disabled={busy} onClick={() => start(step)} className="inline-flex items-center justify-center gap-2 rounded-md border border-border px-3 py-2 text-sm hover:bg-muted"><Play className="size-4" />Start step</button> : isEditing ? <><textarea value={results[step.id] ?? execution.observed_result ?? ""} onChange={(event) => setResults((current) => ({ ...current, [step.id]: event.target.value }))} placeholder="Observed result or comment" className="min-h-24 rounded-md border border-border bg-background p-2 text-sm" /><div className="flex gap-2"><button type="button" disabled={busy} onClick={() => finish(step, "passed")} className="flex-1 rounded-md bg-emerald-600 px-2 py-2 text-xs text-white hover:bg-emerald-700">Pass</button><button type="button" disabled={busy} onClick={() => finish(step, "failed")} className="flex-1 rounded-md bg-red-600 px-2 py-2 text-xs text-white hover:bg-red-700">Fail</button><label className="flex cursor-pointer items-center justify-center rounded-md border border-border px-2 py-2 hover:bg-muted"><Paperclip className="size-4" /><input type="file" className="sr-only" disabled={busy} onChange={(event) => evidence(step, event)} /></label></div></> : <><p className={`text-sm ${step.status === "completed" ? "text-emerald-600" : "text-red-600"}`}>{step.status === "completed" ? "Step passed" : "Step failed"}</p><div className="flex gap-2"><button type="button" disabled={busy} onClick={() => setEditingSteps((current) => ({ ...current, [step.id]: true }))} className="rounded-md border border-border px-2 py-1 text-xs hover:bg-muted">Edit result</button><label className="flex cursor-pointer items-center rounded-md border border-border px-2 py-1 hover:bg-muted"><Paperclip className="size-3" /><input type="file" className="sr-only" disabled={busy} onChange={(event) => evidence(step, event)} /></label></div></>}</div></article> })}</div></section>
    <section className="grid gap-3 rounded-lg border border-border bg-card p-4"><div><h2 className="font-medium">Review</h2><p className="mt-1 text-sm text-muted-foreground">Review approves or rejects the generated test case before execution. It does not record execution results.</p><p className="mt-1 text-sm text-muted-foreground">{reviews[0] ? `Latest review: ${reviews[0].status}` : "This test case has not been reviewed."}</p><textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Review comment" className="mt-3 min-h-16 w-full rounded-md border border-border bg-background p-2 text-sm" /></div><div className="flex flex-wrap gap-2"><button type="button" disabled={busy} onClick={() => saveReview("approved")} className="rounded-md border border-border px-3 py-2 text-xs hover:bg-muted">Approve</button><button type="button" disabled={busy} onClick={() => saveReview("needs_changes")} className="rounded-md border border-border px-3 py-2 text-xs hover:bg-muted">Needs changes</button><button type="button" disabled={busy} onClick={() => saveReview("rejected")} className="rounded-md border border-border px-3 py-2 text-xs hover:bg-muted">Reject</button></div></section>
  </div>
}
