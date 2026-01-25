import { useState } from 'react'

interface FileUploadProps {
  onUpload: (files: { contract?: File; invoices?: File; usage?: File }) => void
  disabled?: boolean
}

export default function FileUpload({ onUpload, disabled }: FileUploadProps) {
  const [contract, setContract] = useState<File | null>(null)
  const [invoices, setInvoices] = useState<File | null>(null)
  const [usage, setUsage] = useState<File | null>(null)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onUpload({
      contract: contract || undefined,
      invoices: invoices || undefined,
      usage: usage || undefined,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="file-upload">
      <div className="file-input-group">
        <label>
          Contract (PDF):
          <input
            type="file"
            accept=".pdf"
            onChange={(e) => setContract(e.target.files?.[0] || null)}
            disabled={disabled}
          />
        </label>
      </div>
      <div className="file-input-group">
        <label>
          Invoices (CSV):
          <input
            type="file"
            accept=".csv"
            onChange={(e) => setInvoices(e.target.files?.[0] || null)}
            disabled={disabled}
          />
        </label>
      </div>
      <div className="file-input-group">
        <label>
          Usage (CSV):
          <input
            type="file"
            accept=".csv"
            onChange={(e) => setUsage(e.target.files?.[0] || null)}
            disabled={disabled}
          />
        </label>
      </div>
      <button type="submit" disabled={disabled || (!contract && !invoices && !usage)}>
        Upload Files
      </button>
    </form>
  )
}
