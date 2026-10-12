/** "nvidia/nemotron-3-super-120b-a12b:free" -> { vendor: "nvidia", name: "nemotron-3-super-120b-a12b" } */
export function splitModelId(id) {
  const withoutTier = id.replace(/:[\w-]+$/, '')
  const slash = withoutTier.indexOf('/')
  if (slash === -1) return { vendor: '', name: withoutTier }
  return { vendor: withoutTier.slice(0, slash), name: withoutTier.slice(slash + 1) }
}

export function shortName(id, max = 18) {
  const { name } = splitModelId(id)
  return name.length > max ? `${name.slice(0, max - 1)}…` : name
}

/** Reviewer agreement (Kendall tau, -1..1) in words. */
export function describeAgreement(value) {
  if (value === null || value === undefined) return null
  if (value >= 0.7) return 'strong'
  if (value >= 0.3) return 'moderate'
  return 'split'
}

/** 0.6667 -> "67%"; null -> "n/a" */
export function formatScore(score) {
  return score === null || score === undefined ? 'n/a' : `${Math.round(score * 100)}%`
}
