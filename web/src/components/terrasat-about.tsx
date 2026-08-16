import { Satellite, Cpu, FileText, Map } from "lucide-react"
import { TerraSATMap } from "@/components/terrasat-map"

const steps = [
  {
    icon: Satellite,
    title: "Captura satelital",
    description: "Imágenes de sensores ópticos y térmicos con resolución de 10–30 metros por píxel.",
  },
  {
    icon: Cpu,
    title: "Procesamiento con IA",
    description: "Modelos de visión computacional detectan patrones de estrés vegetal, calor urbano y cambios de cobertura.",
  },
  {
    icon: FileText,
    title: "Informe narrativo",
    description: "Documento con contexto regional, datos cuantificados y recomendaciones accionables.",
  },
  {
    icon: Map,
    title: "Mapa interactivo",
    description: "Visualización HTML con capas georreferenciadas de las zonas detectadas.",
  },
]

const stats = [
  { value: "10m", label: "resolución espacial" },
  { value: "5 días", label: "frecuencia de revisita" },
  { value: "15 días", label: "anticipación agrícola" },
  { value: "IA", label: "procesamiento automatizado" },
]

export function TerraSATAbout() {
  return (
    <section id="metodologia" className="scroll-mt-20 border-y border-border bg-card/30 py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            Del satélite al mapa interactivo
          </h2>
          <p className="mt-4 text-muted-foreground">
            Pipeline automatizado que transforma datos satelitales crudos en
            mapas interactivos e informes accionables para cualquier organización que necesite inteligencia territorial.
          </p>
        </div>

        {/* Steps */}
        <div className="mt-16 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((step, i) => (
            <div key={step.title} className="relative">
              {i < steps.length - 1 && (
                <div className="absolute left-full top-8 hidden h-px w-full -translate-x-1/2 bg-gradient-to-r from-primary/40 to-transparent lg:block" />
              )}
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10">
                <step.icon className="h-7 w-7 text-primary" />
              </div>
              <div className="mt-4 text-xs font-mono text-muted-foreground">Paso {i + 1}</div>
              <h3 className="mt-1 font-semibold text-foreground">{step.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{step.description}</p>
            </div>
          ))}
        </div>

        {/* Map + Stats */}
        <div className="mt-20 grid gap-8 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <TerraSATMap />
          </div>
          <div className="grid grid-cols-2 gap-6 lg:col-span-2 lg:grid-cols-1 lg:gap-4">
            {stats.map((stat) => (
              <div key={stat.label} className="flex items-baseline gap-3">
                <div className="text-3xl font-bold text-primary">{stat.value}</div>
                <div className="text-sm text-muted-foreground">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
