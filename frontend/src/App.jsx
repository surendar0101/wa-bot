import { Component, useCallback, useEffect, useRef, useState } from 'react'
import {
  confirmPayment,
  getAppointments,
  getHealth,
  getFormSubmissions,
  getStats,
  simulateFormIntake,
  resetDemo,
  selectSlot,
  sendMessage,
  startChat,
  uploadInvestmentDoc,
} from './api'

const PHONE = '+919876543210'

const JOURNEY = [
  'Enquiry',
  'Your Details',
  'Qualification',
  'Investment Profile',
  'Slot Selection',
  'Payment',
  'Confirmation',
  'Reminder',
]

function getJourneyIndex(state, { slots, showPayment, paymentProcessing, bookingConfirmed }) {
  if (bookingConfirmed || state === 'confirmed') return 7
  if (paymentProcessing || showPayment || state === 'payment') return 5
  if (slots.length > 0 || state === 'await_slot_selection' || state === 'show_slots') return 4
  if (
    [
      'collect_consultation_type',
      'collect_investment_range',
      'collect_existing_investor',
      'collect_investment_types',
      'collect_investment_details_method',
      'collect_investment_details_text',
      'await_investment_upload',
      'collect_key_questions',
    ].includes(state)
  )
    return 3
  if (state === 'qualification') return 2
  if (state === 'post_form_followup') return 3
  if (['collect_name', 'collect_email', 'collect_requirement'].includes(state)) return 1
  return 0 // greeting, faq_mode
}

function formatTime() {
  return new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
}

function renderMarkdown(text) {
  return String(text ?? '').replace(/\*(.*?)\*/g, '<strong>$1</strong>')
}

class ViewErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="dashboard-panel">
          <h2>This view hit an error</h2>
          <p style={{ color: 'var(--slate)', margin: '8px 0 16px' }}>{String(this.state.error.message || this.state.error)}</p>
          <button onClick={() => this.setState({ error: null })}>Try again</button>
        </div>
      )
    }
    return this.props.children
  }
}

function WhatsAppChat({ onDashboardRefresh }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [state, setState] = useState('greeting')
  const [slots, setSlots] = useState([])
  const [showPayment, setShowPayment] = useState(false)
  const [paymentProcessing, setPaymentProcessing] = useState(false)
  const [appointmentId, setAppointmentId] = useState(null)
  const [activeOptions, setActiveOptions] = useState([])
  const [optionStyle, setOptionStyle] = useState('list')
  const [bookingConfirmed, setBookingConfirmed] = useState(false)
  const [paymentFee, setPaymentFee] = useState(999)
  const [aiMode, setAiMode] = useState('rule-based')
  const [showUpload, setShowUpload] = useState(false)
  const [uploadAccept, setUploadAccept] = useState('.pdf,.png,.jpg,.jpeg,.webp')
  const fileInputRef = useRef(null)
  const messagesRef = useRef(null)

  useEffect(() => {
    let cancelled = false
    getHealth()
      .then((h) => {
        if (!cancelled) setAiMode(h?.ai_mode || 'rule-based')
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  const applyResponse = (data) => {
    if (!data || typeof data !== 'object') return
    setState(data.state)
    if (data.booking_confirmed) {
      setBookingConfirmed(true)
    } else if (data.state === 'greeting') {
      setBookingConfirmed(false)
      setShowPayment(false)
      setSlots([])
      setPaymentProcessing(false)
    }
    if (data.show_slots && Array.isArray(data.slots)) {
      setSlots(data.slots)
      setShowPayment(false)
      setShowUpload(false)
      setActiveOptions([])
    } else     if (data.show_payment) {
      setShowPayment(true)
      setShowUpload(false)
      setSlots([])
      setActiveOptions([])
      if (data.payment_fee) setPaymentFee(data.payment_fee)
    } else if (data.show_upload) {
      setShowUpload(true)
      setUploadAccept(data.upload_accept || '.pdf,.png,.jpg,.jpeg,.webp')
      if (Array.isArray(data.options) && data.options.length) {
        setActiveOptions(data.options)
        setOptionStyle(data.option_style || 'chips')
      } else {
        setActiveOptions([])
      }
    } else if (Array.isArray(data.options) && data.options.length) {
      setActiveOptions(data.options)
      setOptionStyle(data.option_style || 'list')
      setShowUpload(false)
    } else {
      setActiveOptions([])
      setShowUpload(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    startChat(PHONE)
      .then((data) => {
        if (cancelled || !data) return
        if (Array.isArray(data.messages) && data.messages.length) {
          setMessages(
            data.messages.map((m) => ({
              role: m.role,
              content: m.content,
              time: formatTime(),
            })),
          )
        } else if (data.reply) {
          setMessages([{ role: 'assistant', content: data.reply, time: formatTime() }])
        }
        applyResponse(data)
        if (data.appointment_id) setAppointmentId(data.appointment_id)
        if (data.booking_confirmed) setBookingConfirmed(true)
      })
      .catch(() => {
        if (!cancelled) {
          setMessages([
            {
              role: 'assistant',
              content: 'Could not reach the assistant. Make sure the backend is running on port 8000, then refresh.',
              time: formatTime(),
            },
          ])
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const el = messagesRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, loading, slots, showPayment, showUpload])

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    addUser(`📎 ${file.name}`)
    setLoading(true)
    try {
      const data = await uploadInvestmentDoc(PHONE, file)
      applyResponse(data)
      if (data.reply) addBot(data.reply)
    } catch (err) {
      addBot(`Upload failed: ${err.message}`)
    } finally {
      setLoading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const addBot = (content, extra = {}) => {
    setMessages((m) => [...m, { role: 'assistant', content, time: formatTime(), ...extra }])
  }

  const addUser = (content) => {
    setMessages((m) => [...m, { role: 'user', content, time: formatTime() }])
  }

  const handleSend = async (text) => {
    const msg = (text ?? input).trim()
    if (!msg || loading) return
    setInput('')
    addUser(msg)
    setLoading(true)

    try {
      const data = await sendMessage(PHONE, msg)
      applyResponse(data)
      if (data.reply) addBot(data.reply)
    } finally {
      setLoading(false)
    }
  }

  const handleSlot = async (slot, index) => {
    addUser(`Slot ${index + 1}: ${slot.label}`)
    setLoading(true)
    try {
      const data = await selectSlot(PHONE, index + 1)
      applyResponse(data)
      if (data.reply) addBot(data.reply)
      setAppointmentId(data.appointment_id)
      onDashboardRefresh?.()
    } finally {
      setLoading(false)
    }
  }

  const handlePay = async () => {
    if (paymentProcessing || !appointmentId) return
    addUser(`Pay Now — ₹${paymentFee.toLocaleString('en-IN')}`)
    setPaymentProcessing(true)
    setShowPayment(false)
    addBot('💳 Processing mock payment…', { system: true })

    // Simulate Razorpay delay
    await new Promise((r) => setTimeout(r, 1500))

    setLoading(true)
    try {
      const data = await confirmPayment(PHONE, appointmentId)
      applyResponse(data)
      setMessages((m) => m.filter((msg) => !msg.system))
      if (data.reply) addBot(data.reply)
      setBookingConfirmed(true)
      onDashboardRefresh?.()
    } catch {
      addBot('Payment failed. Please try again.')
      setShowPayment(true)
    } finally {
      setLoading(false)
      setPaymentProcessing(false)
    }
  }

  const journeyIdx = getJourneyIndex(state, {
    slots,
    showPayment,
    paymentProcessing,
    bookingConfirmed,
  })

  return (
    <div>
      <div className="phone-frame">
        <div className="phone-screen">
          <div className="wa-header">
            <div className="wa-avatar">H</div>
            <div className="wa-header-info">
              <h3>Finance with Harish</h3>
              <span>{loading ? 'typing…' : `online · ${aiMode === 'ollama' ? 'LLM' : 'Assistant'}`}</span>
            </div>
          </div>

          <div className="wa-messages" ref={messagesRef}>
            {messages.map((m, i) => (
              <div key={i} className={`bubble ${m.role === 'user' ? 'out' : m.system ? 'system' : 'in'}`}>
                <span dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }} />
                <time>{m.time}</time>
              </div>
            ))}

            {activeOptions.length > 0 && !loading && (
              <div className="bubble in">
                <div className={`option-grid ${optionStyle === 'yes_no' ? 'option-yes-no' : ''}`}>
                  {activeOptions.map((opt) => (
                    <button
                      key={opt}
                      className={`option-btn ${optionStyle === 'yes_no' ? 'option-btn-wide' : ''} ${optionStyle === 'chips' ? 'option-btn-chip' : ''}`}
                      onClick={() => handleSend(opt)}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {slots.length > 0 && (
              <div className="bubble in">
                <div className="slot-grid">
                  {slots.map((s, i) => (
                    <button key={s.id} className="slot-btn" onClick={() => handleSlot(s, i)}>
                      {i + 1}. {s.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {showUpload && !loading && (
              <div className="bubble in">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={uploadAccept}
                  style={{ display: 'none' }}
                  onChange={handleFileUpload}
                />
                <button className="upload-btn" onClick={() => fileInputRef.current?.click()}>
                  📎 Choose file to upload
                </button>
                <p className="upload-hint">PDF, PNG, JPG · max 10MB</p>
              </div>
            )}

            {showPayment && !paymentProcessing && (
              <div className="bubble in">
                <div className="mock-pay-card">
                  <div className="mock-pay-header">Demo Payment</div>
                  <div className="mock-pay-amount">₹{paymentFee.toLocaleString('en-IN')}</div>
                  <div className="mock-pay-label">Consultation fee · Mock Razorpay</div>
                </div>
                <button className="pay-btn" onClick={handlePay} disabled={loading}>
                  Pay Now — ₹{paymentFee.toLocaleString('en-IN')} (Mock)
                </button>
              </div>
            )}

            {loading && <div className="typing">● ● ●</div>}
          </div>

          <div className="quick-actions">
            {['Book consultation', 'What are your fees?', 'What services do you offer?'].map((q) => (
              <button key={q} className="quick-btn" onClick={() => handleSend(q)}>
                {q}
              </button>
            ))}
          </div>

          <div className="wa-input-bar">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Type a message"
              disabled={loading}
            />
            <button onClick={() => handleSend()} disabled={loading || !input.trim()}>
              ➤
            </button>
          </div>
        </div>
      </div>

      <div className="journey-panel">
        <h3>Customer Journey Progress</h3>
        <div className="journey-steps">
          {JOURNEY.map((step, i) => (
            <span
              key={step}
              className={`journey-step ${i < journeyIdx ? 'done' : ''} ${i === journeyIdx ? 'active' : ''}`}
              title={i === journeyIdx ? 'Current step' : i < journeyIdx ? 'Completed' : 'Upcoming'}
            >
              {i < journeyIdx ? '✓ ' : ''}{step}
            </span>
          ))}
        </div>
        <p className="journey-hint">Step {journeyIdx + 1} of {JOURNEY.length} · updates as you chat</p>
      </div>
    </div>
  )
}

function AdvisorDashboard({ refreshKey }) {
  const [stats, setStats] = useState(null)
  const [appointments, setAppointments] = useState([])
  const [formLeads, setFormLeads] = useState([])
  const [selectedBrief, setSelectedBrief] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)

  const load = useCallback(async () => {
    try {
      const [s, a, f] = await Promise.all([getStats(), getAppointments(), getFormSubmissions()])
      setStats(s)
      setAppointments(Array.isArray(a) ? a : [])
      setFormLeads(Array.isArray(f) ? f : [])
      setLastUpdated(new Date())
    } catch {
      /* keep last successful snapshot */
    }
  }, [])

  useEffect(() => {
    load()
    const interval = setInterval(load, 3000)
    return () => clearInterval(interval)
  }, [load, refreshKey])

  const handleReset = async () => {
    await resetDemo()
    load()
  }

  const handleSimulateForm = async () => {
    await simulateFormIntake({
      name: `Demo Form User ${Date.now() % 10000}`,
      phone: '+919876543210',
      service: 'Investment Guidance',
      call_format: 'To Book a Online Audio Call consultation',
      investment_amount: '₹10,000 - ₹20,000',
      consultation_tier: 'Regular Consultation',
    })
    load()
  }

  const upcoming = appointments
    .filter((a) => a.status === 'confirmed')
    .sort((a, b) => new Date(a.slot_datetime) - new Date(b.slot_datetime))

  return (
    <div className="dashboard-panel">
      <div className="panel-header">
        <div>
          <h2>Advisor Dashboard</h2>
          {lastUpdated && (
            <span className="live-indicator">Live · updates from chat</span>
          )}
        </div>
        <div className="panel-actions">
          <button className="secondary-btn" onClick={handleSimulateForm}>Simulate Form Submit</button>
          <button onClick={handleReset}>Reset Dashboard</button>
        </div>
      </div>

      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="value">{stats.todays_consultations}</div>
            <div className="label">Today</div>
          </div>
          <div className="stat-card">
            <div className="value">{stats.pending_requests}</div>
            <div className="label">Pending</div>
          </div>
          <div className="stat-card">
            <div className="value">{stats.confirmed}</div>
            <div className="label">Upcoming</div>
          </div>
          <div className="stat-card">
            <div className="value">{stats.follow_ups}</div>
            <div className="label">Follow-ups</div>
          </div>
          <div className="stat-card">
            <div className="value">{stats.form_leads ?? 0}</div>
            <div className="label">Form leads</div>
          </div>
        </div>
      )}

      {formLeads.length > 0 && (
        <div className="form-leads-list">
          <h3>Google Form leads (awaiting WhatsApp follow-up)</h3>
          {formLeads.map((f) => (
            <div key={f.id} className="form-lead-row">
              <div>
                <div className="appt-name">{f.name}</div>
                <div className="appt-type">{f.phone} · {f.service || '—'}</div>
              </div>
              <div className="form-lead-meta">
                <span className="status-badge pending">{f.status}</span>
                <span className="form-lead-fee">₹{(f.fee_amount || 0).toLocaleString('en-IN')}</span>
              </div>
            </div>
          ))}
          <p style={{ fontSize: '0.8rem', color: 'var(--slate)', marginTop: 8 }}>
            Open Customer WhatsApp tab with the same phone number to continue the journey.
          </p>
        </div>
      )}

      <div className="appointments-list">
        <h3>Upcoming Consultations</h3>
        {upcoming.length === 0 && (
          <p style={{ color: 'var(--slate)', fontSize: '0.9rem' }}>
            No appointments yet. Complete a booking in the WhatsApp demo, or click Load Sample Data.
          </p>
        )}
        {upcoming.map((a) => (
          <div key={a.id} className="appt-row" onClick={() => setSelectedBrief(a.consultation_brief)}>
            <div className="appt-time">
              {new Date(a.slot_datetime).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })}
              <br />
              {new Date(a.slot_datetime).toLocaleTimeString('en-IN', {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </div>
            <div>
              <div className="appt-name">{a.customer_name}</div>
              <div className="appt-type">
                {a.consultation_type}
                {a.intake_source === 'google_form' && <span className="source-tag"> · Form</span>}
              </div>
            </div>
            <span className={`status-badge ${a.status}`}>{a.payment_status}</span>
          </div>
        ))}
        <p style={{ marginTop: 16, fontSize: '0.8rem', color: 'var(--slate)' }}>
          Click a row to view the AI-generated consultation brief →
        </p>
      </div>

      {selectedBrief && (
        <div className="brief-modal" onClick={() => setSelectedBrief(null)}>
          <div className="brief-content" onClick={(e) => e.stopPropagation()}>
            <h3>Consultation Brief</h3>
            <pre>{selectedBrief}</pre>
            <button onClick={() => setSelectedBrief(null)}>Close</button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function App() {
  const [tab, setTab] = useState('demo')
  const [refreshKey, setRefreshKey] = useState(0)
  const bumpDashboard = useCallback(() => setRefreshKey((k) => k + 1), [])

  return (
    <div className={`app-shell ${tab === 'dashboard' ? 'full-width-view' : ''}`}>
      <header className="app-header">
        <h1>Finance with Harish</h1>
        <p>Consultation Journey Automation — MVP Demo</p>
      </header>

      <div className="demo-tabs">
        <button className={`demo-tab ${tab === 'demo' ? 'active' : ''}`} onClick={() => setTab('demo')}>
          Customer WhatsApp
        </button>
        <button
          className={`demo-tab ${tab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setTab('dashboard')}
        >
          Advisor Dashboard
        </button>
      </div>

      {tab === 'demo' ? (
        <div className="demo-grid chat-only-view">
          <ViewErrorBoundary>
            <WhatsAppChat onDashboardRefresh={bumpDashboard} />
          </ViewErrorBoundary>
        </div>
      ) : (
        <div className="demo-grid full-dashboard-view">
          <ViewErrorBoundary>
            <AdvisorDashboard refreshKey={refreshKey} />
          </ViewErrorBoundary>
        </div>
      )}
    </div>
  )
}
