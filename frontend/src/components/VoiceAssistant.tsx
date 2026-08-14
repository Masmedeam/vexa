import { Mic, Pause, Play, Square } from "lucide-react"
import { useEffect, useRef, useState } from "react"

type VisualReference = { id: string; title: string; source_url: string; image_url?: string | null; publisher?: string | null }
type VoiceStatus = "idle" | "connecting" | "listening" | "paused" | "working" | "error"
type Props = { projectId: string }

async function request(path: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers)
  const token = localStorage.getItem("access_token")
  if (token) headers.set("Authorization", `Bearer ${token}`)
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json")
  const response = await fetch(`/api/v1${path}`, { ...options, headers })
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || "Voice action failed")
  return response.json()
}

export function VoiceAssistant({ projectId }: Props) {
  const [status, setStatus] = useState<VoiceStatus>("idle")
  const [message, setMessage] = useState("")
  const [visuals, setVisuals] = useState<VisualReference[]>([])
  const pcRef = useRef<RTCPeerConnection | null>(null)
  const dcRef = useRef<RTCDataChannel | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const stoppingRef = useRef(false)

  function publishChanged() {
    window.dispatchEvent(new CustomEvent("vexa:voice-updated", { detail: { projectId } }))
  }

  function send(event: Record<string, unknown>) {
    if (dcRef.current?.readyState === "open") dcRef.current.send(JSON.stringify(event))
  }

  function stop() {
    stoppingRef.current = true
    dcRef.current?.close()
    pcRef.current?.close()
    streamRef.current?.getTracks().forEach((track) => track.stop())
    dcRef.current = null
    pcRef.current = null
    streamRef.current = null
    setStatus("idle")
    setMessage("")
  }

  function pause() {
    streamRef.current?.getAudioTracks().forEach((track) => { track.enabled = false })
    setStatus("paused")
    setMessage("Microphone paused")
  }

  function resume() {
    streamRef.current?.getAudioTracks().forEach((track) => { track.enabled = true })
    setStatus("listening")
    setMessage("Listening")
  }

  async function executeTool(name: string, args: Record<string, any>) {
    setStatus("working")
    setMessage(`Updating ${name.replace(/_/g, " ")}…`)
    const caseId = args.case_id
    if (name === "start_step") return request(`/projects/${projectId}/test-cases/${caseId}/steps/${args.step_id}/executions`, { method: "POST" })
    if (name === "record_step_result") {
      const executions = await request(`/projects/${projectId}/test-cases/${caseId}/steps/${args.step_id}/executions`)
      const execution = executions[0] || await request(`/projects/${projectId}/test-cases/${caseId}/steps/${args.step_id}/executions`, { method: "POST" })
      return request(`/projects/${projectId}/test-cases/${caseId}/steps/${args.step_id}/executions/${execution.id}`, { method: "PATCH", body: JSON.stringify({ status: args.status, observed_result: args.observed_result, deviation_reference: args.deviation_reference || null }) })
    }
    if (name === "review_case") return request(`/projects/${projectId}/test-cases/${caseId}/reviews`, { method: "POST", body: JSON.stringify({ status: args.status, comment: args.comment || null }) })
    if (name === "complete_stage") return request(`/projects/${projectId}/steps/${args.step_id}`, { method: "PATCH", body: JSON.stringify({ status: "completed" }) })
    if (name === "search_step_visuals") return request(`/projects/${projectId}/visuals/search`, { method: "POST", body: JSON.stringify({ case_id: caseId, step_id: args.step_id, query: args.query }) })
    throw new Error("Unknown voice function")
  }

  async function handleEvent(event: any) {
    if (event.type === "error") {
      setStatus("error")
      setMessage(event.error?.message || "Voice service reported an error")
      return
    }
    if (event.type === "input_audio_buffer.speech_started") {
      setMessage("Listening")
      return
    }
    if (event.type !== "response.function_call_arguments.done") return
    try {
      const result = await executeTool(event.name, JSON.parse(event.arguments || "{}"))
      if (event.name === "search_step_visuals") setVisuals(result.references || [])
      else publishChanged()
      send({ type: "conversation.item.create", item: { type: "function_call_output", call_id: event.call_id, output: JSON.stringify({ ok: true, result }) } })
      send({ type: "response.create" })
      setStatus("listening")
      setMessage("Listening · action completed")
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Action failed"
      send({ type: "conversation.item.create", item: { type: "function_call_output", call_id: event.call_id, output: JSON.stringify({ ok: false, error: detail }) } })
      send({ type: "response.create" })
      setStatus("listening")
      setMessage(detail)
    }
  }

  async function start() {
    stoppingRef.current = false
    setStatus("connecting")
    setMessage("Connecting to voice…")
    try {
      const pc = new RTCPeerConnection()
      pcRef.current = pc
      const audio = new Audio()
      audio.autoplay = true
      pc.ontrack = (event) => { audio.srcObject = event.streams[0] }
      pc.onconnectionstatechange = () => {
        if (pc.connectionState === "connected") { setStatus("listening"); setMessage("Listening") }
        if (["failed", "disconnected", "closed"].includes(pc.connectionState)) { setStatus("error"); setMessage(`Voice connection ${pc.connectionState}`) }
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      stream.getTracks().forEach((track) => pc.addTrack(track, stream))
      const dc = pc.createDataChannel("oai-events")
      dcRef.current = dc
      dc.onmessage = (event) => { void handleEvent(JSON.parse(event.data)) }
      dc.onopen = () => { setStatus("listening"); setMessage("Listening") }
      dc.onerror = () => { setStatus("error"); setMessage("Voice data channel failed") }
      dc.onclose = () => { if (!stoppingRef.current) { setStatus("error"); setMessage("Voice data channel closed") } }
      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)
      const token = localStorage.getItem("access_token")
      const response = await fetch("/api/v1/realtime/session", { method: "POST", body: JSON.stringify({ sdp: offer.sdp, project_id: projectId }), headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) } })
      if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || "Unable to start voice")
      const answerSdp = await response.text()
      if (!answerSdp.trimStart().startsWith("v=0")) throw new Error("Voice server returned an invalid SDP answer")
      await pc.setRemoteDescription({ type: "answer", sdp: answerSdp })
    } catch (error) {
      stop()
      setStatus("error")
      setMessage(error instanceof Error ? error.message : "Unable to start voice")
    }
  }

  useEffect(() => () => stop(), [])

  const active = ["listening", "paused", "working"].includes(status)
  const statusLabel = status === "connecting" ? "Connecting" : status === "working" ? "Updating" : status === "paused" ? "Paused" : status === "listening" ? "Listening" : status === "error" ? "Voice error" : "Voice"
  const statusColor = status === "listening" ? "bg-emerald-500" : status === "working" ? "bg-amber-500" : status === "error" ? "bg-red-500" : status === "paused" ? "bg-slate-400" : "bg-sky-500"

  return <div className="fixed bottom-5 right-5 z-50 grid max-w-[calc(100vw-2rem)] justify-items-end gap-2"><div className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 shadow-lg"><span className={`size-2 rounded-full ${statusColor} ${status === "listening" ? "animate-pulse" : ""}`} aria-hidden="true" /><span className="text-xs font-medium" role="status">{statusLabel}</span>{message && <span className="max-w-52 truncate text-[11px] text-muted-foreground">{message}</span>}{status === "paused" ? <button type="button" onClick={resume} className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted" aria-label="Resume voice"><Play className="size-3" />Resume</button> : active ? <button type="button" onClick={pause} disabled={status === "working"} className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50" aria-label="Pause voice"><Pause className="size-3" />Pause</button> : null}{active || status === "connecting" || status === "error" ? <button type="button" onClick={stop} className="inline-flex items-center gap-1 rounded-md border border-red-500/40 px-2 py-1 text-xs text-red-600 hover:bg-red-500/10" aria-label="Stop voice"><Square className="size-3" />Stop</button> : <button type="button" onClick={() => void start()} className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted" aria-label="Start voice"><Mic className="size-3" />Start</button>}</div>{visuals.length > 0 && <div className="grid max-w-xl gap-2 sm:grid-cols-3">{visuals.map((item) => <a key={item.id} href={item.source_url} target="_blank" rel="noreferrer" className="overflow-hidden rounded-md border border-border bg-card text-xs shadow-lg hover:bg-muted">{item.image_url && <img src={item.image_url} alt="" className="h-20 w-full object-cover" loading="lazy" referrerPolicy="no-referrer" />}<span className="block p-2">{item.title}<span className="mt-1 block text-muted-foreground">{item.publisher || "Source"}</span></span></a>)}</div>}</div>
}
