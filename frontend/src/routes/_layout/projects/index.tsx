import { createFileRoute } from "@tanstack/react-router"
import { ProjectsWorkspace } from "@/components/Projects/ProjectsWorkspace"

export const Route = createFileRoute("/_layout/projects/")({
  component: () => <ProjectsWorkspace />,
  head: () => ({ meta: [{ title: "Projects - Vexa" }] }),
})
