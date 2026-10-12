// Pure state logic for a council session, kept free of React so it is easy to test.

export const initialState = {
  phase: 'idle', // idle | answers | reviews | verdict | done | error
  members: [],
  answers: [],
  reviews: [],
  leaderboard: [],
  winner: null,
  chairman: null,
  verdict: null,
  verdictSource: null,
  chairmanError: null,
  error: null,
}

/**
 * Fold one server event (or a local `start` / `config`) into the session state.
 * Server events: stage, answers, reviews, complete, error.
 */
export function councilReducer(state, action) {
  switch (action.type) {
    case 'start':
      return { ...initialState, phase: 'answers', members: state.members, chairman: state.chairman }
    case 'config':
      return { ...state, members: action.members, chairman: action.chairman }
    case 'stage': {
      const next = { ...state, phase: action.stage }
      if (action.stage === 'answers') next.members = action.models
      if (action.stage === 'verdict') next.chairman = action.models[0]
      return next
    }
    case 'answers':
      return { ...state, answers: action.answers }
    case 'reviews':
      return {
        ...state,
        reviews: action.reviews,
        leaderboard: action.leaderboard,
        winner: action.winner,
      }
    case 'complete': {
      const result = action.result
      return {
        ...state,
        phase: 'done',
        answers: result.individual_responses,
        reviews: result.reviews,
        leaderboard: result.leaderboard,
        winner: result.winner,
        chairman: result.chairman,
        verdict: result.council_verdict,
        verdictSource: result.verdict_source,
        chairmanError: result.chairman_error,
      }
    }
    case 'error':
      return { ...state, phase: 'error', error: action.message }
    default:
      return state
  }
}

/** The visible state of one seat at the table: idle | thinking | reviewing | answered | failed | winner */
export function seatStatus(state, model) {
  const answer = state.answers.find((a) => a.model === model)
  const failed = answer ? !answer.answer : false
  switch (state.phase) {
    case 'idle':
    case 'error':
      return failed ? 'failed' : 'idle'
    case 'answers':
      return 'thinking'
    case 'reviews':
      return failed ? 'failed' : 'reviewing'
    default:
      if (failed) return 'failed'
      return state.winner === model ? 'winner' : 'answered'
  }
}

export const PHASE_LABELS = {
  idle: 'The council awaits your question.',
  answers: 'Round 1 of 3: every member is drafting an answer…',
  reviews: 'Round 2 of 3: members are anonymously ranking each other…',
  verdict: 'Round 3 of 3: the chairman is writing the ruling…',
  done: 'The council has ruled.',
  error: 'The council could not reach a verdict.',
}
