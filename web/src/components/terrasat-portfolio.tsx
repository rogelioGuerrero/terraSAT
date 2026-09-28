import { useMemo, useState } from "react"
import type { ComponentPropsWithoutRef } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import type { Components } from "react-markdown"
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

// Assets por convención de nombre: informe-*-opt.jpg e informe-*-video-opt.mp4
// import.meta.glob hace que agregar un informe sea solo dejar archivos en
// src/assets/ + una entrada en data/informes.json — sin tocar este archivo.
const imageAssets = import.meta.glob<string>("@/assets/informe-*-opt.jpg", {
  eager: true,
  query: "?url",
  import: "default",
})
const videoAssets = import.meta.glob<string>("@/assets/informe-*-video-opt.mp4", {
  eager: true,
  query: "?url",
  import: "default",
})

const fileKey = (p: string) => p.split("/").pop() ?? p

const imageMap: Record<string, string> = Object.fromEntries(
  Object.entries(imageAssets).map(([p, url]) => [fileKey(p), url])
)
const videoMap: Record<string, string> = Object.fromEntries(
  Object.entries(videoAssets).map(([p, url]) => [fileKey(p), url])
)
const fallbackImage = imageMap["informe-agrosat-alert-opt.jpg"] ?? Object.values(imageMap)[0] ?? ""

interface KeyStat {
  value: string
  label: string
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
  cta?: string
  hashtags?: string[]
  keyStats?: KeyStat[]
}

const informes: Informe[] = informesData.map((item) => ({
  ...item,
  category: item.category as "agrosat" | "urbansat" | "forestsat",
  image: imageMap[item.image] ?? fallbackImage,
  video: item.video ? (videoMap[item.video] ?? undefined) : undefined,
}))

const filters = [
  { label: "Todos", value: "all" as const },
  { label: "AgroSAT", value: "agrosat" as const },
  { label: "UrbanSAT", value: "urbansat" as const },
  { label: "ForestSAT", value: "forestsat" as const },
]

const PAGE_SIZE = 6

// ─── Limpieza editorial ────────────────────────────────────────────────
// Los artículos llegan como markdown crudo con restos del formato social
// (emojis, CTA y hashtags pegados al cuerpo). Aquí se separan para poder
// darles su propio lugar en la página.

const EMOJI_RE = /[\p{Extended_Pictographic}\u{FE0F}\u{200D}]/gu
const HASHTAG_LINE_RE = /^(\s*#[\p{L}\d_]+\s*)+$/u

function stripEmojis(s: string): string {
  // Colapsa solo espacios horizontales — \n es separador de párrafo markdown
  return s.replace(EMOJI_RE, "").replace(/[^\S\n]{2,}/g, " ").trim()
}

function stripMarkdown(s: string): string {
  return s
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/__(.+?)__/g, "$1")
    .replace(/^#+\s*/g, "")
    .replace(/[`*_~]/g, "")
}

/** Título publicable: sin markdown, sin emojis, sin espacios dobles. */
function sanitizeTitle(s: string): string {
  return stripEmojis(stripMarkdown(s)).replace(/\s{2,}/g, " ").trim()
}

/** 55 000 / 78,300 / 10.500 → 55.000 / 78.300 / 10.500 (convención es-ES).
 *  No toca decimales: el separador solo aplica si la parte entera empieza
 *  en dígito no-cero ("78,300" → miles; "0,065" → decimal intacto). */
function normalizeNumbers(s: string): string {
  return s.replace(/[1-9]\d{0,2}([,\s\u00A0\u202F]\d{3})+(?!\d)/g, (m) =>
    m.replace(/[,\s\u00A0\u202F]/g, ".")
  )
}

function normalizeText(s: string): string {
  return normalizeNumbers(stripEmojis(s))
}

interface SplitArticle {
  body: string
  cta: string
  hashtags: string[]
}

const isSameText = (a: string, b: string) =>
  normalizeText(stripMarkdown(a)).toLowerCase() ===
  normalizeText(stripMarkdown(b)).toLowerCase()

/**
 * Separa el artículo en cuerpo editorial + CTA + hashtags.
 * - CTA: párrafo que empieza con "¿Su …" o menciona el contacto comercial.
 * - Hashtags: líneas de solo #tags (siempre al final).
 * - Primera línea: se descarta si repite el título o es un marcador interno
 *   ("LEDE") — el título ya se muestra como heading del diálogo.
 * - Líneas 100% en negrita se promueven a headings markdown (###).
 */
function splitArticle(raw: string, title: string): SplitArticle {
  const lines = raw.replace(/\r\n?/g, "\n").split("\n")

  // 1) Hashtags del final
  const hashtags: string[] = []
  while (lines.length) {
    const last = lines[lines.length - 1]
    if (last.trim() === "" && hashtags.length === 0) {
      lines.pop()
      continue
    }
    if (HASHTAG_LINE_RE.test(last)) {
      hashtags.unshift(...last.trim().split(/\s+/))
      lines.pop()
    } else {
      break
    }
  }

  // 2) CTA comercial (párrafo con el contacto, generalmente el último)
  let cta = ""
  const ctaIdx = lines.findIndex(
    (l) => l.trim().startsWith("¿Su ") || l.includes("Contacto: info@agtisa.com")
  )
  if (ctaIdx >= 0) {
    cta = stripEmojis(lines[ctaIdx])
    lines.splice(ctaIdx, 1)
    // Párrafos vacíos que quedaron alrededor del CTA
    while (lines.length && lines[lines.length - 1].trim() === "") lines.pop()
  }

  // 3) Primera línea que repite el título o marcador interno
  const firstIdx = lines.findIndex((l) => l.trim() !== "")
  if (firstIdx >= 0) {
    const first = lines[firstIdx]
    if (/LEDE/i.test(stripMarkdown(first)) || isSameText(first, title)) {
      lines.splice(firstIdx, 1)
    }
  }

  // 4) Líneas fully-bold → headings, y limpieza general
  const body = lines
    .map((l) => {
      const clean = stripEmojis(l.trim())
      if (clean && /^\*\*.+\*\*$/.test(clean)) {
        return `### ${clean.replace(/^\*\*|\*\*$/g, "")}`
      }
      return l
    })
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim()

  return {
    body: normalizeNumbers(stripEmojis(body)),
    cta: normalizeText(cta).replace(/\s*\n\s*/g, " "),
    hashtags: hashtags.map((h) => h.replace(/^#/, "")),
  }
}

// ─── Render markdown ──────────────────────────────────────────────────

const markdownComponents: Components = {
  table: ({ children }: ComponentPropsWithoutRef<"table">) => (
    <div className="informe-table-wrap">
      <table>{children}</table>
    </div>
  ),
}

function ArticleBody({ markdown }: { markdown: string }) {
  return (
    <div className="informe-prose">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {markdown}
      </ReactMarkdown>
    </div>
  )
}

export function TerraSATPortfolio() {
  const [filter, setFilter] = useState<"all" | "agrosat" | "urbansat" | "forestsat">("all")
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)
  const [selected, setSelected] = useState<Informe | null>(null)

  const filtered = filter === "all" ? informes : informes.filter((b) => b.category === filter)
  const visible = filtered.slice(0, visibleCount)
  const hasMore = visibleCount < filtered.length

  const selectedParts = useMemo(
    () =>
      selected
        ? splitArticle(
            selected.article ?? selected.excerpt,
            selected.title
          )
        : null,
    [selected]
  )

  function handleFilterChange(value: "all" | "agrosat" | "urbansat" | "forestsat") {
    setFilter(value)
    setVisibleCount(PAGE_SIZE)
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
                <h3 className="font-semibold text-foreground">{sanitizeTitle(boletin.title)}</h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  {normalizeNumbers(boletin.excerpt)}
                </p>

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
                    {sanitizeTitle(selected.title)}
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

                {/* Bajada (standfirst): resume el hallazgo antes del cuerpo */}
                <p className="mt-3 border-l-2 border-primary/60 pl-3 text-[15px] italic leading-relaxed text-foreground/85">
                  {normalizeNumbers(selected.excerpt)}
                </p>

                {/* Franja de cifras clave */}
                {selected.keyStats && selected.keyStats.length > 0 && (
                  <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                    {selected.keyStats.map((s) => (
                      <div
                        key={s.label}
                        className="flex flex-col rounded-lg border border-border bg-muted/30 px-3 py-2.5"
                      >
                        <dt className="order-2 mt-0.5 text-[11px] leading-tight text-muted-foreground">
                          {s.label}
                        </dt>
                        <dd className="order-first text-lg font-bold leading-tight text-foreground">
                          {normalizeNumbers(s.value)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                )}

                {selectedParts && selectedParts.body.length > 0 && (
                  <ArticleBody markdown={selectedParts.body} />
                )}

                {/* CTA comercial — separado del cuerpo editorial */}
                {(selected.cta || selectedParts?.cta) && (
                  <div className="mt-6 rounded-lg border border-border bg-muted/40 p-4">
                    <p className="text-sm leading-relaxed text-foreground/80">
                      {selected.cta || selectedParts?.cta}
                    </p>
                    <a
                      href="mailto:info@agtisa.com"
                      className="mt-2 inline-block text-sm font-medium text-primary hover:underline"
                    >
                      info@agtisa.com
                    </a>
                  </div>
                )}

                {/* Temas */}
                {(selected.hashtags ?? selectedParts?.hashtags)?.length ? (
                  <div className="mt-4 flex flex-wrap gap-1.5">
                    {(selected.hashtags ?? selectedParts!.hashtags).map((h) => (
                      <span
                        key={h}
                        className="rounded-full bg-muted px-2.5 py-0.5 text-xs text-muted-foreground"
                      >
                        #{h}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </section>
  )
}
