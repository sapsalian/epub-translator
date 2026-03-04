import { useState } from 'react'
import { Link } from 'react-router-dom'
import { JobList } from '../components/JobList'
import { UploadForm } from '../components/UploadForm'

export function MainPage() {
  const [refreshKey, setRefreshKey] = useState(0)

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">EPUB Translator</h1>
        <Link to="/settings" className="text-blue-600 hover:underline text-sm">Settings</Link>
      </div>
      <UploadForm onJobCreated={() => setRefreshKey(k => k + 1)} />
      <hr />
      <JobList refreshKey={refreshKey} />
    </div>
  )
}
