import { Satellite } from "lucide-react"

const footerLinks = [
  {
    title: "Verticales",
    links: [
      { label: "AgroSAT", href: "#agrosat" },
      { label: "UrbanSAT", href: "#urbansat" },
    ],
  },
  {
    title: "Recursos",
    links: [
      { label: "Informes", href: "#informes" },
      { label: "Metodología", href: "#metodologia" },
    ],
  },
  {
    title: "Contacto",
    links: [
      { label: "Solicitar mapa", href: "#contacto" },
      { label: "info@agtisa.com", href: "mailto:info@agtisa.com" },
    ],
  },
]

export function TerraSATFooter() {
  return (
    <footer className="border-t border-border bg-card/30">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid gap-8 md:grid-cols-4">
          {/* Brand */}
          <div>
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-accent">
                <Satellite className="h-4 w-4 text-primary-foreground" />
              </div>
              <span className="text-lg font-semibold text-foreground">TerraSAT</span>
            </div>
            <p className="mt-4 text-sm text-muted-foreground">
              Mapas interactivos e informes de inteligencia satelital para agricultura y ciudades en Latinoamérica y el Caribe.
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              un producto de <a href="https://agtisa.com" className="text-primary hover:underline">agtisa.com</a>
            </p>
          </div>

          {/* Links */}
          {footerLinks.map((section) => (
            <div key={section.title}>
              <h4 className="text-sm font-semibold text-foreground">{section.title}</h4>
              <ul className="mt-4 space-y-2">
                {section.links.map((link) => (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 border-t border-border pt-6 text-center text-xs text-muted-foreground">
          © 2026 TerraSAT · agtisa.com · Todos los derechos reservados
        </div>
      </div>
    </footer>
  )
}
