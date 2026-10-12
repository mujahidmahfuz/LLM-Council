import { describe, expect, it } from 'vitest'
import { PHASE_LABELS, councilReducer, initialState, seatStatus } from './councilState'

const answers = [
  { model: 'a/one', answer: 'text', error: null },
  { model: 'b/two', answer: null, error: 'HTTP 429: rate limited' },
]

const result = {
  question: 'q',
  individual_responses: answers,
  reviews: [],
  leaderboard: [{ model: 'a/one', score: 1, average_rank: 1, votes: 2 }],
  winner: 'a/one',
  chairman: 'c/chair',
  council_verdict: 'ruling',
  verdict_source: 'chairman',
  chairman_error: null,
}

function run(events, state = initialState) {
  return events.reduce(councilReducer, state)
}

describe('councilReducer', () => {
  it('stores the configured round table', () => {
    const state = run([{ type: 'config', members: ['a/one'], chairman: 'c/chair' }])
    expect(state.members).toEqual(['a/one'])
    expect(state.chairman).toBe('c/chair')
    expect(state.phase).toBe('idle')
  })

  it('start clears the previous session but keeps the seating', () => {
    const finished = run([
      { type: 'config', members: ['a/one'], chairman: 'c/chair' },
      { type: 'complete', result },
    ])
    const restarted = councilReducer(finished, { type: 'start' })
    expect(restarted).toMatchObject({
      phase: 'answers',
      members: ['a/one'],
      chairman: 'c/chair',
      verdict: null,
      answers: [],
      leaderboard: [],
    })
  })

  it('follows the three stages in order', () => {
    let state = run([{ type: 'stage', stage: 'answers', models: ['a/one', 'b/two'] }])
    expect(state.phase).toBe('answers')
    expect(state.members).toEqual(['a/one', 'b/two'])

    state = run([{ type: 'answers', answers }, { type: 'stage', stage: 'reviews', models: ['a/one'] }], state)
    expect(state.phase).toBe('reviews')
    expect(state.answers).toEqual(answers)

    state = run([{ type: 'stage', stage: 'verdict', models: ['c/chair'] }], state)
    expect(state.phase).toBe('verdict')
    expect(state.chairman).toBe('c/chair')
  })

  it('records reviews, leaderboard and winner', () => {
    const state = run([
      {
        type: 'reviews',
        reviews: [{ reviewer: 'a/one', ranking: ['b/two'], error: null }],
        leaderboard: result.leaderboard,
        winner: 'a/one',
      },
    ])
    expect(state.winner).toBe('a/one')
    expect(state.leaderboard).toHaveLength(1)
    expect(state.reviews).toHaveLength(1)
  })

  it('complete fills in the verdict', () => {
    const state = run([{ type: 'complete', result }])
    expect(state).toMatchObject({
      phase: 'done',
      verdict: 'ruling',
      verdictSource: 'chairman',
      winner: 'a/one',
      chairman: 'c/chair',
    })
  })

  it('error sets the message and phase', () => {
    expect(run([{ type: 'error', message: 'boom' }])).toMatchObject({ phase: 'error', error: 'boom' })
  })

  it('ignores unknown actions', () => {
    expect(councilReducer(initialState, { type: 'nope' })).toBe(initialState)
  })

  it('does not mutate the previous state', () => {
    const before = structuredClone(initialState)
    councilReducer(initialState, { type: 'answers', answers })
    expect(initialState).toEqual(before)
  })
})

describe('seatStatus', () => {
  const base = { ...initialState, answers }

  it.each([
    ['idle', 'a/one', 'idle'],
    ['answers', 'a/one', 'thinking'],
    ['answers', 'b/two', 'thinking'],
    ['reviews', 'a/one', 'reviewing'],
    ['reviews', 'b/two', 'failed'],
    ['done', 'a/one', 'answered'],
    ['done', 'b/two', 'failed'],
  ])('in phase %s, %s is %s', (phase, model, expected) => {
    expect(seatStatus({ ...base, phase }, model)).toBe(expected)
  })

  it('marks the winner once the council has ruled', () => {
    expect(seatStatus({ ...base, phase: 'done', winner: 'a/one' }, 'a/one')).toBe('winner')
  })

  it('has a label for every phase', () => {
    for (const phase of ['idle', 'answers', 'reviews', 'verdict', 'done', 'error']) {
      expect(PHASE_LABELS[phase]).toBeTruthy()
    }
  })
})
