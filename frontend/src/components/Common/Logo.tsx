import { Link } from "@tanstack/react-router"

import { cn } from "@/lib/utils"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  const content =
    variant === "responsive" ? (
      <>
        <span className={cn("flex items-center gap-2 group-data-[collapsible=icon]:hidden", className)}><span className="grid size-7 place-items-center rounded-md bg-foreground font-serif text-sm text-background">V</span><span className="font-semibold tracking-tight">Vexa</span></span>
        <span className={cn("hidden size-7 place-items-center rounded-md bg-foreground font-serif text-sm text-background group-data-[collapsible=icon]:grid", className)} aria-hidden="true">V</span>
      </>
    ) : (
      <span className={cn(variant === "full" ? "flex items-center gap-2" : "grid size-7 place-items-center", className)}><span className="grid size-7 place-items-center rounded-md bg-foreground font-serif text-sm text-background">V</span>{variant === "full" && <span className="font-semibold tracking-tight">Vexa</span>}</span>
    )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}
