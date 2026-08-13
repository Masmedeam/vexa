import { Mic, Square } from "lucide-react"
import { useRef, useState } from "react"

type VoiceStep = { id: string; step_number: number; action: string; status: string; case_id: string; case_title: string }
type VisualReference = { id: string; title: string; source_url: string; image_url?: string | null; publisher?: string | null }
type CaseContext = { id: string; title: string }
type Props = { projectId: string; stage: string; cases: CaseContext[]; onChanged?: () => void }

async function request(path: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers); const token = localStorage.getItem("access_token")
  if (token) headers.set("Authorization", `Bearer ${token}`)
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json")
  const response = await fetch(`/api/v1${path}`, { ...options, headers })
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || "Voice action failed")
  return response.json()
}

export function VoiceAssistant({ projectId, stage, cases, onChanged }: Props) {
  const [status, setStatus] = useState<"idle" | "connecting" | "connected" | "working" | "error">("idle")
  const [message, setMessage] = useState(""); const [visuals, setVisuals] = useState<VisualReference[]>([])
  const pcRef = useRef<RTCPeerConnection | null>(null); const dcRef = useRef<RTCDataChannel | null>(null); const streamRef = useRef<MediaStream | null>(null)
  function send(event: Record<string, unknown>) { if (dcRef.current?.readyState === "open") dcRef.current.send(JSON.stringify(event)) }
  function stop() { dcRef.current?.close(); pcRef.current?.close(); streamRef.current?.getTracks().forEach((track) => track.stop()); dcRef.current = null; pcRef.current = null; streamRef.current = null; setStatus("idle"); setMessage("") }
  async function executeTool(name: string, args: Record<string, any>) {
    setStatus("working"); setMessage(`Updating ${name.replace(/_/g, " ")}…`); const caseId = args.case_id
    if (name === "start_step") { const result = await request(`/projects/${projectId}/test-cases/${caseId}/steps/${args.step_id}/executions`, { method: "POST" }); onChanged?.(); return result }
    if (name === "record_step_result") { const executions = await request(`/projects/${projectId}/test-cases/${caseId}/steps/${args.step_id}/executions`); const execution = executions[0] || await request(`/projects/${projectId}/test-cases/${caseId}/steps/${args.step_id}/executions`, { method: "POST" }); const result = await request(`/projects/${projectId}/test-cases/${caseId}/steps/${args.step_id}/executions/${execution.id}`, { method: "PATCH", body: JSON.stringify({ status: args.status, observed_result: args.observed_result, deviation_reference: args.deviation_reference || null }) }); onChanged?.(); return result }
    if (name === "review_case") { const result = await request(`/projects/${projectId}/test-cases/${caseId}/reviews`, { method: "POST", body: JSON.stringify({ status: args.status, comment: args.comment || null }) }); onChanged?.(); return result }
    if (name === "complete_stage") { const result = await request(`/projects/${projectId}/steps/${args.step_id}`, { method: "PATCH", body: JSON.stringify({ status: "completed" }) }); onChanged?.(); return result }
    if (name === "search_step_visuals") return request(`/projects/${projectId}/visuals/search`, { method: "POST", body: JSON.stringify({ case_id: caseId, step_id: args.step_id, query: args.query }) })
    throw new Error("Unknown voice function")
  }
  async function handleEvent(event: any) {
    if (event.type !== "response.function_call_arguments.done") return
    try { const result = await executeTool(event.name, JSON.parse(event.arguments || "{}")); if (event.name === "search_step_visuals") setVisuals(result.references || []); send({ type: "conversation.item.create", item: { type: "function_call_output", call_id: event.call_id, output: JSON.stringify({ ok: true, result }) } }); send({ type: "response.create" }); setStatus("connected"); setMessage("Action completed") }
    catch (error) { const detail = error instanceof Error ? error.message : "Action failed"; send({ type: "conversation.item.create", item: { type: "function_call_output", call_id: event.call_id, output: JSON.stringify({ ok: false, error: detail }) } }); send({ type: "response.create" }); setStatus("connected"); setMessage(detail) }
  }
  async function start() {
    setStatus("connecting"); setMessage("Connecting…")
    try {
      const stepGroups = await Promise.all(cases.map(async (item) => ({ item, steps: await request(`/projects/${projectId}/test-cases/${item.id}/steps`) }))); const steps: VoiceStep[] = stepGroups.flatMap(({ item, steps: records }) => records.map((step: Omit<VoiceStep, "case_id" | "case_title">) => ({ ...step, case_id: item.id, case_title: item.title })))
      const pc = new RTCPeerConnection(); pcRef.current = pc; const audio = new Audio(); audio.autoplay = true; pc.ontrack = (event) => { audio.srcObject = event.streams[0] }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true }); streamRef.current = stream; stream.getTracks().forEach((track) => pc.addTrack(track, stream)); const dc = pc.createDataChannel("oai-events"); dcRef.current = dc; dc.onmessage = (event) => { void handleEvent(JSON.parse(event.data)) }; dc.onopen = () => { setStatus("connected"); setMessage("Listening") }
      const offer = await pc.createOffer(); await pc.setLocalDescription(offer); const token = localStorage.getItem("access_token"); const context = JSON.stringify({ project_id: projectId, stage, steps }); const response = await fetch("/api/v1/realtime/session", { method: "POST", body: offer.sdp, headers: { "Content-Type": "application/sdp", "X-Voice-Context": context, ...(token ? { Authorization: `Bearer ${token}` } : {}) } }); if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || "Unable to start voice"); await pc.setRemoteDescription({ type: "answer", sdp: await response.text() })
    } catch (error) { stop(); setStatus("error"); setMessage(error instanceof Error ? error.message : "Unable to start voice") }
  }
  const active = status !== "idle" && status !== "error"
  return <div className="grid justify-items-end gap-2"><div className="flex items-center gap-2"><button type="button" onClick={active ? stop : () => void start()} className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs ${active ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : "border-border hover:bg-muted"}`} aria-label={active ? "Stop voice assistant" : "Start voice assistant"}>{active ? <Square className="size-3.5" /> : <Mic className="size-3.5" />}{status === "connecting" ? "Connecting" : status === "working" ? "Updating" : active ? "Listening" : "Voice"}</button>{message && <span className="max-w-40 truncate text-[11px] text-muted-foreground" role="status">{message}</span>}</div>{visuals.length > 0 && <div className="grid max-w-xl gap-2 sm:grid-cols-3">{visuals.map((item) => <a key={item.id} href={item.source_url} target="_blank" rel="noreferrer" className="overflow-hidden rounded-md border border-border text-xs hover:bg-muted">{item.image_url && <img src={item.image_url} alt="" className="h-20 w-full object-cover" loading="lazy" referrerPolicy="no-referrer" />}<span className="block p-2">{item.title}<span className="mt-1 block text-muted-foreground">{item.publisher || "Source"}</span></span></a>)}</div>}</div>
}
