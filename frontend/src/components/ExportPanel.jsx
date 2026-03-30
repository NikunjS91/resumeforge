import { useState, useEffect } from 'react'
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
  const [previews, setPreviews] = useState({ classic: null, minimal: null, modern: null })
  const [loading, setLoading] = useState({ classic: false, minimal: false, modern: false })
  const [errors, setErrors] = useState({ classic: false, minimal: false, modern: false })
  const [selected, setSelected] = useState('classic')
  const [hasFetched, setHasFetched] = useState(false)

  // Pre-fetch all 3 templates in parallel when component mounts or IDs change
  useEffect(() => {
    if (!sessionId && !resumeId) return
    if (hasFetched) return // Don't re-fetch if already done

    const body = sessionId ? { session_id: sessionId } : { resume_id: resumeId }

    // Set all to loading
    setLoading({ classic: true, minimal: true, modern: true })
    setErrors({ classic: false, minimal: false, modern: false })
    setHasFetched(true)

    // Fetch all 3 templates in parallel
    ;['classic', 'minimal', 'modern'].forEach(async (tpl) => {
      try {
        const res = await api.post('/api/export/pdf',
          { ...body, template: tpl },
          { responseType: 'blob' }
        )
        const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
        setPreviews(prev => ({ ...prev, [tpl]: url }))
      } catch (e) {
        console.error(`Failed to fetch ${tpl}:`, e)
        setErrors(prev => ({ ...prev, [tpl]: true }))
      } finally {
        setLoading(prev => ({ ...prev, [tpl]: false }))
      }
    })

    // Cleanup blob URLs on unmount
    return () => {
      Object.values(previews).forEach(url => {
        if (url) URL.revokeObjectURL(url)
      })
    }
  }, [sessionId, resumeId])

  // Download using existing blob URL (no API call)
  const handleDownload = () => {
    if (!previews[selected]) return
    const a = document.createElement('a')
    a.href = previews[selected]
    a.download = `resume_${selected}.pdf`
    a.click()
  }

  // Check if any template is still loading
  const anyLoading = loading.classic || loading.minimal || loading.modern
  const allReady = !anyLoading && (previews.classic || previews.minimal || previews.modern)

  // Get status indicator for each card
  const getStatusIndicator = (tpl) => {
    if (loading[tpl]) {
      return <span className="absolute top-2 right-2 animate-spin text-sm">⏳</span>
    }
    if (errors[tpl]) {
      return <span className="absolute top-2 right-2 text-red-500 text-sm">❌</span>
    }
    if (previews[tpl]) {
      return <span className="absolute top-2 right-2 text-green-500 text-sm">✅</span>
    }
    return null
  }

  return (
    <Card title="📥 Step 5 — Export PDF">

      {/* Status message */}
      {anyLoading && (
        <div className="mb-4 p-3 bg-indigo-50 border border-indigo-200 rounded-xl">
          <p className="text-sm text-indigo-700">
            ⏳ Generating all 3 template previews in parallel...
          </p>
          <p className="text-xs text-indigo-500 mt-1">
            This takes ~20-30 seconds. You can switch between templates instantly once loaded.
          </p>
        </div>
      )}

      {allReady && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-xl">
          <p className="text-sm text-green-700">
            ✅ All templates ready! Click to switch instantly.
          </p>
        </div>
      )}

      {/* Template Selector Cards */}
      <div className="mb-4">
        <p className="text-xs font-medium text-gray-500 mb-2">Choose template style:</p>
        <div className="grid grid-cols-3 gap-2">
          {Object.entries(TEMPLATES).map(([key, t]) => (
            <button
              key={key}
              onClick={() => setSelected(key)}
              disabled={loading[key] && !previews[key]}
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

      {/* Download Button */}
      <div className="flex gap-3 mb-4">
        <button
          onClick={handleDownload}
          disabled={loading[selected] || !previews[selected]}
          className="flex-1 bg-indigo-600 text-white py-3 rounded-xl text-sm font-medium
            hover:bg-indigo-700 disabled:opacity-40 transition"
        >
          {loading[selected]
            ? `⏳ Generating ${TEMPLATES[selected].name}...`
            : `⬇ Download Tailored Resume`}
        </button>
      </div>

      {/* PDF Preview */}
      <div className="mt-2">
        <div className="flex items-center justify-between mb-2">
          <p className="text-sm font-medium text-gray-700">
            Preview:
            <span className="ml-2 text-xs bg-indigo-100 text-indigo-600
              px-2 py-0.5 rounded-full">
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
              <p className="text-sm">Generating {TEMPLATES[selected].name} preview...</p>
              <p className="text-xs text-gray-300 mt-1">This may take 20-30 seconds</p>
            </div>
          ) : errors[selected] ? (
            <div className="w-full flex flex-col items-center justify-center text-red-400"
              style={{ height: '400px' }}>
              <p className="text-4xl mb-4">❌</p>
              <p className="text-sm">Failed to generate {TEMPLATES[selected].name} template</p>
              <p className="text-xs text-gray-400 mt-1">Try refreshing the page</p>
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
              <p className="text-sm">Preview will appear here</p>
            </div>
          )}
        </div>
      </div>
    </Card>
  )
}
