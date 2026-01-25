interface TraceViewerProps {
  trace: any
}

export default function TraceViewer({ trace }: TraceViewerProps) {
  return (
    <div className="trace-viewer">
      <h3>Request ID: {trace.request_id}</h3>
      <div className="trace-section">
        <h4>Retrieved Documents</h4>
        <ul>
          {trace.retrieved_doc_ids?.map((doc: string, i: number) => (
            <li key={i}>{doc}</li>
          ))}
        </ul>
      </div>
      <div className="trace-section">
        <h4>Token Usage</h4>
        <p>Input: {trace.tokens?.in}</p>
        <p>Output: {trace.tokens?.out}</p>
        <p>Total: {trace.tokens?.total}</p>
      </div>
      <div className="trace-section">
        <h4>Validation</h4>
        <pre>{JSON.stringify(trace.validation, null, 2)}</pre>
      </div>
    </div>
  )
}
