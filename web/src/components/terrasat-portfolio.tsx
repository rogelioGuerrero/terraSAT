import { useState } from "react"
import { MapPin, Calendar, ArrowUpRight, ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"
import informesData from "@/data/informes.json"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"

import coffeeImg from "@/assets/informe-coffee-opt.jpg"
import urbanHeatImg from "@/assets/informe-urban-heat-opt.jpg"
import soybeanImg from "@/assets/informe-soybean-opt.jpg"
import urbanSprawlImg from "@/assets/informe-urban-sprawl-opt.jpg"
import coffeeHillImg from "@/assets/informe-coffee-hill-opt.jpg"
import urbanTreesImg from "@/assets/informe-urban-trees-opt.jpg"
import agrosatCrisisImg from "@/assets/informe-agrosat-crisis-opt.jpg"
import forestImg from "@/assets/informe-forest-opt.jpg"

import agrosatCrisisVideo from "@/assets/informe-agrosat-crisis-video-opt.mp4"
import coffeeVideo from "@/assets/informe-coffee-video-opt.mp4"
import urbanHeatVideo from "@/assets/informe-urban-heat-video-opt.mp4"
import soybeanVideo from "@/assets/informe-soybean-video-opt.mp4"
import urbanSprawlVideo from "@/assets/informe-urban-sprawl-video-opt.mp4"
import coffeeHillVideo from "@/assets/informe-coffee-hill-video-opt.mp4"
import urbanTreesVideo from "@/assets/informe-urban-trees-video-opt.mp4"
import forestVideo from "@/assets/informe-forest-video-opt.mp4"

const imageMap: Record<string, string> = {
  "informe-coffee-opt.jpg": coffeeImg,
  "informe-urban-heat-opt.jpg": urbanHeatImg,
  "informe-soybean-opt.jpg": soybeanImg,
  "informe-urban-sprawl-opt.jpg": urbanSprawlImg,
  "informe-coffee-hill-opt.jpg": coffeeHillImg,
  "informe-urban-trees-opt.jpg": urbanTreesImg,
  "informe-agrosat-crisis-opt.jpg": agrosatCrisisImg,
  "informe-forest-opt.jpg": forestImg,
}

const videoMap: Record<string, string> = {
  "informe-agrosat-crisis-video-opt.mp4": agrosatCrisisVideo,
  "informe-coffee-video-opt.mp4": coffeeVideo,
  "informe-urban-heat-video-opt.mp4": urbanHeatVideo,
  "informe-soybean-video-opt.mp4": soybeanVideo,
  "informe-urban-sprawl-video-opt.mp4": urbanSprawlVideo,
  "informe-coffee-hill-video-opt.mp4": coffeeHillVideo,
  "informe-urban-trees-video-opt.mp4": urbanTreesVideo,
  "informe-forest-video-opt.mp4": forestVideo,
}

interface Informe {
  id: string
  title: string
  category: "agrosat" | "urbansat" | "forestsat"
  date: string
  location: string
  image: string
  video?: string
  excerpt: string
  article?: string
}

const informes: Informe[] = informesData.map((item) => ({
  ...item,
  category: item.category as "agrosat" | "urbansat" | "forestsat",
  image: imageMap[item.image] ?? coffeeImg,
  video: item.video ? (videoMap[item.video] ?? undefined) : undefined,
}))

const filters = [
  { label: "Todos", value: "all" as const },
  { label: "AgroSAT", value: "agrosat" as const },
  { label: "UrbanSAT", value: "urbansat" as const },
  { label: "ForestSAT", value: "forestsat" as const },
]

const PAGE_SIZE = 6

export function TerraSATPortfolio() {
  const [filter, setFilter] = useState<"all" | "agrosat" | "urbansat" | "forestsat">("all")
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)
  const [selected, setSelected] = useState<Informe | null>(null)

  const filtered = filter === "all" ? informes : informes.filter((b) => b.category === filter)
  const visible = filtered.slice(0, visibleCount)
  const hasMore = visibleCount < filtered.length

  function handleFilterChange(value: "all" | "agrosat" | "urbansat" | "forestsat") {
    setFilter(value)
    setVisibleCount(PAGE_SIZE)
  }

  function formatArticle(text: string): string[] {
    return text.split("\n").filter((line) => line.trim().length > 0)
  }

  return (
    <section id="informes" className="scroll-mt-20 py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            Informes recientes
          </h2>
          <p className="mt-4 text-muted-foreground">
            Inteligencia satelital procesada con IA, disponible como mapa interactivo + informe.
          </p>
        </div>

        {/* Filters */}
        <div className="mt-10 flex justify-center gap-2">
          {filters.map((f) => (
            <button
              key={f.value}
              onClick={() => handleFilterChange(f.value)}
              className={cn(
                "rounded-full px-4 py-1.5 text-sm font-medium transition-colors",
                filter === f.value
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:text-foreground"
              )}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Grid */}
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {visible.map((boletin) => (
            <article
              key={boletin.id}
              onClick={() => setSelected(boletin)}
              className="group relative cursor-pointer overflow-hidden rounded-xl border border-border bg-card transition-all hover:border-primary/40"
            >
              <div className="relative h-48 overflow-hidden">
                <img
                  src={boletin.image}
                  alt={boletin.title}
                  className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-card to-transparent" />
                <div
                  className={cn(
                    "absolute top-3 right-3 rounded-full px-2.5 py-0.5 text-[10px] font-medium",
                    boletin.category === "agrosat"
                      ? "bg-amber-400/20 text-amber-400"
                      : boletin.category === "forestsat"
                        ? "bg-green-500/20 text-green-500"
                        : "bg-primary/20 text-primary"
                  )}
                >
                  {boletin.category === "agrosat" ? "AgroSAT" : boletin.category === "forestsat" ? "ForestSAT" : "UrbanSAT"}
                </div>
              </div>

              <div className="p-5">
                <h3 className="font-semibold text-foreground">{boletin.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{boletin.excerpt}</p>

                <div className="mt-4 flex items-center gap-4 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <MapPin className="h-3 w-3" />
                    {boletin.location}
                  </span>
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3 w-3" />
                    {boletin.date}
                  </span>
                </div>

                <div className="mt-4 flex items-center gap-1 text-sm font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
                  Ver detalle
                  <ArrowUpRight className="h-3.5 w-3.5" />
                </div>
              </div>
            </article>
          ))}
        </div>

        {/* Load more */}
        {hasMore && (
          <div className="mt-10 flex justify-center">
            <button
              onClick={() => setVisibleCount((c) => c + PAGE_SIZE)}
              className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-6 py-2.5 text-sm font-medium text-foreground transition-colors hover:border-primary/40 hover:bg-muted"
            >
              Cargar más informes
              <ChevronDown className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>

      {/* Modal */}
      <Dialog open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto p-0 sm:max-w-2xl">
          {selected && (
            <>
              {/* Video/Image header */}
              <div className="relative h-56 overflow-hidden rounded-t-xl bg-black sm:h-64">
                {selected.video ? (
                  <video
                    autoPlay
                    loop
                    muted
                    playsInline
                    poster={selected.image}
                    className="h-full w-full object-cover"
                  >
                    <source src={selected.video} type="video/mp4" />
                    <img
                      src={selected.image}
                      alt={selected.title}
                      className="h-full w-full object-cover"
                    />
                  </video>
                ) : (
                  <img
                    src={selected.image}
                    alt={selected.title}
                    className="h-full w-full object-cover"
                  />
                )}
                <div className="absolute inset-0 bg-gradient-to-t from-popover via-popover/10 to-transparent" />
                <div
                  className={cn(
                    "absolute top-4 right-4 rounded-full px-3 py-1 text-xs font-medium",
                    selected.category === "agrosat"
                      ? "bg-amber-400/20 text-amber-400"
                      : selected.category === "forestsat"
                        ? "bg-green-500/20 text-green-500"
                        : "bg-primary/20 text-primary"
                  )}
                >
                  {selected.category === "agrosat" ? "AgroSAT" : selected.category === "forestsat" ? "ForestSAT" : "UrbanSAT"}
                </div>
              </div>

              {/* Content */}
              <div className="p-6 pt-4">
                <DialogHeader className="gap-1">
                  <DialogTitle className="text-xl font-bold">
                    {selected.article ? formatArticle(selected.article)[0] : selected.title}
                  </DialogTitle>
                  <DialogDescription className="flex items-center gap-4 text-xs">
                    <span className="flex items-center gap-1">
                      <MapPin className="h-3 w-3" />
                      {selected.location}
                    </span>
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3 w-3" />
                      {selected.date}
                    </span>
                  </DialogDescription>
                </DialogHeader>

                {selected.article && (
                  <div className="mt-4 space-y-3 text-sm leading-relaxed text-muted-foreground">
                    {formatArticle(selected.article)
                      .slice(1)
                      .map((line, i) => {
                        const isHashtag = line.startsWith("#")
                        return (
                          <p
                            key={i}
                            className={cn(
                              isHashtag && "pt-2 text-xs text-primary/70",
                              !isHashtag && line.length < 60 && "font-medium text-foreground"
                            )}
                          >
                            {line}
                          </p>
                        )
                      })}
                  </div>
                )}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </section>
  )
}
