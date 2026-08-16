import { Satellite, Menu, X } from "lucide-react"
import { useState } from "react"
import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const links = [
  { label: "AgroSAT", href: "#agrosat" },
  { label: "UrbanSAT", href: "#urbansat" },
  { label: "Informes", href: "#informes" },
  { label: "Metodología", href: "#metodologia" },
  { label: "Contacto", href: "#contacto" },
]

export function TerraSATNavbar() {
  const [open, setOpen] = useState(false)

  return (
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-border/40 bg-background/80 backdrop-blur-xl">
      <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <a href="#" className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-accent">
            <Satellite className="h-5 w-5 text-primary-foreground" />
          </div>
          <div className="flex flex-col leading-none">
            <span className="text-lg font-semibold tracking-tight text-foreground">TerraSAT</span>
            <span className="text-[10px] text-muted-foreground">agtisa.com</span>
          </div>
        </a>

        <div className="hidden items-center gap-8 md:flex">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              {link.label}
            </a>
          ))}
        </div>

        <div className="hidden md:block">
          <a href="#contacto" className={buttonVariants({ size: "sm" })}>
            Solicitar mapa
          </a>
        </div>

        <button
          className="md:hidden"
          onClick={() => setOpen(!open)}
          aria-label="Toggle menu"
        >
          {open ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      </nav>

      <div
        className={cn(
          "overflow-hidden transition-all duration-300 md:hidden",
          open ? "max-h-96" : "max-h-0"
        )}
      >
        <div className="flex flex-col gap-4 px-4 py-6">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              onClick={() => setOpen(false)}
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              {link.label}
            </a>
          ))}
          <a href="#contacto" onClick={() => setOpen(false)} className={buttonVariants({ size: "sm" })}>
            Solicitar mapa
          </a>
        </div>
      </div>
    </header>
  )
}
