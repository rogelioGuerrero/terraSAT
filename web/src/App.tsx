import { TerraSATNavbar } from "@/components/terrasat-navbar"
import { TerraSATHero } from "@/components/terrasat-hero"
import { TerraSATServices } from "@/components/terrasat-services"
import { TerraSATPortfolio } from "@/components/terrasat-portfolio"
import { TerraSATAbout } from "@/components/terrasat-about"
import { TerraSATCTA } from "@/components/terrasat-cta"
import { TerraSATContact } from "@/components/terrasat-contact"
import { TerraSATFooter } from "@/components/terrasat-footer"

function App() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <TerraSATNavbar />
      <main>
        <TerraSATHero />
        <TerraSATServices />
        <TerraSATPortfolio />
        <TerraSATAbout />
        <TerraSATCTA />
        <TerraSATContact />
      </main>
      <TerraSATFooter />
    </div>
  )
}

export default App
