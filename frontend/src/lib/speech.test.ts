import { describe, expect, it } from 'vitest'

import { toSpeech } from './speech'

describe('toSpeech', () => {
  it('reads Markdown replies as plain sentences', () => {
    const reply = [
      'Start with **lockout/tagout** per `SAF-01`:',
      '',
      '- isolate traction supply',
      '- apply the parking brake',
      '',
      'See [the manual](https://example.com).',
    ].join('\n')

    expect(toSpeech(reply)).toBe(
      'Start with lockout/tagout per SAF-01: isolate traction supply. apply the parking brake. See the manual.',
    )
  })
})
