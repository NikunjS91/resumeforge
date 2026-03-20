import { useState, useEffect } from 'react'
import api from '../api/axios'

export default function ATSScore({ resumeId, jobId, sessionId, onScored }) {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (sessionId) scoreIt()
  }, [sessionId])

  const scoreIt = async () => {
    setLoading(true)
    try {
      const res = await api.post('/api/score/ats', {
        resume_id: resumeId,
        job_id: jobId,
        session_id: sessionId
      })
      setResult(res.data)
      onScored(res.data.ats_score)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const scoreColor = (score) => {
    if (score >= 80) return 'text-green-600'
    if (score >= 60) return 'text-yellow-600'
    return 'text-red-600'
  }

  const scoreRing = (score) => {
    if (score >= 80) return 'border-green-500'
    if (score >= 60) return 'border-yellow-500'
    return 'border-red-500'
  }

  return (
    <div className="bg-white rounded-xl shadow p-6">
      <h2 className="text-lg font-semibold text-gray-800 mb-4">📊 Step 4 — ATS Score</h2>
      {loading && <p className="text-gray-500 text-sm">Scoring your resume...</p>}
      {result && (
        <div className="flex gap-6 items-start">
          {/* Score circle */}
          <div className={`flex-shrink-0 w-24 h-24 rounded-full border-4 ${scoreRing(result.ats_score)}
            flex items-center justify-center`}>
            <span className={`text-3xl font-bold ${scoreColor(result.ats_score)}`}>
              {result.ats_score}
            </span>
          </div>
          {/* Details */}
          <div className="flex-1">
            <p className="text-sm text-gray-600 mb-2">{result.recommendation}</p>
            <div className="flex gap-4 text-sm">
              <div>
                <p className="font-medium text-green-700 mb-1">✅ Matched ({result.matched_count})</p>
                <div className="flex flex-wrap gap-1">
                  {result.matched_keywords?.map(k => (
                    <span key={k} className="bg-green-100 text-green-700 text-xs px-2 py-0.5 rounded-full">{k}</span>
                  ))}
                </div>
              </div>
              {result.missing_keywords?.length > 0 && (
                <div>
                  <p className="font-medium text-red-700 mb-1">❌ Missing ({result.missing_keywords.length})</p>
                  <div className="flex flex-wrap gap-1">
                    {result.missing_keywords?.map(k => (
                      <span key={k} className="bg-red-100 text-red-700 text-xs px-2 py-0.5 rounded-full">{k}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
