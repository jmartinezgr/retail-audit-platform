import { Route, Routes } from "react-router-dom"

import { AppLayout } from "@/components/app/layout"
import { HomePage } from "@/pages/home-page"
import { JobDetailPage } from "@/pages/job-detail-page"

function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<HomePage />} />
        <Route path="jobs/:uploadId" element={<JobDetailPage />} />
      </Route>
    </Routes>
  )
}

export default App
