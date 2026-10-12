import { describe, expect, it } from 'vitest'
import { errorFromResponse, readNdjson } from './councilApi'

const encoder = new TextEncoder()

function streamOf(...chunks) {
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(typeof chunk === 'string' ? encoder.encode(chunk) : chunk)
      controller.close()
    },
  })
}

async function collect(stream) {
  const events = []
  for await (const event of readNdjson(stream)) events.push(event)
  return events
}

describe('readNdjson', () => {
  it('parses one event per line', async () => {
    const events = await collect(streamOf('{"type":"a"}\n{"type":"b"}\n'))
    expect(events).toEqual([{ type: 'a' }, { type: 'b' }])
  })

  it('reassembles events split across chunks', async () => {
    const events = await collect(streamOf('{"type":"sta', 'ge","n":1}\n{"ty', 'pe":"b"}\n'))
    expect(events).toEqual([{ type: 'stage', n: 1 }, { type: 'b' }])
  })

  it('handles multi-byte characters split between chunks', async () => {
    const bytes = encoder.encode('{"text":"é🧙"}\n')
    const events = await collect(streamOf(bytes.slice(0, 10), bytes.slice(10)))
    expect(events).toEqual([{ text: 'é🧙' }])
  })

  it('reads a final line with no trailing newline', async () => {
    expect(await collect(streamOf('{"type":"last"}'))).toEqual([{ type: 'last' }])
  })

  it('skips blank lines', async () => {
    expect(await collect(streamOf('\n{"type":"a"}\n\n'))).toEqual([{ type: 'a' }])
  })

  it('rejects malformed JSON', async () => {
    await expect(collect(streamOf('not json\n'))).rejects.toThrow(SyntaxError)
  })

  it('yields nothing for an empty stream', async () => {
    expect(await collect(streamOf())).toEqual([])
  })
})

describe('errorFromResponse', () => {
  it('uses a string detail from the server', async () => {
    const response = new Response(JSON.stringify({ detail: 'OpenRouter API key missing.' }), { status: 503 })
    expect((await errorFromResponse(response)).message).toBe('OpenRouter API key missing.')
  })

  it('turns validation errors into a friendly message', async () => {
    const response = new Response(JSON.stringify({ detail: [{ msg: 'too short' }] }), { status: 422 })
    expect((await errorFromResponse(response)).message).toMatch(/enter a question/)
  })

  it('falls back to the status code when the body is not JSON', async () => {
    const response = new Response('<html>oops</html>', { status: 500 })
    expect((await errorFromResponse(response)).message).toBe('The server answered 500.')
  })
})
