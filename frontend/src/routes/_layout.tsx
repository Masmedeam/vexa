import { createFileRoute, Outlet } from "@tanstack/react-router"
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import AppSidebar from "@/components/Sidebar/AppSidebar"
import { isLoggedIn } from "@/hooks/useAuth"
import { redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_layout")({
  component: Layout,
  beforeLoad: async () => {
    if (!isLoggedIn()) {
      throw redirect({ to: "/login" })
    }
  },
})

function Layout() {
  return <SidebarProvider><AppSidebar /><SidebarInset><header className="flex h-14 items-center gap-3 border-b px-5"><SidebarTrigger /><span className="font-semibold tracking-tight">Vexa</span></header><main className="flex-1 p-6"><Outlet /></main></SidebarInset></SidebarProvider>
}
