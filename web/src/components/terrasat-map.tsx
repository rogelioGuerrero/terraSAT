import { MapContainer, TileLayer, CircleMarker, Tooltip } from "react-leaflet"
import "leaflet/dist/leaflet.css"

const sites = [
  { name: "Bogotá", country: "Colombia", coords: [4.71, -74.07] as [number, number], type: "agro" },
  { name: "Cundinamarca", country: "Colombia", coords: [4.8, -74.0] as [number, number], type: "agro" },
  { name: "Cuenca", country: "Ecuador", coords: [-2.9, -79.0] as [number, number], type: "agro" },
  { name: "Santa Cruz", country: "Bolivia", coords: [-17.78, -63.18] as [number, number], type: "agro" },
  { name: "Asunción", country: "Paraguay", coords: [-25.26, -57.59] as [number, number], type: "urban" },
  { name: "Santiago", country: "Chile", coords: [-33.45, -70.67] as [number, number], type: "urban" },
  { name: "Montevideo", country: "Uruguay", coords: [-34.90, -56.16] as [number, number], type: "urban" },
  { name: "Buenos Aires", country: "Argentina", coords: [-34.61, -58.39] as [number, number], type: "urban" },
  { name: "Ciudad de Panamá", country: "Panamá", coords: [8.98, -79.53] as [number, number], type: "urban" },
  { name: "Quito", country: "Ecuador", coords: [-0.18, -78.47] as [number, number], type: "urban" },
]

export function TerraSATMap() {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-border bg-card">
      <div className="absolute right-3 top-3 z-[1000] flex gap-2">
        <span className="flex items-center gap-1.5 rounded-full bg-background/80 px-3 py-1 text-xs font-medium text-amber-400 backdrop-blur">
          <span className="h-2 w-2 rounded-full bg-amber-400" /> AgroSAT
        </span>
        <span className="flex items-center gap-1.5 rounded-full bg-background/80 px-3 py-1 text-xs font-medium text-primary backdrop-blur">
          <span className="h-2 w-2 rounded-full bg-primary" /> UrbanSAT
        </span>
      </div>
      <MapContainer
        center={[-10, -65] as [number, number]}
        zoom={3}
        scrollWheelZoom={false}
        style={{ height: "400px", width: "100%", background: "#0a0f0e" }}
        attributionControl={false}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        {sites.map((site) => (
          <CircleMarker
            key={`${site.name}-${site.country}`}
            center={site.coords}
            radius={6}
            pathOptions={{
              color: site.type === "agro" ? "#f59e0b" : "#0d9488",
              fillColor: site.type === "agro" ? "#f59e0b" : "#0d9488",
              fillOpacity: 0.7,
              weight: 2,
            }}
          >
            <Tooltip direction="top" offset={[0, -8]} opacity={1}>
              <div className="text-xs">
                <div className="font-semibold">{site.name}</div>
                <div className="text-muted-foreground">{site.country}</div>
              </div>
            </Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  )
}
