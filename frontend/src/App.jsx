import { useCallback, useEffect, useReducer, useRef, useState } from 'react'
import './App.css'
import Answers from './components/Answers'
import Leaderboard from './components/Leaderboard'
import RoundTable from './components/RoundTable'
import { askCouncil, fetchConfig } from './lib/councilApi'
import { PHASE_LABELS, councilReducer, initialState, seatStatus } from './lib/councilState'

const BUSY_PHASES = new Set(['answers', 'reviews', 'verdict'])

function App() {
  const [state, dispatch] = useReducer(councilReducer, initialState)
  const [prompt, setPrompt] = useState('')
  const [peerReview, setPeerReview] = useState(true)
  const [backendError, setBackendError] = useState(null)
  const abortRef = useRef(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchConfig(controller.signal)
      .then((config) => dispatch({ type: 'config', members: config.members, chairman: config.chairman }))
      .catch((error) => {
        if (error.name !== 'AbortError') {
          setBackendError('Cannot reach the council backend. Is it running on port 8000?')
        }
      })
    return () => {
      controller.abort()
      abortRef.current?.abort()
    }
  }, [])

  const busy = BUSY_PHASES.has(state.phase)

  const handleSubmit = useCallback(
    async (event) => {
      event.preventDefault()
      const question = prompt.trim()
      if (!question || busy) return

      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      dispatch({ type: 'start' })
      setBackendError(null)

      try {
        for await (const serverEvent of askCouncil({ prompt: question, peerReview }, controller.signal)) {
          dispatch(serverEvent)
        }
      } catch (error) {
        if (error.name !== 'AbortError') {
          dispatch({ type: 'error', message: error.message || 'The connection to the council was lost.' })
        }
      }
    },
    [prompt, peerReview, busy],
  )

  const chairmanStatus =
    state.phase === 'verdict' ? 'thinking' : state.phase === 'done' ? 'answered' : 'idle'

  return (
    <main className="container">
      <header className="hero">
        <h1>🧙‍♂️ The High Council</h1>
        <p className="tagline">
          Several LLMs answer your question, rank each other&apos;s work blind, and a chairman delivers the
          final ruling.
        </p>
      </header>

      {backendError && (
        <p className="banner banner-error" role="alert">
          {backendError}
        </p>
      )}

      <form className="input-area" onSubmit={handleSubmit}>
        <label htmlFor="question" className="visually-hidden">
          Your question for the council
        </label>
        <textarea
          id="question"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="Ask the council anything…"
          rows={3}
          disabled={busy}
        />
        <div className="controls">
          <label className="check">
            <input
              type="checkbox"
              checked={peerReview}
              onChange={(event) => setPeerReview(event.target.checked)}
              disabled={busy}
            />
            Peer review (more requests, gives a consensus ranking)
          </label>
          <button type="submit" disabled={busy || !prompt.trim()}>
            {busy ? 'Council is deliberating…' : 'Consult the council'}
          </button>
        </div>
      </form>

      <p className="status" role="status" aria-live="polite">
        {PHASE_LABELS[state.phase]}
      </p>

      {state.phase === 'error' && (
        <p className="banner banner-error" role="alert">
          {state.error}
        </p>
      )}

      {state.members.length > 0 && (
        <RoundTable
          members={state.members}
          chairman={state.chairman}
          statusOf={(model) => seatStatus(state, model)}
          chairmanStatus={chairmanStatus}
        />
      )}

      {state.verdict && (
        <section className="verdict-card" aria-labelledby="verdict-title">
          <h2 id="verdict-title">👑 The Council&apos;s Decision</h2>
          {state.verdictSource === 'fallback' && (
            <p className="banner banner-warn">
              The chairman was unavailable ({state.chairmanError}), so this is the top-ranked member&apos;s
              answer.
            </p>
          )}
          <p className="verdict-text">{state.verdict}</p>
        </section>
      )}

      <Leaderboard
        leaderboard={state.leaderboard}
        reviews={state.reviews}
        winner={state.winner}
        agreement={state.agreement}
      />
      <Answers answers={state.answers} />
    </main>
  )
}

export default App
