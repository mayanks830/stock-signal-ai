import { useState } from 'react'

const TYPES = [
  { value: 'feature', label: 'Feature Request' },
  { value: 'bug', label: 'Bug Report' },
  { value: 'general', label: 'General Feedback' },
]

export default function FeedbackModal({ onClose, username }: { onClose: () => void; username?: string }) {
  const [type, setType] = useState('feature')
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)

  const submit = async () => {
    if (!message.trim()) return
    setSending(true)
    try {
      await fetch('/api/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: username || 'Anonymous',
          email: 'in-app@feedback',
          topic: type,
          message: message.trim(),
        }),
      })
      setSent(true)
    } catch {
      // silently fail
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60" />
      <div
        className="relative bg-surface-secondary border border-border rounded-xl w-full max-w-sm p-5"
        onClick={e => e.stopPropagation()}
      >
        {sent ? (
          <div className="text-center py-4">
            <div className="text-3xl mb-3">&#x1F389;</div>
            <h3 className="text-sm font-semibold text-content-primary mb-1">Thanks for the feedback!</h3>
            <p className="text-xs text-content-muted mb-4">We'll review it shortly.</p>
            <button
              onClick={onClose}
              className="text-xs text-blue-400 hover:text-blue-300 transition"
            >
              Close
            </button>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-content-primary">Send Feedback</h3>
              <button onClick={onClose} className="text-content-faint hover:text-content-primary transition text-lg leading-none">&times;</button>
            </div>

            <div className="flex gap-1.5 mb-3">
              {TYPES.map(t => (
                <button
                  key={t.value}
                  onClick={() => setType(t.value)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                    type === t.value
                      ? 'bg-blue-600 text-white'
                      : 'bg-surface-tertiary text-content-muted hover:text-content-primary'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <textarea
              value={message}
              onChange={e => setMessage(e.target.value)}
              placeholder={type === 'feature' ? 'What would make this more useful?' : type === 'bug' ? 'What went wrong?' : 'What\'s on your mind?'}
              className="w-full bg-surface-primary border border-border rounded-lg p-3 text-sm text-content-primary placeholder:text-content-faint outline-none focus:border-blue-500 transition resize-none h-28"
            />

            <button
              onClick={submit}
              disabled={!message.trim() || sending}
              className="w-full mt-3 bg-blue-600 hover:bg-blue-500 disabled:bg-surface-tertiary disabled:text-content-faint text-white text-sm font-medium py-2 rounded-lg transition"
            >
              {sending ? 'Sending...' : 'Send'}
            </button>
          </>
        )}
      </div>
    </div>
  )
}
