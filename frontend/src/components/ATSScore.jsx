import { useState, useEffect } from 'react'
import api from '../api/axios'
import { Card } from './ResumeUpload'

export default function ATSScore({ resumeId, jobId, sessionId, onScored }) {
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => { score() }, [sessionId])

  const score = async () => {
    setLoading(true)
    try {
      const res = await api.post('/api/score/ats', {
        resume_id: resumeId, job_id: jobId, session_id: sessionId
      })
      setResult(res.data)
      onScored(res.data.ats_score)
    } catch (e) {
      console.error(e)
      setResult({
        ats_score: 0,
        recommendation: 'Run a fresh JD analysis with required skills to get a score.',
        matched_keywords: [], missing_keywords: [],
        matched_count: 0, required_count: 0
      })
    }
    finally { setLoading(false) }
  }

  const color = (s) => s >= 80 ? '#22c55e' : s >= 60 ? '#f59e0b' : '#ef4444'
  const ring  = (s) => s >= 80 ? 'border-green-400' : s >= 60 ? 'border-yellow-400' : 'border-red-400'

  return (
    <Card title="📊 Step 4 — ATS Score">
      {loading && <p className="text-gray-400 text-sm">Scoring against job requirements...</p>}
      {result && (
        <div className="flex gap-5 items-start">
          <div className={`w-20 h-20 rounded-full border-4 ${ring(result.ats_score)} flex-shrink-0
            flex items-center justify-center`}>
            <span className="text-2xl font-bold" style={{color: color(result.ats_score)}}>
              {result.ats_score}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-gray-600 mb-2">{result.recommendation}</p>
            <div className="space-y-2">
              {result.matched_keywords?.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-green-700 mb-1">✅ Matched ({result.matched_count})</p>
                  <div className="flex flex-wrap gap-1">
                    {result.matched_keywords.map(k => (
                      <span key={k} className="bg-green-100 text-green-700 text-xs px-2 py-0.5 rounded-full">{k}</span>
                    ))}
                  </div>
                </div>
              )}
              {result.missing_keywords?.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-red-700 mb-1">❌ Missing ({result.missing_keywords.length})</p>
                  <div className="flex flex-wrap gap-1">
                    {result.missing_keywords.map(k => (
                      <span key={k} className="bg-red-100 text-red-700 text-xs px-2 py-0.5 rounded-full">{k}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </Card>
  )
}
