import { useState } from 'react'
import api from '../api/axios'

export default function TailorPanel({ resumeId, jobId, onTailored }) {
  const [provider, setProvider] = useState('ollama')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleTailor = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.post('/api/tailor/resume', { resume_id: resumeId, job_id: jobId, provider })
      setResult(res.data)
      onTailored(res.data.session_id)
    } catch (e) {
      setError(e.response?.data?.detail || 'Tailoring failed')
    } finally {
      setLoading(false)
    }
  }

  const providerInfo = {
    ollama: { label: 'Local (Ollama)', desc: 'qwen3:14b · ~2-3 min · 100% private', color: 'green' },
    nvidia: { label: 'NVIDIA NIM', desc: 'llama-3.3-70b · ~15-20s · cloud', color: 'blue' },
  }

  return (
    <div className="bg-white rounded-xl shadow p-6">
      <h2 className="text-lg font-semibold text-gray-800 mb-4">✂️ Step 3 — Tailor Resume</h2>
      {!result ? (
        <div className="space-y-4">
          {/* Provider selector */}
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(providerInfo).map(([key, info]) => (
              <button key={key} onClick={() => setProvider(key)}
                className={`border-2 rounded-lg p-3 text-left transition
                  ${provider === key
                    ? `border-${info.color}-500 bg-${info.color}-50`
                    : 'border-gray-200 hover:border-gray-300'}`}>
                <p className="font-medium text-sm text-gray-800">{info.label}</p>
                <p className="text-xs text-gray-500 mt-1">{info.desc}</p>
              </button>
            ))}
          </div>
          {provider === 'ollama' && (
            <p className="text-xs text-amber-600 bg-amber-50 px-3 py-2 rounded-lg">
              ⏱ Local mode takes 2-3 minutes. Keep this window open.
            </p>
          )}
          <button onClick={handleTailor} disabled={loading}
            className="w-full bg-indigo-600 text-white py-2 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 transition">
            {loading
              ? `Tailoring with ${providerInfo[provider].label}...`
              : `Tailor with ${providerInfo[provider].label}`}
          </button>
          {loading && provider === 'ollama' && (
            <div className="w-full bg-gray-200 rounded-full h-1.5">
              <div className="bg-indigo-600 h-1.5 rounded-full animate-pulse w-1/3" />
            </div>
          )}
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </div>
      ) : (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <p className="text-green-700 font-medium">✅ Resume tailored with {result.ai_model}</p>
          <p className="text-sm text-gray-600 mt-1">{result.sections_tailored} sections improved</p>
          <ul className="mt-2 space-y-1">
            {result.improvement_notes?.slice(0, 3).map((note, i) => (
              <li key={i} className="text-xs text-gray-600">• {note}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
