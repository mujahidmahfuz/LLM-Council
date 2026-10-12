import { describe, expect, it } from 'vitest'
import { formatScore, shortName, splitModelId } from './format'

describe('splitModelId', () => {
  it('separates vendor and name and drops the pricing tier', () => {
    expect(splitModelId('nvidia/nemotron-3-super-120b-a12b:free')).toEqual({
      vendor: 'nvidia',
      name: 'nemotron-3-super-120b-a12b',
    })
  })

  it('handles ids without a vendor or tier', () => {
    expect(splitModelId('solo')).toEqual({ vendor: '', name: 'solo' })
  })

  it('keeps dots in names', () => {
    expect(splitModelId('liquid/lfm-2.5-2.6b:free').name).toBe('lfm-2.5-2.6b')
  })
})

describe('shortName', () => {
  it('leaves short names alone', () => {
    expect(shortName('a/tiny:free')).toBe('tiny')
  })

  it('truncates long names with an ellipsis', () => {
    const result = shortName('v/a-very-long-model-name-indeed:free', 10)
    expect(result).toBe('a-very-lo…')
    expect(result).toHaveLength(10)
  })
})

describe('formatScore', () => {
  it.each([
    [1, '100%'],
    [0.6667, '67%'],
    [0, '0%'],
    [null, 'n/a'],
    [undefined, 'n/a'],
  ])('formats %s as %s', (input, expected) => {
    expect(formatScore(input)).toBe(expected)
  })
})
