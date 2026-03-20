import { useState } from 'react'
import api from '../api/axios'

export default function ResumeUpload({ onUpload }) {
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleUpload = async () => {
    if (!file) return
    setLoading(true)
    setError('')
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await api.post('/api/parse/upload', form)
      setResult(res.data)
      onUpload(res.data.resume_id)
    } catch (e) {
      setError(e.response?.data?.detail || 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-xl shadow p-6">
      <h2 className="text-lg font-semibold text-gray-800 mb-4">📄 Step 1 — Upload Resume</h2>
      {!result ? (
        <div className="space-y-3">
          <input type="file" accept=".pdf,.docx"
            onChange={e => setFile(e.target.files[0])}
            className="block w-full text-sm text-gray-600 border rounded-lg p-2" />
          <button onClick={handleUpload} disabled={!file || loading}
            className="bg-indigo-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 transition">
            {loading ? 'Parsing...' : 'Upload & Parse'}
          </button>
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </div>
      ) : (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <p className="text-green-700 font-medium">✅ {result.resume_name} parsed successfully</p>
          <p className="text-sm text-gray-600 mt-1">
            {result.section_count} sections · {result.char_count.toLocaleString()} characters
          </p>
          <div className="flex flex-wrap gap-2 mt-2">
            {result.sections?.map(s => (
              <span key={s.position_index}
                className="bg-indigo-100 text-indigo-700 text-xs px-2 py-1 rounded-full">
                {s.section_label}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
