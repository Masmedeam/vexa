import { createFileRoute, Outlet } from "@tanstack/react-router"

export const Route = createFileRoute("/_layout/projects")({
  component: () => <Outlet />,
  head: () => ({ meta: [{ title: "Projects - Vexa" }] }),
})
