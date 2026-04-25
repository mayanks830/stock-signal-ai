import { useState } from 'react'

const TOPICS = [
  { value: 'general', label: 'General Inquiry' },
  { value: 'feature', label: 'Feature Request' },
  { value: 'bug', label: 'Bug Report' },
  { value: 'partnership', label: 'Partnership / Business' },
  { value: 'support', label: 'Account Support' },
]

export default function ContactForm() {
  const [form, setForm] = useState({ name: '', email: '', topic: 'general', message: '' })
  const [status, setStatus] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim() || !form.email.trim() || !form.message.trim()) return
    setStatus('sending')
    try {
      const res = await fetch('/api/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (res.ok) {
        setStatus('sent')
        setForm({ name: '', email: '', topic: 'general', message: '' })
        setTimeout(() => setStatus('idle'), 5000)
      } else {
        setStatus('error')
      }
    } catch {
      setStatus('error')
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-surface-secondary border border-border rounded-xl p-6">
        <div className="flex flex-col sm:flex-row gap-6">
          {/* Left: info */}
          <div className="sm:w-2/5 space-y-4">
            <h3 className="text-lg font-semibold text-content-primary">Get in Touch</h3>
            <p className="text-sm text-content-muted leading-relaxed">
              Have a question, feature request, or just want to say hi? We'd love to hear from you.
            </p>
            <div className="space-y-3 pt-2">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-blue-600/20 flex items-center justify-center text-sm shrink-0">&#x1f4e7;</div>
                <div>
                  <p className="text-xs text-content-faint uppercase tracking-wider">Email</p>
                  <p className="text-sm text-content-secondary">mayanksethi86@gmail.com</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-purple-600/20 flex items-center justify-center text-sm shrink-0">&#x1f4ac;</div>
                <div>
                  <p className="text-xs text-content-faint uppercase tracking-wider">Discord</p>
                  <p className="text-sm text-content-secondary">Join for real-time alerts</p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-green-600/20 flex items-center justify-center text-sm shrink-0">&#x23f0;</div>
                <div>
                  <p className="text-xs text-content-faint uppercase tracking-wider">Response Time</p>
                  <p className="text-sm text-content-secondary">Usually within 24 hours</p>
                </div>
              </div>
            </div>
          </div>

          {/* Right: form */}
          <div className="sm:w-3/5">
            {status === 'sent' ? (
              <div className="flex flex-col items-center justify-center h-full text-center py-8">
                <div className="w-14 h-14 rounded-full bg-green-600/20 flex items-center justify-center text-2xl mb-4">&#x2705;</div>
                <h4 className="text-content-primary font-semibold mb-1">Message Sent!</h4>
                <p className="text-sm text-content-muted">Thanks for reaching out. We'll get back to you soon.</p>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-3">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-content-faint uppercase tracking-wider mb-1 block">Name</label>
                    <input
                      type="text"
                      placeholder="Your name"
                      value={form.name}
                      onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                      required
                      className="w-full bg-surface-tertiary border border-border-subtle rounded-lg px-4 py-2.5 text-sm text-content-primary placeholder-content-faint focus:border-blue-500 focus:outline-none transition"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-content-faint uppercase tracking-wider mb-1 block">Email</label>
                    <input
                      type="email"
                      placeholder="you@example.com"
                      value={form.email}
                      onChange={e => setForm(p => ({ ...p, email: e.target.value }))}
                      required
                      className="w-full bg-surface-tertiary border border-border-subtle rounded-lg px-4 py-2.5 text-sm text-content-primary placeholder-content-faint focus:border-blue-500 focus:outline-none transition"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-xs text-content-faint uppercase tracking-wider mb-1 block">Topic</label>
                  <select
                    value={form.topic}
                    onChange={e => setForm(p => ({ ...p, topic: e.target.value }))}
                    className="w-full bg-surface-tertiary border border-border-subtle rounded-lg px-4 py-2.5 text-sm text-content-primary focus:border-blue-500 focus:outline-none transition"
                  >
                    {TOPICS.map(t => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-content-faint uppercase tracking-wider mb-1 block">Message</label>
                  <textarea
                    placeholder="Tell us what's on your mind..."
                    value={form.message}
                    onChange={e => setForm(p => ({ ...p, message: e.target.value }))}
                    required
                    rows={4}
                    className="w-full bg-surface-tertiary border border-border-subtle rounded-lg px-4 py-2.5 text-sm text-content-primary placeholder-content-faint focus:border-blue-500 focus:outline-none resize-none transition"
                  />
                </div>
                <button
                  type="submit"
                  disabled={status === 'sending'}
                  className="w-full sm:w-auto bg-blue-600 hover:bg-blue-500 disabled:bg-surface-tertiary disabled:text-content-faint text-white text-sm font-medium px-8 py-2.5 rounded-lg transition"
                >
                  {status === 'sending' ? 'Sending...' : 'Send Message'}
                </button>
                {status === 'error' && <p className="text-red-400 text-sm">Failed to send. Please try again.</p>}
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
