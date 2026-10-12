import { shortName } from '../lib/format'

const SIZE = 460
const CENTER = SIZE / 2
const RING_RADIUS = 150

const STATUS_TEXT = {
  idle: 'waiting',
  thinking: 'thinking',
  reviewing: 'reviewing',
  answered: 'answered',
  failed: 'failed',
  winner: 'winner',
}

function seatPosition(slot, total) {
  const angle = ((-90 + (360 * slot) / total) * Math.PI) / 180
  return {
    x: CENTER + RING_RADIUS * Math.cos(angle),
    y: CENTER + RING_RADIUS * Math.sin(angle),
    cos: Math.cos(angle),
    sin: Math.sin(angle),
  }
}

function Seat({ position, glyph, name, status, large = false }) {
  const radius = large ? 34 : 28
  const labelX = position.x + position.cos * (radius + 10)
  const labelY = position.y + position.sin * (radius + 14)
  const anchor = Math.abs(position.cos) < 0.3 ? 'middle' : position.cos > 0 ? 'start' : 'end'
  // Seats at the top put their label above the ring, so the status line must sit closer to it.
  const above = position.sin < -0.5
  const nameY = labelY + (above ? -12 : 0)
  const statusY = labelY + (above ? 2 : 14)
  return (
    <g className={`seat seat-${status}`}>
      <title>{`${name}: ${STATUS_TEXT[status] ?? status}`}</title>
      <circle className="seat-ring" cx={position.x} cy={position.y} r={radius} />
      <text className="seat-glyph" x={position.x} y={position.y} textAnchor="middle" dominantBaseline="central">
        {status === 'winner' ? '🏆' : glyph}
      </text>
      <text className="seat-name" x={labelX} y={nameY} textAnchor={anchor} dominantBaseline="central">
        {shortName(name, 16)}
      </text>
      <text className="seat-status" x={labelX} y={statusY} textAnchor={anchor} dominantBaseline="central">
        {STATUS_TEXT[status] ?? status}
      </text>
    </g>
  )
}

/** Scientists around a table, the chairman at the head (top). */
export default function RoundTable({ members, chairman, statusOf, chairmanStatus }) {
  const total = members.length + 1
  const chairPosition = seatPosition(0, total)
  return (
    <svg
      className="round-table"
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      role="img"
      aria-label={`Round table with ${members.length} council members and the chairman`}
    >
      <circle className="table-top" cx={CENTER} cy={CENTER} r={RING_RADIUS - 38} />
      <text className="table-label" x={CENTER} y={CENTER} textAnchor="middle" dominantBaseline="central">
        LLM Council
      </text>
      {members.map((model, index) => (
        <Seat
          key={model}
          position={seatPosition(index + 1, total)}
          glyph="🧑‍🔬"
          name={model}
          status={statusOf(model)}
        />
      ))}
      {chairman && (
        <Seat position={chairPosition} glyph="⚖️" name={chairman} status={chairmanStatus} large />
      )}
    </svg>
  )
}
