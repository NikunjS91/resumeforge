import { useState } from 'react'
import ResumeUpload from '../components/ResumeUpload'
import JobInput     from '../components/JobInput'
import TailorPanel  from '../components/TailorPanel'
import ATSScore     from '../components/ATSScore'
import ExportPanel  from '../components/ExportPanel'

const STEPS = [
  { num: 1, label: 'Upload Resume' },
  { num: 2, label: 'Analyze JD' },
  { num: 3, label: 'Tailor' },
  { num: 4, label: 'ATS Score' },
  { num: 5, label: 'Export PDF' },
]

export default function Dashboard() {
  const [resumeId,  setResumeId]  = useState(null)
  const [jobId,     setJobId]     = useState(null)
  const [sessionId, setSessionId] = useState(null)
  const [atsScore,  setAtsScore]  = useState(null)

  const currentStep = !resumeId ? 1 : !jobId ? 2 : !sessionId ? 3 : atsScore === null ? 4 : 5

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Nav */}
      <nav className="bg-indigo-700 text-white px-8 py-4 flex items-center justify-between shadow-md">
        <h1 className="text-xl font-bold">⚡ ResumeForge</h1>
        <button onClick={() => { localStorage.removeItem('token'); window.location.href = '/' }}
          className="text-sm opacity-75 hover:opacity-100 transition">
          Sign out
        </button>
      </nav>

      <div className="max-w-3xl mx-auto mt-8 px-4 pb-16">
        {/* Progress bar */}
        <div className="flex items-center mb-8">
          {STEPS.map((s, i) => (
            <div key={s.num} className="flex items-center flex-1">
              <div className="flex flex-col items-center">
                <div className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold border-2 transition
                  ${currentStep > s.num
                    ? 'bg-green-500 border-green-500 text-white'
                    : currentStep === s.num
                      ? 'bg-indigo-600 border-indigo-600 text-white'
                      : 'bg-white border-gray-300 text-gray-400'}`}>
                  {currentStep > s.num ? '✓' : s.num}
                </div>
                <span className="text-xs text-gray-500 mt-1 hidden sm:block">{s.label}</span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`flex-1 h-0.5 mx-1 ${currentStep > s.num ? 'bg-green-400' : 'bg-gray-200'}`} />
              )}
            </div>
          ))}
        </div>

        {/* Steps */}
        <div className="space-y-5">
          <ResumeUpload onUpload={setResumeId} />
          {resumeId  && <JobInput onAnalyze={setJobId} />}
          {jobId     && <TailorPanel resumeId={resumeId} jobId={jobId} onTailored={setSessionId} />}
          {sessionId && <ATSScore resumeId={resumeId} jobId={jobId} sessionId={sessionId} onScored={setAtsScore} />}
          {sessionId && <ExportPanel resumeId={resumeId} sessionId={sessionId} />}
        </div>
      </div>
    </div>
  )
}
