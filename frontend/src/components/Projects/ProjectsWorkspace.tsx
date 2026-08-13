import { Link } from "@tanstack/react-router"
import { FolderPlus } from "lucide-react"
import { useEffect, useState, type FormEvent } from "react"

type Project = { id: string; name: string; description?: string | null; created_at?: string | null }

async function request(path: string, options: RequestInit = {}) {
  const token = localStorage.getItem("access_token")
  const headers = new Headers(options.headers)
  if (token) headers.set("Authorization", `Bearer ${token}`)
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json")
  const response = await fetch(`/api/v1${path}`, { ...options, headers })
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || "Request failed")
  return response.json()
}

export function ProjectsWorkspace({ compact = false }: { compact?: boolean }) {
  const [projects, setProjects] = useState<Project[]>([])
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [showCreate, setShowCreate] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  async function load() {
    try {
      const result = await request("/projects/")
      setProjects(result.data)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load projects")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  async function createProject(event: FormEvent) {
    event.preventDefault()
    if (!name.trim()) return
    setSaving(true)
    setError("")
    try {
      const project = await request("/projects/", { method: "POST", body: JSON.stringify({ name, description: description || null }) })
      setProjects((current) => [project, ...current])
      setName("")
      setDescription("")
      setShowCreate(false)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create project")
    } finally {
      setSaving(false)
    }
  }

  return <div className="flex flex-col gap-7">
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div><h1 className="text-2xl font-semibold tracking-tight">{compact ? "Recent projects" : "Projects"}</h1><p className="text-muted-foreground">Create a project, add its source documents, and move through qualification stages in order.</p></div>
      <button className="inline-flex items-center gap-2 rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background" onClick={() => setShowCreate((value) => !value)}><FolderPlus className="size-4" /> New project</button>
    </div>
    {showCreate && <form onSubmit={createProject} className="max-w-xl rounded-lg border bg-card p-5"><h2 className="font-medium">New project</h2><div className="mt-4 grid gap-3"><input className="rounded-md border bg-background px-3 py-2 text-sm" placeholder="Project name" value={name} onChange={(event) => setName(event.target.value)} autoFocus /><textarea className="min-h-20 rounded-md border bg-background px-3 py-2 text-sm" placeholder="Description (optional)" value={description} onChange={(event) => setDescription(event.target.value)} /><button className="w-fit rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background disabled:opacity-50" disabled={saving || !name.trim()}>{saving ? "Creating…" : "Create project"}</button></div></form>}
    {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
    {loading ? <p className="text-sm text-muted-foreground">Loading projects…</p> : projects.length === 0 ? <div className="rounded-lg border border-dashed p-10 text-center"><h2 className="font-medium">No projects yet</h2><p className="mt-1 text-sm text-muted-foreground">Create your first project to begin a qualification workflow.</p></div> : <div className="grid gap-4 md:grid-cols-2">{projects.slice(0, compact ? 4 : undefined).map((project) => <Link key={project.id} to="/projects/$projectId" params={{ projectId: project.id }} className="rounded-lg border bg-card p-5 transition-colors hover:bg-muted/40"><h2 className="font-medium">{project.name}</h2><p className="mt-2 line-clamp-2 text-sm text-muted-foreground">{project.description || "No description"}</p><p className="mt-5 text-xs text-muted-foreground">Open workflow →</p></Link>)}</div>}
  </div>
}
