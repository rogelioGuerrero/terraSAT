import { Satellite, ArrowRight, Activity, MapPinned } from "lucide-react"
import { buttonVariants } from "@/components/ui/button"
import heroVideo from "@/assets/hero-aerial-opt.mp4"
import heroPoster from "@/assets/hero-aerial-poster-opt.jpg"

export function TerraSATHero() {
  return (
    <section className="relative flex min-h-screen items-center justify-center overflow-hidden">
      {/* Background video */}
      <div className="absolute inset-0">
        <video
          autoPlay
          loop
          muted
          playsInline
          poster={heroPoster}
          className="h-full w-full object-cover"
        >
          <source src={heroVideo} type="video/mp4" />
        </video>
        {/* Dark gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-b from-background/60 via-background/40 to-background" />
        <div className="absolute inset-0 bg-gradient-to-r from-background/70 via-transparent to-background/30" />
      </div>

      {/* Scan line animation */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="terrasat-scanline absolute left-0 right-0 h-px bg-gradient-to-r from-transparent via-primary to-transparent opacity-60" />
      </div>

      {/* Content */}
      <div className="relative z-10 mx-auto max-w-4xl px-4 py-32 text-center sm:px-6 lg:px-8">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-4 py-1.5 text-xs font-medium text-primary">
          <Satellite className="h-3.5 w-3.5" />
          Procesa · Analiza · Alerta
        </div>

        <h1 className="text-5xl font-bold tracking-tight text-foreground sm:text-6xl lg:text-7xl">
          Imágenes satelitales
          <br />
          <span className="text-foreground [text-shadow:0_2px_8px_rgba(0,0,0,0.5)]">
            para anticipar eventos
          </span>
        </h1>

        <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
          Mapas interactivos e informes de inteligencia satelital para tu territorio.
          Detección de deterioro agrícola 15 días antes de síntomas visibles.
          Monitoreo urbano de islas de calor, expansión y áreas verdes.
        </p>

        <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
          <a href="#contacto" className={buttonVariants({ size: "lg" })}>
            <MapPinned className="h-4 w-4" />
            Solicitar mapa de mi territorio
          </a>
          <a href="#agrosat" className={buttonVariants({ variant: "outline", size: "lg" })}>
            <Activity className="h-4 w-4" />
            Ver servicios
            <ArrowRight className="h-4 w-4" />
          </a>
        </div>

        {/* Stats */}
        <div className="mx-auto mt-16 grid max-w-2xl grid-cols-3 gap-8">
          <div>
            <div className="text-3xl font-bold text-foreground">15</div>
            <div className="text-xs text-muted-foreground">días de anticipación</div>
          </div>
          <div>
            <div className="text-3xl font-bold text-foreground">LAC</div>
            <div className="text-xs text-muted-foreground">cobertura regional</div>
          </div>
          <div>
            <div className="text-3xl font-bold text-foreground">100%</div>
            <div className="text-xs text-muted-foreground">datos satelitales</div>
          </div>
        </div>
      </div>
    </section>
  )
}
