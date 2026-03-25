import { useState, useEffect } from 'react'
import api from '../api/axios'

export default function History() {
  const [sessions, setSessions] = useState([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState('')

  useEffect(() => { loadHistory() }, [])

  const loadHistory = async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/history/')
      setSessions(res.data.sessions || [])
    } catch (e) {
      setError('Failed to load history')
    } finally {
      setLoading(false)
    }
  }

  const downloadPdf = async (sessionId, resumeName) => {
    try {
      const res = await api.get(`/api/history/${sessionId}/pdf`, { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
      const a = document.createElement('a')
      a.href = url
      a.download = `ResumeForge_${resumeName}_session${sessionId}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      alert('PDF not available — please re-export from the Pipeline tab')
    }
  }

  const scoreColor = (score) => {
    if (!score) return 'text-gray-400'
    if (score >= 80) return 'text-green-600'
    if (score >= 60) return 'text-yellow-600'
    return 'text-red-500'
  }

  const scoreRing = (score) => {
    if (!score) return 'border-gray-200'
    if (score >= 80) return 'border-green-400'
    if (score >= 60) return 'border-yellow-400'
    return 'border-red-400'
  }

  const modelLabel = (model) => {
    if (!model || model === 'unknown') return '❓ Unknown'
    if (model.includes('llama') || model.includes('nvidia')) return '⚡ NVIDIA NIM'
    if (model.includes('qwen') || model.includes('ollama')) return '🔒 Local Ollama'
    return model
  }

  const formatDate = (dateStr) => {
    if (!dateStr) return ''
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric'
      })
    } catch { return dateStr }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400 text-sm">Loading history...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-500 text-sm">{error}</div>
      </div>
    )
  }

  if (sessions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-center">
        <p className="text-4xl mb-3">📭</p>
        <p className="text-gray-500 font-medium">No tailoring sessions yet</p>
        <p className="text-gray-400 text-sm mt-1">Run the pipeline to see your history here</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-base font-semibold text-gray-700">
          {sessions.length} tailoring {sessions.length === 1 ? 'session' : 'sessions'}
        </h2>
        <button onClick={loadHistory}
          className="text-xs text-indigo-600 hover:underline">
          ↻ Refresh
        </button>
      </div>

      {sessions.map(session => (
        <div key={session.session_id}
          className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">

          {/* Header row */}
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-gray-800 text-sm truncate">
                {session.job_title || 'Unknown Role'}
                {session.company_name && (
                  <span className="text-gray-400 font-normal"> at {session.company_name}</span>
                )}
              </p>
              <p className="text-xs text-gray-400 mt-0.5">
                📄 {session.resume_name}
                {session.created_at && (
                  <span className="ml-2">· {formatDate(session.created_at)}</span>
                )}
              </p>
            </div>

            {/* ATS Score */}
            <div className={`flex-shrink-0 w-14 h-14 rounded-full border-2
              ${scoreRing(session.ats_score)} flex items-center justify-center`}>
              <span className={`text-lg font-bold ${scoreColor(session.ats_score)}`}>
                {session.ats_score || '—'}
              </span>
            </div>
          </div>

          {/* Meta row */}
          <div className="flex flex-wrap gap-2 mt-3">
            <span className="bg-gray-100 text-gray-600 text-xs px-2.5 py-1 rounded-full">
              {modelLabel(session.ai_model)}
            </span>
            {session.sections_tailored > 0 && (
              <span className="bg-indigo-50 text-indigo-600 text-xs px-2.5 py-1 rounded-full">
                ✂️ {session.sections_tailored} sections improved
              </span>
            )}
            {session.notes_count > 0 && (
              <span className="bg-blue-50 text-blue-600 text-xs px-2.5 py-1 rounded-full">
                💡 {session.notes_count} improvements
              </span>
            )}
          </div>

          {/* Action row */}
          <div className="flex gap-2 mt-3">
            {session.has_pdf ? (
              <button
                onClick={() => downloadPdf(session.session_id, session.resume_name)}
                className="flex-1 bg-indigo-600 text-white text-xs py-2 rounded-xl
                  font-medium hover:bg-indigo-700 transition">
                ⬇ Download PDF
              </button>
            ) : (
              <button disabled
                className="flex-1 bg-gray-100 text-gray-400 text-xs py-2 rounded-xl
                  font-medium cursor-not-allowed">
                No PDF yet — re-export from Pipeline
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
