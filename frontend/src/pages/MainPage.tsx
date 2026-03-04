import { useState } from 'react'
import { JobList } from '../components/JobList'
import { UploadForm } from '../components/UploadForm'

export function MainPage() {
  const [refreshKey, setRefreshKey] = useState(0)

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <UploadForm onJobCreated={() => setRefreshKey(k => k + 1)} />
      <hr />
      <JobList refreshKey={refreshKey} />
    </div>
  )
}
