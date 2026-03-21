import { useState } from 'react'
import api from '../api/axios'
import { Card, Success } from './ResumeUpload'

const PROVIDERS = {
  ollama: { label: 'Local — Ollama',    model: 'qwen3:14b',               time: '~2-3 min', color: 'green', private: true },
  nvidia: { label: 'NVIDIA NIM',        model: 'llama-3.3-70b-instruct',  time: '~15-20s',  color: 'blue',  private: false },
}

export default function TailorPanel({ resumeId, jobId, onTailored }) {
  const [provider, setProvider] = useState('ollama')
  const [result,   setResult]   = useState(null)
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState('')

  const handle = async () => {
    setLoading(true); setError('')
    try {
      const res = await api.post('/api/tailor/resume', {
        resume_id: resumeId, job_id: jobId, provider
      })
      setResult(res.data)
      onTailored(res.data.session_id)
    } catch (e) {
      setError(e.response?.data?.detail || 'Tailoring failed')
    } finally { setLoading(false) }
  }

  return (
    <Card title="✂️ Step 3 — Tailor Resume">
      {!result ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(PROVIDERS).map(([key, p]) => (
              <button key={key} onClick={() => setProvider(key)}
                className={`border-2 rounded-xl p-3 text-left transition
                  ${provider === key ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200 hover:border-gray-300'}`}>
                <p className="font-medium text-sm text-gray-800">{p.label}</p>
                <p className="text-xs text-gray-400 mt-0.5">{p.model}</p>
                <div className="flex gap-2 mt-1.5">
                  <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">⏱ {p.time}</span>
                  {p.private && <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">🔒 private</span>}
                </div>
              </button>
            ))}
          </div>
          {provider === 'ollama' && (
            <p className="text-xs text-amber-600 bg-amber-50 px-3 py-2 rounded-lg">
              ⏱ Local mode takes 2-3 minutes. Keep this tab open and wait.
            </p>
          )}
          <button onClick={handle} disabled={loading}
            className="w-full bg-indigo-600 text-white py-2.5 rounded-xl text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 transition">
            {loading ? `Tailoring with ${PROVIDERS[provider].label}...` : `Tailor with ${PROVIDERS[provider].label}`}
          </button>
          {loading && (
            <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
              <div className="bg-indigo-500 h-1.5 rounded-full animate-pulse" style={{width: '60%'}} />
            </div>
          )}
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </div>
      ) : (
        <Success title={`Tailored with ${result.ai_model}`}
          subtitle={`${result.sections_tailored} sections improved`}>
          <ul className="mt-2 space-y-1">
            {result.improvement_notes?.slice(0, 3).map((n, i) => (
              <li key={i} className="text-xs text-gray-600">• {n}</li>
            ))}
          </ul>
        </Success>
      )}
    </Card>
  )
}
