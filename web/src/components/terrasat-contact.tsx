import { Mail, MapPin, MessageCircle } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { buttonVariants } from "@/components/ui/button"

export function TerraSATContact() {
  return (
    <section id="contacto" className="scroll-mt-20 py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid gap-12 lg:grid-cols-2">
          {/* Info */}
          <div>
            <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
              Solicita tu mapa interactivo
            </h2>
            <p className="mt-4 text-muted-foreground">
              Cuéntanos sobre tu región o ciudad. Te respondemos en menos de 24 horas
              con una propuesta de mapa interactivo e informe satelital.
            </p>

            <div className="mt-8 space-y-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <Mail className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <div className="text-sm font-medium text-foreground">Email</div>
                  <div className="text-sm text-muted-foreground">info@agtisa.com</div>
                </div>
              </div>

              <a
                href="https://wa.me/595971561333"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 transition-opacity hover:opacity-80"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <MessageCircle className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <div className="text-sm font-medium text-foreground">WhatsApp</div>
                  <div className="text-sm text-muted-foreground">0971 561333</div>
                </div>
              </a>

              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <MapPin className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <div className="text-sm font-medium text-foreground">Cobertura</div>
                  <div className="text-sm text-muted-foreground">Latinoamérica y el Caribe (LAC)</div>
                </div>
              </div>
            </div>
          </div>

          {/* Form */}
          <form
            name="contact"
            method="POST"
            data-netlify="true"
            className="rounded-2xl border border-border bg-card p-6 sm:p-8"
          >
            <input type="hidden" name="form-name" value="contact" />

            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label htmlFor="name">Nombre</Label>
                  <Input id="name" name="name" type="text" placeholder="Tu nombre" className="mt-1.5" required />
                </div>
                <div>
                  <Label htmlFor="email">Email</Label>
                  <Input id="email" name="email" type="email" placeholder="tu@email.com" className="mt-1.5" required />
                </div>
              </div>

              <div>
                <Label htmlFor="organization">Organización</Label>
                <Input id="organization" name="organization" type="text" placeholder="Cooperativa, municipio, empresa..." className="mt-1.5" />
              </div>

              <div>
                <Label htmlFor="interest">Interés</Label>
                <select
                  id="interest"
                  name="interest"
                  className="mt-1.5 flex h-9 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <option value="agrosat">AgroSAT — Mapa de mi región agrícola</option>
                  <option value="urbansat">UrbanSAT — Mapa de mi ciudad</option>
                  <option value="both">Ambos</option>
                </select>
              </div>

              <div>
                <Label htmlFor="message">Mensaje</Label>
                <Textarea
                  id="message"
                  name="message"
                  placeholder="Cuéntanos sobre tu región o ciudad..."
                  className="mt-1.5"
                  rows={4}
                />
              </div>

              <button type="submit" className={buttonVariants({ size: "lg", className: "w-full" })}>
                Enviar solicitud
              </button>
            </div>
          </form>
        </div>
      </div>
    </section>
  )
}
