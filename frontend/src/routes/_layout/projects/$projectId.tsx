import { createFileRoute, Outlet } from "@tanstack/react-router"

export const Route = createFileRoute("/_layout/projects/$projectId")({
  component: () => <Outlet />,
  head: () => ({ meta: [{ title: "Project workflow - Vexa" }] }),
})
