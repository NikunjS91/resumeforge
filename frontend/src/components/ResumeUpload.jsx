import { useState } from 'react'
import api from '../api/axios'

export default function ResumeUpload({ onUpload }) {
  const [file,    setFile]    = useState(null)
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  const handleUpload = async () => {
    if (!file) return
    setLoading(true); setError('')
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await api.post('/api/parse/upload', form)
      setResult(res.data)
      onUpload(res.data.resume_id)
    } catch (e) {
      setError(e.response?.data?.detail || 'Upload failed')
    } finally { setLoading(false) }
  }

  return (
    <Card title="📄 Step 1 — Upload Resume">
      {!result ? (
        <div className="space-y-3">
          <label className="block border-2 border-dashed border-gray-200 rounded-xl p-6 text-center cursor-pointer hover:border-indigo-300 transition">
            <input type="file" accept=".pdf,.docx" className="hidden"
              onChange={e => setFile(e.target.files[0])} />
            {file
              ? <p className="text-indigo-600 font-medium">{file.name}</p>
              : <><p className="text-gray-400 text-sm">Click to upload PDF or DOCX</p><p className="text-gray-300 text-xs mt-1">Max 10MB</p></>
            }
          </label>
          <button onClick={handleUpload} disabled={!file || loading}
            className="w-full bg-indigo-600 text-white py-2.5 rounded-xl text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 transition">
            {loading ? 'Parsing resume...' : 'Upload & Parse'}
          </button>
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </div>
      ) : (
        <Success title={`${result.name || result.resume_name || 'Resume'} parsed`}
          subtitle={`${result.section_count} sections · ${result.char_count?.toLocaleString()} chars`}>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {result.sections?.map(s => (
              <span key={s.position_index}
                className="bg-indigo-100 text-indigo-700 text-xs px-2.5 py-0.5 rounded-full">
                {s.section_label}
              </span>
            ))}
          </div>
        </Success>
      )}
    </Card>
  )
}

// Shared sub-components
function Card({ title, children }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
      <h2 className="text-base font-semibold text-gray-800 mb-4">{title}</h2>
      {children}
    </div>
  )
}

function Success({ title, subtitle, children }) {
  return (
    <div className="bg-green-50 border border-green-100 rounded-xl p-4">
      <p className="text-green-700 font-medium text-sm">✅ {title}</p>
      {subtitle && <p className="text-gray-500 text-xs mt-0.5">{subtitle}</p>}
      {children}
    </div>
  )
}

export { Card, Success }
