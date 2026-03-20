import { useState } from 'react'
import ResumeUpload from '../components/ResumeUpload'
import JobInput from '../components/JobInput'
import TailorPanel from '../components/TailorPanel'
import ATSScore from '../components/ATSScore'
import ExportButton from '../components/ExportButton'

export default function Dashboard() {
  const [resumeId, setResumeId]     = useState(null)
  const [jobId, setJobId]           = useState(null)
  const [sessionId, setSessionId]   = useState(null)
  const [atsScore, setAtsScore]     = useState(null)

  const steps = [
    { num: 1, label: 'Upload Resume',   done: !!resumeId },
    { num: 2, label: 'Analyze JD',      done: !!jobId },
    { num: 3, label: 'Tailor Resume',   done: !!sessionId },
    { num: 4, label: 'ATS Score',       done: atsScore !== null },
    { num: 5, label: 'Download PDF',    done: false },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <nav className="bg-indigo-700 text-white px-8 py-4 flex items-center justify-between shadow">
        <h1 className="text-xl font-bold tracking-wide">⚡ ResumeForge</h1>
        <button onClick={() => { localStorage.removeItem('token'); window.location.href = '/' }}
          className="text-sm opacity-80 hover:opacity-100">Sign out</button>
      </nav>

      {/* Progress Steps */}
      <div className="max-w-4xl mx-auto mt-8 px-4">
        <div className="flex items-center justify-between mb-8">
          {steps.map((s, i) => (
            <div key={s.num} className="flex items-center">
              <div className={`flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold
                ${s.done ? 'bg-green-500 text-white' : 'bg-gray-200 text-gray-600'}`}>
                {s.done ? '✓' : s.num}
              </div>
              <span className="ml-2 text-sm text-gray-600 hidden sm:block">{s.label}</span>
              {i < steps.length - 1 && <div className="w-8 h-px bg-gray-300 mx-3" />}
            </div>
          ))}
        </div>

        {/* Pipeline Steps */}
        <div className="space-y-6">
          <ResumeUpload onUpload={setResumeId} />

          {resumeId && (
            <JobInput onAnalyze={setJobId} />
          )}

          {resumeId && jobId && (
            <TailorPanel resumeId={resumeId} jobId={jobId} onTailored={setSessionId} />
          )}

          {sessionId && (
            <ATSScore resumeId={resumeId} jobId={jobId} sessionId={sessionId} onScored={setAtsScore} />
          )}

          {sessionId && (
            <ExportButton resumeId={resumeId} sessionId={sessionId} />
          )}
        </div>
      </div>
    </div>
  )
}
