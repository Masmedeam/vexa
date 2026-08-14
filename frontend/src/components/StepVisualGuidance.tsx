import { Search } from "lucide-react"
import { useEffect, useState } from "react"

type Step = { id: string; step_number: number; action: string }
type Reference = { id: string; title: string; source_url: string; image_url?: string | null; snippet?: string | null; publisher?: string | null }

async function readResponse(response: Response) {
  const text = await response.text()
  try { return JSON.parse(text) } catch { return { detail: text || "Visual guidance request failed" } }
}

export function StepVisualGuidance({ projectId, caseId, steps }: { projectId: string; caseId: string; steps: Step[] }) {
  const [references, setReferences] = useState<Reference[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  async function load() {
    const token = localStorage.getItem("access_token")
    const response = await fetch(`/api/v1/projects/${projectId}/visuals?case_id=${caseId}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    if (response.ok) setReferences(await readResponse(response))
  }
  useEffect(() => { void load() }, [projectId, caseId])
  async function search() {
    setBusy(true); setError("")
    try {
      const token = localStorage.getItem("access_token")
      const query = steps.map((step) => `Step ${step.step_number}: ${step.action}`).join("\n")
      const response = await fetch(`/api/v1/projects/${projectId}/visuals/search`, { method: "POST", headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: JSON.stringify({ case_id: caseId, query }) })
      const data = await readResponse(response)
      if (!response.ok) throw new Error(data.detail || "Visual guidance search failed")
      setReferences(data.references || [])
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Visual guidance search failed") } finally { setBusy(false) }
  }
  return <section className="grid gap-3 rounded-lg border border-border bg-card p-4"><div><h2 className="font-medium">Visual guidance</h2><p className="mt-1 text-sm text-muted-foreground">Find verified reference images and tutorial pages for this test case. These references guide the operator and are not acceptance evidence.</p></div><button type="button" disabled={busy || !steps.length} onClick={() => void search()} className="inline-flex w-fit items-center gap-2 rounded-md bg-foreground px-3 py-2 text-sm text-background disabled:opacity-50"><Search className="size-4" />{busy ? "Finding guidance…" : references.length ? "Refresh visual guidance" : "Find visual guidance"}</button>{error && <p className="text-sm text-destructive" role="alert">{error}</p>}{references.length > 0 && <div className="grid gap-3 sm:grid-cols-3">{references.map((item) => <article key={item.id} className="overflow-hidden rounded-md border border-border">{item.image_url && <img src={item.image_url} alt="" className="h-32 w-full object-cover" loading="lazy" referrerPolicy="no-referrer" />}<div className="grid gap-1 p-3"><a href={item.source_url} target="_blank" rel="noreferrer" className="text-sm font-medium hover:underline">{item.title}</a><p className="text-xs text-muted-foreground">{item.publisher || "Verified web source"}</p>{item.snippet && <p className="text-xs text-muted-foreground">{item.snippet}</p>}</div></article>)}</div>}</section>
}
