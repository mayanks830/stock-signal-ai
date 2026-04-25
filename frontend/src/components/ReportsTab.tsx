import { useQuery } from '@tanstack/react-query'

interface Report {
  filename: string
  date: string
  size_kb: number
}

export default function ReportsTab() {
  const { data, isLoading } = useQuery<Report[]>({
    queryKey: ['reports'],
    queryFn: () => fetch('/api/reports').then(r => r.json()),
  })

  if (isLoading) return <div className="text-content-muted text-sm py-8 text-center">Loading reports...</div>
  if (!data?.length) return (
    <div className="text-content-faint text-sm py-12 text-center">
      <div className="text-4xl mb-3">📄</div>
      No reports yet. Reports are generated during watchlist scans.
    </div>
  )

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-content-muted text-left">
            <th className="py-3 px-4">Date</th>
            <th className="py-3 px-4">Report</th>
            <th className="py-3 px-4 text-right">Size</th>
            <th className="py-3 px-4 text-right">Action</th>
          </tr>
        </thead>
        <tbody>
          {data.map(r => (
            <tr key={r.filename} className="border-b border-border/50 hover:bg-surface-secondary/50 transition">
              <td className="py-3 px-4 text-content-secondary">{r.date}</td>
              <td className="py-3 px-4 text-content-primary font-medium">{r.filename}</td>
              <td className="py-3 px-4 text-content-muted text-right">{r.size_kb} KB</td>
              <td className="py-3 px-4 text-right">
                <a
                  href={`/api/reports/${encodeURIComponent(r.filename)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bg-blue-600 hover:bg-blue-500 text-white text-xs px-3 py-1.5 rounded-lg transition inline-block"
                >
                  Download
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
