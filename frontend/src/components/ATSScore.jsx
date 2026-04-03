import { useState, useEffect } from 'react'
import api from '../api/axios'
import { Card } from './ResumeUpload'

// Module-level stores — survive React remounts (StrictMode double-invoke, tab switch, step rerender)
// _pending: sessionId → Promise<[origRes, tailRes]>  (in-flight or resolved)
// _results: sessionId → { original, tailored }        (completed)
const _pending = new Map()
const _results = new Map()

export default function ATSScore({ resumeId, jobId, sessionId, onScored }) {
  const cached = _results.get(sessionId) ?? null
  const [original, setOriginal] = useState(cached?.original ?? null)
  const [tailored, setTailored] = useState(cached?.tailored ?? null)
  const [loading,  setLoading]  = useState(cached === null)

  useEffect(() => {
    let cancelled = false

    // State already initialized from cache in useState above — nothing to do
    if (_results.has(sessionId)) return

    if (!_pending.has(sessionId)) {
      // First caller — create the shared promise (both requests in parallel)
      _pending.set(
        sessionId,
        Promise.all([
          api.post('/api/score/ats', { resume_id: resumeId, job_id: jobId }),
          api.post('/api/score/ats', { resume_id: resumeId, job_id: jobId, session_id: sessionId }),
        ])
      )
    }

    // Subscribe to the shared in-flight promise (safe for concurrent mounts / StrictMode)
    _pending.get(sessionId)
      .then(([origRes, tailRes]) => {
        if (cancelled) return
        const r = { original: origRes.data, tailored: tailRes.data }
        _results.set(sessionId, r)
        setOriginal(r.original)
        setTailored(r.tailored)
        setLoading(false)
        onScored(r.tailored.ats_score)
      })
      .catch(() => {
        if (cancelled) return
        // Remove pending so a retry is possible on the next render
        _pending.delete(sessionId)
        const fallback = {
          ats_score: 0,
          recommendation: 'Run a fresh JD analysis with required skills to get a score.',
          matched_keywords: [],
          missing_keywords: [],
          matched_count: 0,
          required_count: 0,
        }
        setTailored(fallback)
        setLoading(false)
      })

    return () => { cancelled = true }
  // resumeId/jobId are stable per session — intentionally omitted to avoid recreating the promise
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  const color = (s) => s >= 80 ? '#22c55e' : s >= 60 ? '#f59e0b' : '#ef4444'
  const ring  = (s) => s >= 80 ? 'border-green-400' : s >= 60 ? 'border-yellow-400' : 'border-red-400'

  return (
    <Card title="📊 Step 4 — ATS Score Comparison">
      {loading && <p className="text-gray-400 text-sm">Scoring original and tailored resumes...</p>}

      {/* No required skills warning */}
      {tailored && original && tailored.ats_score === 0 && original.ats_score === 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
          <p className="text-sm text-amber-800 font-medium mb-2">⚠️ Job description has no required skills to score against</p>
          <p className="text-xs text-amber-700">
            Please analyze a new job description that includes required skills in this format:
          </p>
          <p className="text-xs text-amber-900 font-mono bg-amber-100 px-2 py-1 rounded mt-2">
            Requirements: skill1, skill2, skill3...
          </p>
        </div>
      )}

      {tailored && (
        <div className="space-y-4">
          {/* Score comparison */}
          <div className="flex items-center gap-4 justify-center">
            {original && (
              <div className="flex flex-col items-center">
                <p className="text-xs text-gray-500 mb-2">Original</p>
                <div className="w-20 h-20 rounded-full border-4 border-gray-300 flex items-center justify-center">
                  <span className="text-2xl font-bold text-gray-600">{original.ats_score}</span>
                </div>
              </div>
            )}

            <div className="text-gray-400 text-2xl">→</div>

            <div className="flex flex-col items-center">
              <p className="text-xs text-gray-500 mb-2">Tailored</p>
              <div className={`w-20 h-20 rounded-full border-4 ${ring(tailored.ats_score)} flex items-center justify-center`}>
                <span className="text-2xl font-bold" style={{ color: color(tailored.ats_score) }}>
                  {tailored.ats_score}
                </span>
              </div>
            </div>

            {original && (
              <div className="flex flex-col items-center">
                <p className="text-xs text-gray-500 mb-2">Change</p>
                <div className={`px-3 py-2 rounded-lg font-bold text-lg ${
                  tailored.ats_score > original.ats_score
                    ? 'bg-green-100 text-green-700'
                    : tailored.ats_score < original.ats_score
                    ? 'bg-red-100 text-red-700'
                    : 'bg-gray-100 text-gray-700'
                }`}>
                  {tailored.ats_score > original.ats_score ? '+' : ''}
                  {tailored.ats_score - original.ats_score}
                </div>
              </div>
            )}
          </div>

          {/* Recommendation */}
          <p className="text-sm text-gray-600 text-center">{tailored.recommendation}</p>

          {/* Keyword breakdown */}
          <div className="space-y-2">
            {tailored.matched_keywords?.length > 0 && (
              <div>
                <p className="text-xs font-medium text-green-700 mb-1">✅ Matched ({tailored.matched_count})</p>
                <div className="flex flex-wrap gap-1">
                  {tailored.matched_keywords.map(k => (
                    <span key={k} className="bg-green-100 text-green-700 text-xs px-2 py-0.5 rounded-full">{k}</span>
                  ))}
                </div>
              </div>
            )}
            {tailored.missing_keywords?.length > 0 && (
              <div>
                <p className="text-xs font-medium text-red-700 mb-1">❌ Missing ({tailored.missing_keywords.length})</p>
                <div className="flex flex-wrap gap-1">
                  {tailored.missing_keywords.map(k => (
                    <span key={k} className="bg-red-100 text-red-700 text-xs px-2 py-0.5 rounded-full">{k}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  )
}
