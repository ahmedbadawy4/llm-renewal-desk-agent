import { useState, useEffect } from 'react'
import axios from 'axios'
import FileUpload from '@/components/FileUpload'
import RenewalBriefViewer from '@/components/RenewalBriefViewer'
import TraceViewer from '@/components/TraceViewer'

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000'

export default function Home() {
  const [vendorId, setVendorId] = useState('vendor_123')
  const [apiStatus, setApiStatus] = useState<'checking' | 'online' | 'offline'>('offline')
  const [brief, setBrief] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [trace, setTrace] = useState<any>(null)

  useEffect(() => {
    checkHealth()
  }, [])

  const checkHealth = async () => {
    setApiStatus('checking')
    try {
      await axios.get(`${API_BASE}/health`)
      setApiStatus('online')
    } catch {
      setApiStatus('offline')
    }
  }

  const handleIngest = async (files: { contract?: File; invoices?: File; usage?: File }) => {
    setLoading(true)
    const formData = new FormData()
    if (files.contract) formData.append('contract', files.contract)
    if (files.invoices) formData.append('invoices', files.invoices)
    if (files.usage) formData.append('usage', files.usage)

    try {
      const response = await axios.post(`${API_BASE}/ingest?vendor_id=${vendorId}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      alert(`Ingestion started: ${response.data.job_ids?.join(', ') || 'success'}`)
    } catch (error: any) {
      alert(`Ingestion failed: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateBrief = async () => {
    setLoading(true)
    setBrief(null)
    setTrace(null)
    try {
      const response = await axios.post(
        `${API_BASE}/renewal-brief?vendor_id=${vendorId}`,
        { refresh: false }
      )
      setBrief(response.data.brief)
      if (response.data.request_id) {
        fetchTrace(response.data.request_id)
      }
    } catch (error: any) {
      alert(`Failed to generate brief: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const fetchTrace = async (requestId: string) => {
    try {
      const response = await axios.get(`${API_BASE}/debug/trace/${requestId}`)
      setTrace(response.data)
    } catch (error) {
      console.error('Failed to fetch trace:', error)
    }
  }

  return (
    <div className="container">
      <header>
        <h1>Renewal Desk Agent</h1>
        <div className="status">
          <span>API Status: </span>
          <span className={apiStatus === 'online' ? 'online' : 'offline'}>
            {apiStatus}
          </span>
          <button onClick={checkHealth}>Refresh</button>
        </div>
      </header>

      <main>
        <section>
          <h2>Configuration</h2>
          <label>
            Vendor ID:
            <input
              type="text"
              value={vendorId}
              onChange={(e) => setVendorId(e.target.value)}
            />
          </label>
        </section>

        <section>
          <h2>Document Ingestion</h2>
          <FileUpload onUpload={handleIngest} disabled={loading} />
        </section>

        <section>
          <h2>Generate Renewal Brief</h2>
          <button onClick={handleGenerateBrief} disabled={loading || apiStatus !== 'online'}>
            {loading ? 'Generating...' : 'Generate Brief'}
          </button>
        </section>

        {brief && (
          <section>
            <h2>Renewal Brief</h2>
            <RenewalBriefViewer brief={brief} />
          </section>
        )}

        {trace && (
          <section>
            <h2>Debug Trace</h2>
            <TraceViewer trace={trace} />
          </section>
        )}
      </main>
    </div>
  )
}
