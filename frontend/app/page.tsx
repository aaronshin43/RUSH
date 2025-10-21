'use client'

import { useState } from 'react'

export default function Home() {
  const [query, setQuery] = useState('')
  const [response, setResponse] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      })
      const data = await res.json()
      setResponse(data.answer || 'No response')
    } catch (error) {
      setResponse('Error: Could not connect to API')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-4xl font-bold mb-8">RUSH</h1>
        <p className="text-gray-600 mb-8">Dickinson College AI Assistant</p>
        
        <form onSubmit={handleSubmit} className="mb-8">
          <div className="flex gap-4">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask anything about Dickinson..."
              className="flex-1 px-4 py-2 border rounded"
            />
            <button
              type="submit"
              disabled={loading}
              className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Thinking...' : 'Ask'}
            </button>
          </div>
        </form>
        
        {response && (
          <div className="p-4 bg-gray-100 rounded">
            <pre className="whitespace-pre-wrap">{response}</pre>
          </div>
        )}
      </div>
    </main>
  )
}