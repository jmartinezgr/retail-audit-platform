import { Route, Routes } from "react-router-dom"

import { AppLayout } from "@/components/app/layout"
import { HomePage } from "@/pages/home-page"
import { JobDetailPage } from "@/pages/job-detail-page"
import { LandingPage } from "@/pages/landing-page"

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route element={<AppLayout />}>
        <Route path="/app" element={<HomePage />} />
        <Route path="/jobs/:uploadId" element={<JobDetailPage />} />
      </Route>
    </Routes>
  )
}

export default App
