// Talks to the FastAPI backend. Events arrive as newline-delimited JSON.

export const API_BASE = (import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000').replace(/\/+$/, '')

/** Yield each parsed JSON object from an NDJSON byte stream. */
export async function* readNdjson(body) {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()
      for (const line of lines) {
        if (line.trim()) yield JSON.parse(line)
      }
    }
    buffer += decoder.decode()
    if (buffer.trim()) yield JSON.parse(buffer)
  } finally {
    reader.releaseLock()
  }
}

/** Turn a failed HTTP response into a readable Error. */
export async function errorFromResponse(response) {
  let detail = `The server answered ${response.status}.`
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') detail = body.detail
    else if (Array.isArray(body.detail)) detail = 'Please enter a question for the council.'
  } catch {
    // keep the generic message
  }
  return new Error(detail)
}

export async function fetchConfig(signal) {
  const response = await fetch(`${API_BASE}/config`, { signal })
  if (!response.ok) throw await errorFromResponse(response)
  return response.json()
}

/** Ask the council and yield progress events as they happen. */
export async function* askCouncil({ prompt, peerReview }, signal) {
  const response = await fetch(`${API_BASE}/ask-council/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, peer_review: peerReview }),
    signal,
  })
  if (!response.ok) throw await errorFromResponse(response)
  yield* readNdjson(response.body)
}
