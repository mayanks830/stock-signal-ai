import { useState } from 'react'

const TOPICS = [
  { value: 'general', label: 'General Inquiry' },
  { value: 'feature', label: 'Feature Request' },
  { value: 'bug', label: 'Bug Report' },
  { value: 'partnership', label: 'Partnership / Business' },
  { value: 'support', label: 'Account Support' },
]

export default function AboutPage() {
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
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Hero */}
      <div className="text-center py-10">
        <div className="inline-flex items-center gap-2 bg-blue-600/10 border border-blue-500/20 rounded-full px-4 py-1.5 mb-4">
          <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          <span className="text-xs text-blue-400 font-medium">Live &amp; Scanning Markets Daily</span>
        </div>
        <h2 className="text-4xl font-bold text-content-primary mb-3">Trading Signals</h2>
        <p className="text-content-muted text-lg max-w-xl mx-auto">
          Institutional-grade market intelligence powered by AI — built for investors who want an edge.
        </p>
      </div>

      {/* What We Do */}
      <section className="bg-surface-secondary border border-border rounded-xl p-6">
        <h3 className="text-lg font-semibold text-content-primary mb-4">What We Do</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-surface-tertiary/50 rounded-lg p-5 border border-border-subtle/50 hover:border-blue-500/30 transition">
            <div className="w-10 h-10 rounded-lg bg-blue-600/20 flex items-center justify-center text-xl mb-3">&#x1f916;</div>
            <h4 className="text-sm font-semibold text-content-primary mb-2">AI-Powered Signals</h4>
            <p className="text-xs text-content-muted leading-relaxed">
              Claude AI scans S&amp;P 500 stocks daily — analyzing price action, volume, news catalysts, technicals, and insider activity to find high-conviction buy signals.
            </p>
          </div>
          <div className="bg-surface-tertiary/50 rounded-lg p-5 border border-border-subtle/50 hover:border-blue-500/30 transition">
            <div className="w-10 h-10 rounded-lg bg-purple-600/20 flex items-center justify-center text-xl mb-3">&#x1f3db;</div>
            <h4 className="text-sm font-semibold text-content-primary mb-2">Congress Tracking</h4>
            <p className="text-xs text-content-muted leading-relaxed">
              Real-time monitoring of congressional stock trades with $500k+ alerts. See what senators are buying and selling before the market reacts.
            </p>
          </div>
          <div className="bg-surface-tertiary/50 rounded-lg p-5 border border-border-subtle/50 hover:border-blue-500/30 transition">
            <div className="w-10 h-10 rounded-lg bg-green-600/20 flex items-center justify-center text-xl mb-3">&#x1f4ca;</div>
            <h4 className="text-sm font-semibold text-content-primary mb-2">Full Transparency</h4>
            <p className="text-xs text-content-muted leading-relaxed">
              Every signal tracked with entry price, target, and stop loss. Real-time P&amp;L, win/loss outcomes, and complete historical performance.
            </p>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="bg-surface-secondary border border-border rounded-xl p-6">
        <h3 className="text-lg font-semibold text-content-primary mb-5">How It Works</h3>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          {[
            { step: '1', title: 'Scan', desc: 'Daily scan of S&P 500 for stocks with 3%+ weekly moves, strong volume, and news catalysts.', color: 'blue' },
            { step: '2', title: 'Analyze', desc: 'AI evaluates fundamentals, technicals, sentiment, insider activity, and congressional trades.', color: 'purple' },
            { step: '3', title: 'Signal', desc: 'High and medium confidence buy signals with price targets and stop losses.', color: 'green' },
            { step: '4', title: 'Track', desc: 'Automated tracking with real-time P&L, win/loss outcomes, and performance history.', color: 'amber' },
          ].map(s => (
            <div key={s.step} className="text-center">
              <div className={`w-10 h-10 rounded-full bg-${s.color === 'amber' ? 'yellow' : s.color}-600 flex items-center justify-center text-sm font-bold text-white mx-auto mb-3`}>
                {s.step}
              </div>
              <h4 className="text-sm font-semibold text-content-primary mb-1">{s.title}</h4>
              <p className="text-xs text-content-muted leading-relaxed">{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Founder — Enhanced */}
      <section className="relative rounded-xl overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-600/10 via-purple-600/5 to-transparent pointer-events-none" />
        <div className="relative bg-surface-secondary border border-border rounded-xl p-8">
          <h3 className="text-lg font-semibold text-content-primary mb-6">Meet the Founder</h3>
          <div className="flex flex-col sm:flex-row gap-8">
            {/* Avatar */}
            <div className="flex flex-col items-center shrink-0">
              <div className="relative">
                <div className="absolute inset-0 bg-blue-500/20 rounded-full blur-xl" />
                <div className="relative w-28 h-28 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-4xl font-bold text-white ring-4 ring-blue-500/20 shadow-2xl shadow-blue-500/20">
                  MS
                </div>
              </div>
              <a
                href="https://www.linkedin.com/in/mayank-sethi-b8682613/"
                target="_blank"
                rel="noopener noreferrer"
                className="mt-4 inline-flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition bg-blue-500/10 border border-blue-500/20 rounded-full px-3 py-1"
              >
                <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
                LinkedIn
              </a>
            </div>

            {/* Bio */}
            <div className="space-y-4 flex-1">
              <div>
                <h4 className="text-content-primary text-2xl font-bold">Mayank Sethi</h4>
                <div className="flex items-center gap-2 mt-1">
                  <div className="w-2 h-2 rounded-full bg-green-400" />
                  <span className="text-blue-400 text-sm font-semibold">Founder &amp; CEO</span>
                </div>
              </div>

              <p className="text-sm text-content-secondary leading-relaxed">
                A seasoned technologist with <span className="text-content-primary font-semibold">17+ years</span> of experience in fintech and enterprise data architecture,
                having built and managed data systems powering over <span className="text-content-primary font-semibold">$2+ trillion</span> in assets under management.
              </p>
              <p className="text-sm text-content-secondary leading-relaxed">
                Former database architect at <span className="text-content-primary font-semibold">PIMCO</span> — one of the world's largest fixed-income investment managers —
                and currently at <span className="text-content-primary font-semibold">Group1001</span>. Certified across AWS, Oracle Cloud, and Snowflake with a deep focus
                on Generative AI and LLMs.
              </p>

              {/* Blockquote */}
              <blockquote className="border-l-2 border-blue-500 pl-4 py-1">
                <p className="text-sm text-content-muted italic leading-relaxed">
                  "I built Trading Signals to bridge the gap between institutional-grade market intelligence and everyday investors —
                  combining decades of financial data engineering with cutting-edge AI."
                </p>
              </blockquote>

              {/* Stat cards with gradient tint */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
                <div className="bg-gradient-to-br from-blue-500/10 to-transparent rounded-lg p-3 text-center border border-blue-500/20">
                  <div className="text-xl font-bold text-content-primary">17+</div>
                  <div className="text-[10px] text-content-muted uppercase tracking-wider">Years in Fintech</div>
                </div>
                <div className="bg-gradient-to-br from-purple-500/10 to-transparent rounded-lg p-3 text-center border border-purple-500/20">
                  <div className="text-xl font-bold text-content-primary">$2T+</div>
                  <div className="text-[10px] text-content-muted uppercase tracking-wider">AUM Supported</div>
                </div>
                <div className="bg-gradient-to-br from-green-500/10 to-transparent rounded-lg p-3 text-center border border-green-500/20">
                  <div className="text-xl font-bold text-content-primary">PIMCO</div>
                  <div className="text-[10px] text-content-muted uppercase tracking-wider">Former</div>
                </div>
                <div className="bg-gradient-to-br from-amber-500/10 to-transparent rounded-lg p-3 text-center border border-amber-500/20">
                  <div className="text-xl font-bold text-content-primary">GenAI</div>
                  <div className="text-[10px] text-content-muted uppercase tracking-wider">Certified</div>
                </div>
              </div>

              {/* Certifications with hover */}
              <div className="pt-1">
                <p className="text-xs text-content-faint mb-2 uppercase tracking-wider font-medium">Certifications</p>
                <div className="flex flex-wrap gap-1.5">
                  {[
                    'Oracle Cloud GenAI Professional',
                    'SnowPro Advanced: Administrator',
                    'AWS Database Specialty',
                    'AWS Solutions Architect',
                    'AWS Cloud Practitioner',
                    'ITIL v3',
                  ].map(c => (
                    <span key={c} className="px-2.5 py-1 bg-surface-tertiary border border-border-subtle/50 text-content-muted rounded-full text-[11px] hover:border-blue-500/30 hover:text-blue-400 transition cursor-default">{c}</span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Tech Stack */}
      <section className="bg-surface-secondary border border-border rounded-xl p-6">
        <h3 className="text-lg font-semibold text-content-primary mb-3">Powered By</h3>
        <div className="flex flex-wrap gap-2">
          {[
            { name: 'Claude AI', cat: 'ai' },
            { name: 'Python', cat: 'backend' },
            { name: 'FastAPI', cat: 'backend' },
            { name: 'React', cat: 'frontend' },
            { name: 'TypeScript', cat: 'frontend' },
            { name: 'SQLite', cat: 'backend' },
            { name: 'Yahoo Finance', cat: 'data' },
            { name: 'Capitol Trades', cat: 'data' },
            { name: 'Discord', cat: 'alerts' },
            { name: 'Railway', cat: 'infra' },
          ].map(t => (
            <span key={t.name} className={`px-3 py-1.5 rounded-full text-xs font-medium border ${
              t.cat === 'ai' ? 'bg-purple-900/30 border-purple-700/50 text-purple-300' :
              t.cat === 'data' ? 'bg-green-900/30 border-green-700/50 text-green-300' :
              t.cat === 'alerts' ? 'bg-yellow-900/30 border-yellow-700/50 text-yellow-300' :
              t.cat === 'infra' ? 'bg-red-900/30 border-red-700/50 text-red-300' :
              'bg-surface-tertiary border-border-subtle/50 text-content-secondary'
            }`}>
              {t.name}
            </span>
          ))}
        </div>
      </section>

      {/* Contact Form */}
      <section className="bg-surface-secondary border border-border rounded-xl p-6">
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
      </section>

      {/* Disclaimer */}
      <div className="text-center pb-8 space-y-2">
        <p className="text-xs text-content-ghost">
          This tool is for informational purposes only. Not financial advice. Always do your own research before making investment decisions.
        </p>
        <p className="text-xs text-content-ghost/60">&copy; {new Date().getFullYear()} Trading Signals. All rights reserved.</p>
      </div>
    </div>
  )
}
