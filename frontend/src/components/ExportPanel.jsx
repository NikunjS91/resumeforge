import { useState } from 'react'
import api from '../api/axios'
import { Card } from './ResumeUpload'

const TEMPLATES = {
  classic: {
    name: 'Classic',
    icon: '🏛️',
    desc: 'Dark navy header, tabular skills',
    tag: 'Tech / Engineering'
  },
  minimal: {
    name: 'Minimal',
    icon: '⬜',
    desc: 'Clean, no colors, max ATS safety',
    tag: 'Finance / Corporate'
  },
  modern: {
    name: 'Modern',
    icon: '✨',
    desc: 'Blue accent bar, colored bullets',
    tag: 'Startup / Creative'
  }
}

export default function ExportPanel({ resumeId, sessionId }) {
  const [previews,      setPreviews]      = useState({})
  const [loading,       setLoading]       = useState({})
  const [stages,        setStages]        = useState({})
  const [errors,        setErrors]        = useState({})
  const [errorMessages, setErrorMessages] = useState({})
  const [selected,      setSelected]      = useState('classic')

  const body = sessionId ? { session_id: sessionId } : { resume_id: resumeId }

  const pollStatus = (job_id, tpl) => new Promise((resolve, reject) => {
    const deadline = Date.now() + 600000  // 10 min max (full 2-stage LLM generation can take 6-8 min)
    const iv = setInterval(async () => {
      try {
        const res = await api.get(`/api/export/status/${job_id}`)
        const { status, stage, error } = res.data
        if (stage) setStages(prev => ({ ...prev, [tpl]: stage }))
        if (status === 'done') { clearInterval(iv); resolve() }
        else if (status === 'error') { clearInterval(iv); reject(new Error(error || 'Export failed')) }
        else if (Date.now() > deadline) { clearInterval(iv); reject(new Error('Export timed out after 10 minutes')) }
      } catch (e) { clearInterval(iv); reject(e) }
    }, 3000)
  })

  const generateTemplate = async (tpl) => {
    if (loading[tpl] || previews[tpl]) return
    setLoading(prev => ({ ...prev, [tpl]: true }))
    setStages(prev => ({ ...prev, [tpl]: 'Submitting...' }))
    setErrors(prev => ({ ...prev, [tpl]: false }))
    try {
      // 1. Submit job — returns immediately with job_id
      const jobRes = await api.post('/api/export/pdf/async', { ...body, template: tpl })
      const { job_id } = jobRes.data

      // 2. Poll for progress (updates stage label every 3s)
      await pollStatus(job_id, tpl)

      // 3. Fetch completed PDF blob
      setStages(prev => ({ ...prev, [tpl]: 'Downloading PDF...' }))
      const pdfRes = await api.get(`/api/export/result/${job_id}`, { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([pdfRes.data], { type: 'application/pdf' }))
      setPreviews(prev => ({ ...prev, [tpl]: url }))
    } catch (e) {
      console.error(`Failed to generate ${tpl}:`, e)
      const msg = e.message?.includes('timed out')
        ? e.message
        : e.response?.data?.detail || e.message || 'Generation failed. Check backend logs.'
      setErrors(prev => ({ ...prev, [tpl]: true }))
      setErrorMessages(prev => ({ ...prev, [tpl]: msg }))
    } finally {
      setLoading(prev => ({ ...prev, [tpl]: false }))
      setStages(prev => ({ ...prev, [tpl]: '' }))
    }
  }

  const handleDownload = () => {
    if (!previews[selected]) return
    const a = document.createElement('a')
    a.href = previews[selected]
    a.download = `resume_${selected}.pdf`
    a.click()
  }

  const getStatusIndicator = (tpl) => {
    if (loading[tpl])  return <span className="absolute top-2 right-2 animate-spin text-sm">⏳</span>
    if (errors[tpl])   return <span className="absolute top-2 right-2 text-red-500 text-sm">❌</span>
    if (previews[tpl]) return <span className="absolute top-2 right-2 text-green-500 text-sm">✅</span>
    return null
  }

  return (
    <Card title="📥 Step 5 — Export PDF">

      {/* Template Selector Cards */}
      <div className="mb-4">
        <p className="text-xs font-medium text-gray-500 mb-2">Choose template style:</p>
        <div className="grid grid-cols-3 gap-2">
          {Object.entries(TEMPLATES).map(([key, t]) => (
            <button
              key={key}
              onClick={() => setSelected(key)}
              className={`border-2 rounded-xl p-3 text-left transition relative
                ${selected === key
                  ? 'border-indigo-500 bg-indigo-50'
                  : 'border-gray-200 hover:border-gray-300'}
                ${errors[key] ? 'opacity-50' : ''}`}
            >
              {getStatusIndicator(key)}
              <p className="text-lg mb-1">{t.icon}</p>
              <p className="text-xs font-semibold text-gray-800">{t.name}</p>
              <p className="text-xs text-gray-400 mt-0.5 leading-tight">{t.desc}</p>
              <span className="inline-block mt-1.5 text-xs bg-gray-100 text-gray-500
                px-1.5 py-0.5 rounded-full">{t.tag}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Generate / Download Buttons */}
      <div className="flex gap-3 mb-4">
        {!previews[selected] ? (
          <button
            onClick={() => generateTemplate(selected)}
            disabled={loading[selected]}
            className="flex-1 bg-indigo-600 text-white py-3 rounded-xl text-sm font-medium
              hover:bg-indigo-700 disabled:opacity-40 transition"
          >
            {loading[selected]
              ? `⏳ ${stages[selected] || `Generating ${TEMPLATES[selected].name}...`}`
              : `Generate ${TEMPLATES[selected].name} Preview`}
          </button>
        ) : (
          <button
            onClick={handleDownload}
            className="flex-1 bg-green-600 text-white py-3 rounded-xl text-sm font-medium
              hover:bg-green-700 transition"
          >
            ⬇ Download {TEMPLATES[selected].name} Resume
          </button>
        )}
      </div>

      {/* PDF Preview */}
      <div className="mt-2">
        <div className="flex items-center justify-between mb-2">
          <p className="text-sm font-medium text-gray-700">
            Preview:
            <span className="ml-2 text-xs bg-indigo-100 text-indigo-600 px-2 py-0.5 rounded-full">
              {TEMPLATES[selected].name}
            </span>
          </p>
          {previews[selected] && (
            <a href={previews[selected]} target="_blank" rel="noopener noreferrer"
              className="text-xs text-indigo-600 hover:underline">
              Open in new tab ↗
            </a>
          )}
        </div>

        <div className="border border-gray-200 rounded-xl overflow-hidden shadow-sm bg-gray-50">
          {loading[selected] ? (
            <div className="w-full flex flex-col items-center justify-center text-gray-400"
              style={{ height: '800px' }}>
              <div className="animate-spin text-4xl mb-4">⏳</div>
              <p className="text-sm font-medium">{stages[selected] || `Generating ${TEMPLATES[selected].name}...`}</p>
              <p className="text-xs text-gray-300 mt-1">This may take 1-3 minutes</p>
            </div>
          ) : errors[selected] ? (
            <div className="w-full flex flex-col items-center justify-center text-red-400"
              style={{ height: '400px' }}>
              <p className="text-4xl mb-4">❌</p>
              <p className="text-sm">Failed to generate {TEMPLATES[selected].name} template</p>
              {errorMessages[selected] && (
                <p className="text-xs text-red-300 mt-1 px-4 text-center">{errorMessages[selected]}</p>
              )}
              <button onClick={() => {
                setErrors(prev => ({ ...prev, [selected]: false }))
                setErrorMessages(prev => ({ ...prev, [selected]: null }))
                generateTemplate(selected)
              }} className="mt-3 text-xs text-indigo-600 hover:underline">
                Retry
              </button>
            </div>
          ) : previews[selected] ? (
            <iframe
              src={previews[selected]}
              title={`Resume PDF Preview - ${TEMPLATES[selected].name}`}
              className="w-full"
              style={{ height: '800px' }}
            />
          ) : (
            <div className="w-full flex flex-col items-center justify-center text-gray-300"
              style={{ height: '400px' }}>
              <p className="text-4xl mb-4">📄</p>
              <p className="text-sm">Click "Generate Preview" to render this template</p>
            </div>
          )}
        </div>
      </div>
    </Card>
  )
}
