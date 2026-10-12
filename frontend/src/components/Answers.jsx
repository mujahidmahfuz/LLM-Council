import { splitModelId } from '../lib/format'

/** Every member's own answer, collapsed by default. */
export default function Answers({ answers }) {
  if (answers.length === 0) return null
  return (
    <section className="panel" aria-labelledby="answers-title">
      <h2 id="answers-title">Individual opinions</h2>
      <div className="grid">
        {answers.map((item) => {
          const { vendor, name } = splitModelId(item.model)
          return (
            <details key={item.model} className={`card ${item.answer ? '' : 'card-failed'}`}>
              <summary>
                <strong>{name}</strong>
                <small>{vendor}</small>
              </summary>
              {item.answer ? (
                <p className="answer-text">{item.answer}</p>
              ) : (
                <p className="error-text">Could not answer: {item.error}</p>
              )}
            </details>
          )
        })}
      </div>
    </section>
  )
}
