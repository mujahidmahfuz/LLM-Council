import { formatScore, splitModelId } from '../lib/format'

function reviewSummary(reviews) {
  const counted = reviews.filter((review) => review.ranking.length > 0).length
  return `${counted} of ${reviews.length} peer reviews counted`
}

/** Consensus ranking: how the members themselves rated each other. */
export default function Leaderboard({ leaderboard, reviews, winner }) {
  if (leaderboard.length === 0) return null
  const hasScores = leaderboard.some((entry) => entry.score !== null)
  return (
    <section className="panel" aria-labelledby="leaderboard-title">
      <h2 id="leaderboard-title">Consensus ranking</h2>
      <p className="muted">
        {hasScores
          ? `Each member ranked the others anonymously (never itself). ${reviewSummary(reviews)}.`
          : 'Peer review was skipped, so no ranking is available.'}
      </p>
      <ol className="leaderboard">
        {leaderboard.map((entry, index) => {
          const { vendor, name } = splitModelId(entry.model)
          const isWinner = entry.model === winner
          return (
            <li key={entry.model} className={isWinner ? 'is-winner' : undefined}>
              <span className="place">{hasScores ? index + 1 : '•'}</span>
              <span className="who">
                <strong>{name}</strong>
                <small>{vendor}</small>
              </span>
              <span className="bar" aria-hidden="true">
                <span style={{ width: `${Math.round((entry.score ?? 0) * 100)}%` }} />
              </span>
              <span className="score" title={`${entry.votes} reviewer(s)`}>
                {formatScore(entry.score)}
              </span>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
