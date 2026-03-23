import { useState, useEffect } from 'react'
import api from '../api/axios'
import { Card } from './ResumeUpload'

export default function ATSScore({ resumeId, jobId, sessionId, onScored }) {
  const [originalScore, setOriginalScore] = useState(null)
  const [tailoredScore, setTailoredScore] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => { scoreBoth() }, [sessionId])

  const scoreBoth = async () => {
    setLoading(true)
    console.log('🔍 ATSScore: Starting scoreBoth()', { resumeId, jobId, sessionId })
    
    try {
      // Score original resume first
      console.log('📊 Scoring original resume:', { resume_id: resumeId, job_id: jobId })
      const origRes = await api.post('/api/score/ats', {
        resume_id: resumeId, job_id: jobId
      })
      console.log('✅ Original score received:', origRes.data)
      setOriginalScore(origRes.data)

      // Then score tailored resume
      console.log('📊 Scoring tailored resume:', { resume_id: resumeId, job_id: jobId, session_id: sessionId })
      const tailRes = await api.post('/api/score/ats', {
        resume_id: resumeId, job_id: jobId, session_id: sessionId
      })
      console.log('✅ Tailored score received:', tailRes.data)
      setTailoredScore(tailRes.data)
      onScored(tailRes.data.ats_score)
    } catch (e) {
      console.error('❌ ATSScore error:', e)
      console.error('Error details:', e.response?.data)
      setTailoredScore({
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
    <Card title="📊 Step 4 — ATS Score Comparison">
      {loading && <p className="text-gray-400 text-sm">Scoring original and tailored resumes...</p>}
      
      {/* Show helpful message if both scores are 0 (no required skills) */}
      {tailoredScore && originalScore && tailoredScore.ats_score === 0 && originalScore.ats_score === 0 && (
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

      {tailoredScore && (
        <div className="space-y-4">
          {/* Score Comparison */}
          <div className="flex items-center gap-4 justify-center">
            {/* Original Score */}
            {originalScore && (
              <div className="flex flex-col items-center">
                <p className="text-xs text-gray-500 mb-2">Original</p>
                <div className="w-20 h-20 rounded-full border-4 border-gray-300 flex items-center justify-center">
                  <span className="text-2xl font-bold text-gray-600">{originalScore.ats_score}</span>
                </div>
              </div>
            )}

            {/* Arrow */}
            <div className="text-gray-400 text-2xl">→</div>

            {/* Tailored Score */}
            <div className="flex flex-col items-center">
              <p className="text-xs text-gray-500 mb-2">Tailored</p>
              <div className={`w-20 h-20 rounded-full border-4 ${ring(tailoredScore.ats_score)} flex items-center justify-center`}>
                <span className="text-2xl font-bold" style={{color: color(tailoredScore.ats_score)}}>
                  {tailoredScore.ats_score}
                </span>
              </div>
            </div>

            {/* Delta Badge */}
            {originalScore && (
              <div className="flex flex-col items-center">
                <p className="text-xs text-gray-500 mb-2">Change</p>
                <div className={`px-3 py-2 rounded-lg font-bold text-lg ${
                  tailoredScore.ats_score > originalScore.ats_score 
                    ? 'bg-green-100 text-green-700' 
                    : tailoredScore.ats_score < originalScore.ats_score
                    ? 'bg-red-100 text-red-700'
                    : 'bg-gray-100 text-gray-700'
                }`}>
                  {tailoredScore.ats_score > originalScore.ats_score ? '+' : ''}
                  {tailoredScore.ats_score - originalScore.ats_score}
                </div>
              </div>
            )}
          </div>

          {/* Recommendation */}
          <p className="text-sm text-gray-600 text-center">{tailoredScore.recommendation}</p>

          {/* Keywords */}
          <div className="space-y-2">
            {tailoredScore.matched_keywords?.length > 0 && (
              <div>
                <p className="text-xs font-medium text-green-700 mb-1">✅ Matched ({tailoredScore.matched_count})</p>
                <div className="flex flex-wrap gap-1">
                  {tailoredScore.matched_keywords.map(k => (
                    <span key={k} className="bg-green-100 text-green-700 text-xs px-2 py-0.5 rounded-full">{k}</span>
                  ))}
                </div>
              </div>
            )}
            {tailoredScore.missing_keywords?.length > 0 && (
              <div>
                <p className="text-xs font-medium text-red-700 mb-1">❌ Missing ({tailoredScore.missing_keywords.length})</p>
                <div className="flex flex-wrap gap-1">
                  {tailoredScore.missing_keywords.map(k => (
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
