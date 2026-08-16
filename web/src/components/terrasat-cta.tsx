import { Satellite } from "lucide-react"
import { buttonVariants } from "@/components/ui/button"

export function TerraSATCTA() {
  return (
    <section className="py-24 sm:py-32">
      <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
        <div className="relative overflow-hidden rounded-3xl border border-primary/20 bg-gradient-to-br from-primary/10 via-card to-accent/10 p-12 text-center">
          <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-primary/10 blur-3xl" />
          <div className="absolute -bottom-20 -left-20 h-64 w-64 rounded-full bg-accent/10 blur-3xl" />

          <div className="relative">
            <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-accent">
              <Satellite className="h-7 w-7 text-primary-foreground" />
            </div>

            <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
              ¿Necesitas inteligencia satelital de tu territorio?
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-muted-foreground">
              Trabajamos con cualquier organización que necesite inteligencia territorial
              en Latinoamérica y el Caribe. Solicita un mapa interactivo piloto de tu región o ciudad.
            </p>

            <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <a href="#contacto" className={buttonVariants({ size: "lg" })}>
                Solicitar mapa piloto
              </a>
              <a href="mailto:info@agtisa.com" className={buttonVariants({ variant: "outline", size: "lg" })}>
                info@agtisa.com
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
