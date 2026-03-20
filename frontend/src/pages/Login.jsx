import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const handleLogin = async (e) => {
    e.preventDefault()
    try {
      const res = await axios.post('/auth/login',
        new URLSearchParams({ username: email, password }),
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' }}
      )
      localStorage.setItem('token', res.data.access_token)
      navigate('/dashboard')
    } catch {
      setError('Invalid credentials')
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="bg-white p-8 rounded-xl shadow-md w-full max-w-md">
        <h1 className="text-3xl font-bold text-center text-indigo-700 mb-2">ResumeForge</h1>
        <p className="text-center text-gray-500 mb-6">AI-powered resume tailoring</p>
        {error && <p className="text-red-500 text-sm mb-4 text-center">{error}</p>}
        <form onSubmit={handleLogin} className="space-y-4">
          <input type="email" placeholder="Email" value={email}
            onChange={e => setEmail(e.target.value)}
            className="w-full border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400" />
          <input type="password" placeholder="Password" value={password}
            onChange={e => setPassword(e.target.value)}
            className="w-full border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400" />
          <button type="submit"
            className="w-full bg-indigo-600 text-white py-2 rounded-lg font-semibold hover:bg-indigo-700 transition">
            Sign In
          </button>
        </form>
      </div>
    </div>
  )
}
