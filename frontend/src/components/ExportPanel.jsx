import { useState } from 'react'
import api from '../api/axios'
import { Card } from './ResumeUpload'

export default function ExportPanel({ resumeId, sessionId }) {
  const [loading,    setLoading]    = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [previewLabel, setPreviewLabel] = useState('')

  const download = async (type) => {
    setLoading(type)
    try {
      const body = type === 'tailored' ? { session_id: sessionId } : { resume_id: resumeId }
      const res  = await api.post('/api/export/pdf', body, { responseType: 'blob' })
      const blob = new Blob([res.data], { type: 'application/pdf' })
      const url  = URL.createObjectURL(blob)

      // Show preview
      setPreviewUrl(url)
      setPreviewLabel(type === 'tailored' ? 'Tailored Resume' : 'Original Resume')

      // Also trigger download
      const a = document.createElement('a')
      a.href = url
      a.download = type === 'tailored' ? 'tailored_resume.pdf' : 'original_resume.pdf'
      a.click()
    } catch (e) {
      console.error(e)
    } finally { setLoading(null) }
  }

  return (
    <Card title="📥 Step 5 — Export PDF">
      <div className="flex gap-3 mb-4">
        <button onClick={() => download('tailored')} disabled={loading === 'tailored'}
          className="flex-1 bg-indigo-600 text-white py-3 rounded-xl text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 transition">
          {loading === 'tailored' ? '⏳ Generating...' : '⬇ Download Tailored Resume'}
        </button>
        <button onClick={() => download('original')} disabled={loading === 'original'}
          className="flex-1 border-2 border-gray-200 text-gray-700 py-3 rounded-xl text-sm font-medium hover:border-indigo-300 disabled:opacity-40 transition">
          {loading === 'original' ? '⏳ Generating...' : '⬇ Download Original'}
        </button>
      </div>

      {/* PDF Preview — Overleaf-style */}
      {previewUrl && (
        <div className="mt-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-gray-700">Preview: {previewLabel}</p>
            <a href={previewUrl} target="_blank" rel="noopener noreferrer"
              className="text-xs text-indigo-600 hover:underline">Open in new tab ↗</a>
          </div>
          <div className="border border-gray-200 rounded-xl overflow-hidden shadow-sm">
            <iframe
              src={previewUrl}
              title="Resume PDF Preview"
              className="w-full"
              style={{ height: '800px' }}
            />
          </div>
        </div>
      )}
    </Card>
  )
}
