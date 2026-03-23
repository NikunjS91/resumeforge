import { useState } from 'react'
import api from '../api/axios'
import { Card, Success } from './ResumeUpload'

export default function JobInput({ onAnalyze }) {
  const [text,    setText]    = useState('')
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  const handle = async () => {
    if (!text.trim()) return
    setLoading(true); setError('')
    try {
      const res = await api.post('/api/analyze/job', { jd_text: text })
      setResult(res.data)
      onAnalyze(res.data.job_id)
    } catch (e) {
      setError(e.response?.data?.detail || 'Analysis failed')
    } finally { setLoading(false) }
  }

  return (
    <Card title="🔍 Step 2 — Analyze Job Description">
      {!result ? (
        <div className="space-y-3">
          <textarea rows={5} value={text} onChange={e => setText(e.target.value)}
            placeholder="Paste the full job description here..."
            className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none" />
          <button onClick={handle} disabled={!text.trim() || loading}
            className="w-full bg-indigo-600 text-white py-2.5 rounded-xl text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 transition">
            {loading ? 'Analyzing...' : 'Analyze JD'}
          </button>
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </div>
      ) : (
        <>
          <Success title={`${result.job_title || 'Role'} at ${result.company_name || 'Company'}`}
            subtitle={`${result.required_count} required · ${result.nicetohave_count} nice-to-have`}>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {result.required_skills?.slice(0, 12).map(s => (
                <span key={s} className="bg-blue-100 text-blue-700 text-xs px-2.5 py-0.5 rounded-full">{s}</span>
              ))}
            </div>
          </Success>
          <button onClick={() => setResult(null)}
            className="w-full mt-3 bg-gray-100 text-gray-700 py-2 rounded-xl text-sm font-medium hover:bg-gray-200 transition">
            🔄 Analyze Different JD
          </button>
        </>
      )}
    </Card>
  )
}
