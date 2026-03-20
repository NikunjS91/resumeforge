import { useState } from 'react'
import api from '../api/axios'

export default function ExportButton({ resumeId, sessionId }) {
  const [loading, setLoading] = useState(null) // 'original' | 'tailored' | null

  const download = async (type) => {
    setLoading(type)
    try {
      const body = type === 'tailored' ? { session_id: sessionId } : { resume_id: resumeId }
      const res = await api.post('/api/export/pdf', body, { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
      const a = document.createElement('a')
      a.href = url
      a.download = type === 'tailored' ? 'tailored_resume.pdf' : 'original_resume.pdf'
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="bg-white rounded-xl shadow p-6">
      <h2 className="text-lg font-semibold text-gray-800 mb-4">📥 Step 5 — Download PDF</h2>
      <div className="flex gap-3">
        <button onClick={() => download('tailored')} disabled={loading === 'tailored'}
          className="flex-1 bg-indigo-600 text-white py-3 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 transition">
          {loading === 'tailored' ? 'Generating...' : '⬇ Download Tailored Resume'}
        </button>
        <button onClick={() => download('original')} disabled={loading === 'original'}
          className="flex-1 border-2 border-gray-300 text-gray-700 py-3 rounded-lg font-medium hover:border-indigo-400 disabled:opacity-50 transition">
          {loading === 'original' ? 'Generating...' : '⬇ Download Original'}
        </button>
      </div>
    </div>
  )
}
