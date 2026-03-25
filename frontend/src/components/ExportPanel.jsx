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
  const [loading,      setLoading]      = useState(null)
  const [previewUrl,   setPreviewUrl]   = useState(null)
  const [previewLabel, setPreviewLabel] = useState('')
  const [template,     setTemplate]     = useState('classic')

  const download = async (type) => {
    setLoading(type)
    try {
      const body = type === 'tailored'
        ? { session_id: sessionId, template }
        : { resume_id: resumeId, template }

      const res = await api.post('/api/export/pdf', body, { responseType: 'blob' })
      const blob = new Blob([res.data], { type: 'application/pdf' })
      const url  = URL.createObjectURL(blob)

      setPreviewUrl(url)
      setPreviewLabel(type === 'tailored' ? 'Tailored Resume' : 'Original Resume')

      const a = document.createElement('a')
      a.href = url
      a.download = type === 'tailored' ? 'tailored_resume.pdf' : 'original_resume.pdf'
      a.click()
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(null)
    }
  }

  return (
    <Card title="📥 Step 5 — Export PDF">

      {/* Template Selector */}
      <div className="mb-4">
        <p className="text-xs font-medium text-gray-500 mb-2">Choose template style:</p>
        <div className="grid grid-cols-3 gap-2">
          {Object.entries(TEMPLATES).map(([key, t]) => (
            <button key={key} onClick={() => setTemplate(key)}
              className={`border-2 rounded-xl p-3 text-left transition
                ${template === key
                  ? 'border-indigo-500 bg-indigo-50'
                  : 'border-gray-200 hover:border-gray-300'}`}>
              <p className="text-lg mb-1">{t.icon}</p>
              <p className="text-xs font-semibold text-gray-800">{t.name}</p>
              <p className="text-xs text-gray-400 mt-0.5 leading-tight">{t.desc}</p>
              <span className="inline-block mt-1.5 text-xs bg-gray-100 text-gray-500
                px-1.5 py-0.5 rounded-full">{t.tag}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Download Buttons */}
      <div className="flex gap-3 mb-4">
        <button onClick={() => download('tailored')} disabled={loading === 'tailored'}
          className="flex-1 bg-indigo-600 text-white py-3 rounded-xl text-sm font-medium
            hover:bg-indigo-700 disabled:opacity-40 transition">
          {loading === 'tailored' ? '⏳ Generating...' : '⬇ Download Tailored Resume'}
        </button>
        <button onClick={() => download('original')} disabled={loading === 'original'}
          className="flex-1 border-2 border-gray-200 text-gray-700 py-3 rounded-xl
            text-sm font-medium hover:border-indigo-300 disabled:opacity-40 transition">
          {loading === 'original' ? '⏳ Generating...' : '⬇ Download Original'}
        </button>
      </div>

      {/* PDF Preview */}
      {previewUrl && (
        <div className="mt-2">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-gray-700">
              Preview: {previewLabel}
              <span className="ml-2 text-xs bg-indigo-100 text-indigo-600
                px-2 py-0.5 rounded-full">
                {TEMPLATES[template].name}
              </span>
            </p>
            <a href={previewUrl} target="_blank" rel="noopener noreferrer"
              className="text-xs text-indigo-600 hover:underline">
              Open in new tab ↗
            </a>
          </div>
          <div className="border border-gray-200 rounded-xl overflow-hidden shadow-sm">
            <iframe
              src={previewUrl}
              title="Resume PDF Preview"
              className="w-full"
              style={{ height: '800px' }}
            />
          </div>
        </div>
      )}
    </Card>
  )
}
