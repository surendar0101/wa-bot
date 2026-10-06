const API = '/api'

export async function startChat(phone) {
  const res = await fetch(`${API}/chat/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone }),
  })
  return res.json()
}

export async function sendMessage(phone, message) {
  const res = await fetch(`${API}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone, message }),
  })
  return res.json()
}

export async function selectSlot(phone, slotId) {
  const res = await fetch(`${API}/chat/select-slot`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone, slot_id: String(slotId) }),
  })
  return res.json()
}

export async function confirmPayment(phone, appointmentId) {
  const res = await fetch(`${API}/chat/pay`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone, appointment_id: appointmentId }),
  })
  return res.json()
}

export async function uploadInvestmentDoc(phone, file) {
  const form = new FormData()
  form.append('phone', phone)
  form.append('file', file)
  const res = await fetch(`${API}/chat/upload-investment`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Upload failed')
  }
  return res.json()
}

export async function getHealth() {
  const res = await fetch(`${API}/health`)
  return res.json()
}

export async function getStats() {
  const res = await fetch(`${API}/dashboard/stats`)
  return res.json()
}

export async function getAppointments() {
  const res = await fetch(`${API}/dashboard/appointments`)
  return res.json()
}

export async function seedDemo() {
  const res = await fetch(`${API}/demo/seed`, { method: 'POST' })
  return res.json()
}

export async function getFormSubmissions() {
  const res = await fetch(`${API}/dashboard/form-submissions`)
  return res.json()
}

export async function simulateFormIntake(payload) {
  const res = await fetch(`${API}/demo/simulate-form`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return res.json()
}

export async function resetDemo() {
  const res = await fetch(`${API}/demo/reset`, { method: 'POST' })
  return res.json()
}
