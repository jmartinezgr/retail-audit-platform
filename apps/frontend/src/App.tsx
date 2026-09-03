import { Route, Routes } from "react-router-dom"

import { AppLayout } from "@/components/app/layout"
import { HomePage } from "@/pages/home-page"
import { InvoiceDetailPage } from "@/pages/invoice-detail-page"
import { JobDetailPage } from "@/pages/job-detail-page"
import { LandingPage } from "@/pages/landing-page"
import { RulesPage } from "@/pages/rules-page"

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route element={<AppLayout />}>
        <Route path="/app" element={<HomePage />} />
        <Route path="/app/rules" element={<RulesPage />} />
        <Route path="/jobs/:uploadId" element={<JobDetailPage />} />
        <Route path="/jobs/:uploadId/fac/:facturaId" element={<InvoiceDetailPage />} />
      </Route>
    </Routes>
  )
}

export default App
