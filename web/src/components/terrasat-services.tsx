import { Sprout, Building2, ThermometerSun, Trees, MapPin, Clock, FileText, Map as MapIcon, Drone, Package } from "lucide-react"
import droughtSoil from "@/assets/drought-soil-opt.jpg"

const services = [
  {
    id: "agrosat",
    name: "AgroSAT",
    tagline: "Alerta temprana agrícola",
    description:
      "Informe semanal con mapa interactivo que detecta deterioro de cultivos, déficit hídrico y enfermedad del cultivo 15 días antes de que aparezcan síntomas visibles.",
    image: droughtSoil,
    accent: "text-amber-400",
    accentBg: "bg-amber-400/10",
    accentBorder: "border-amber-400/20",
    features: [
      { icon: Sprout, label: "Detección de estrés en cultivos" },
      { icon: Clock, label: "15 días de anticipación" },
      { icon: MapPin, label: "Cobertura regional Latinoamérica" },
    ],
    deliverables: [
      { icon: MapIcon, label: "Mapa interactivo HTML" },
      { icon: FileText, label: "Informe narrativo con recomendaciones" },
      { icon: Drone, label: "GeoJSON/KML drone-ready para vuelos dirigidos" },
      { icon: Package, label: "Mapa de prescripción (VRA) para aplicación variable" },
    ],
    clients: "Productores, cooperativas, aseguradoras, agroservicios, ONGs, fondos verdes en LAC",
  },
  {
    id: "urbansat",
    name: "UrbanSAT",
    tagline: "Monitoreo urbano satelital",
    description:
      "Informe mensual con mapa interactivo de nuevas construcciones, islas de calor urbano y pérdida de áreas verdes en ciudades de Latinoamérica y el Caribe.",
    image: "https://picsum.photos/seed/aerial-city-night-7/800/600?grayscale",
    accent: "text-primary",
    accentBg: "bg-primary/10",
    accentBorder: "border-primary/20",
    features: [
      { icon: Building2, label: "Cambio de uso de suelo" },
      { icon: ThermometerSun, label: "Islas de calor urbano" },
      { icon: Trees, label: "Pérdida de áreas verdes" },
    ],
    deliverables: [
      { icon: MapIcon, label: "Mapa interactivo HTML" },
      { icon: FileText, label: "Informe narrativo con recomendaciones" },
    ],
    clients: "Gobiernos, catastro, urbanistas, ONGs ambientales, fondos verdes, academia en LAC",
  },
]

export function TerraSATServices() {
  return (
    <section className="relative py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            Dos verticales, un satélite
          </h2>
          <p className="mt-4 text-muted-foreground">
            Procesamos imágenes satelitales con IA para generar informes accionables en agricultura y gestión urbana.
          </p>
        </div>

        <div className="mt-16 grid gap-8 lg:grid-cols-2">
          {services.map((service) => (
            <div
              key={service.id}
              id={service.id}
              className="group relative overflow-hidden rounded-2xl border border-border bg-card scroll-mt-20"
            >
              {/* Image */}
              <div className="relative h-64 overflow-hidden">
                <img
                  src={service.image}
                  alt={service.name}
                  className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-card via-card/40 to-transparent" />
                <div className={`absolute top-4 left-4 rounded-full border ${service.accentBorder} ${service.accentBg} px-3 py-1 text-xs font-medium ${service.accent}`}>
                  {service.tagline}
                </div>
              </div>

              {/* Content */}
              <div className="p-6">
                <h3 className="text-2xl font-bold text-foreground">{service.name}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{service.description}</p>

                <ul className="mt-6 space-y-3">
                  {service.features.map((feature) => (
                    <li key={feature.label} className="flex items-center gap-3 text-sm text-foreground">
                      <feature.icon className={`h-4 w-4 ${service.accent}`} />
                      {feature.label}
                    </li>
                  ))}
                </ul>

                <div className="mt-6 border-t border-border pt-4">
                  <p className="text-xs font-medium text-foreground">Entregables</p>
                  <ul className="mt-3 space-y-2">
                    {service.deliverables.map((deliv) => (
                      <li key={deliv.label} className="flex items-center gap-2 text-xs text-muted-foreground">
                        <deliv.icon className="h-3.5 w-3.5 text-primary" />
                        {deliv.label}
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="mt-4 border-t border-border pt-4">
                  <p className="text-xs text-muted-foreground">
                    <span className="font-medium text-foreground">Clientes:</span> {service.clients}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
