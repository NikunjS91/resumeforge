import { useState } from 'react'
import api from '../api/axios'

export default function JobInput({ onAnalyze }) {
  const [jdText, setJdText] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleAnalyze = async () => {
    if (!jdText.trim()) return
    setLoading(true)
    setError('')
    try {
      const res = await api.post('/api/analyze/job', { jd_text: jdText })
      setResult(res.data)
      onAnalyze(res.data.job_id)
    } catch (e) {
      setError(e.response?.data?.detail || 'Analysis failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-xl shadow p-6">
      <h2 className="text-lg font-semibold text-gray-800 mb-4">🔍 Step 2 — Analyze Job Description</h2>
      {!result ? (
        <div className="space-y-3">
          <textarea rows={6} value={jdText}
            onChange={e => setJdText(e.target.value)}
            placeholder="Paste the full job description here..."
            className="w-full border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none" />
          <button onClick={handleAnalyze} disabled={!jdText.trim() || loading}
            className="bg-indigo-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 transition">
            {loading ? 'Analyzing...' : 'Analyze JD'}
          </button>
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </div>
      ) : (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <p className="text-green-700 font-medium">✅ {result.job_title} at {result.company_name}</p>
          <p className="text-sm text-gray-600 mt-1">
            {result.required_count} required skills · {result.nicetohave_count} nice-to-have
          </p>
          <div className="flex flex-wrap gap-2 mt-2">
            {result.required_skills?.slice(0, 10).map(s => (
              <span key={s} className="bg-blue-100 text-blue-700 text-xs px-2 py-1 rounded-full">{s}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
