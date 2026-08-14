import { createFileRoute, Outlet } from "@tanstack/react-router"
import { VoiceAssistant } from "@/components/VoiceAssistant"

export const Route = createFileRoute("/_layout/projects/$projectId")({
  component: ProjectLayout,
  head: () => ({ meta: [{ title: "Project workflow - Vexa" }] }),
})

function ProjectLayout() {
  const { projectId } = Route.useParams()
  return <><VoiceAssistant projectId={projectId} /><Outlet /></>
}
