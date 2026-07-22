import type { BillingBlock } from '@hermes/shared/billing'
import { describe, expect, it } from 'vitest'

import { billingNoticeText } from './billingNotice.js'

function makeBlock(overrides: Partial<BillingBlock> = {}): BillingBlock {
  return {
    billing_url: 'https://openrouter.ai/settings/credits',
    is_nous: false,
    message: 'out of credits',
    model: 'x',
    provider: 'openrouter',
    provider_label: 'OpenRouter',
    ...overrides
  }
}

describe('billingNoticeText', () => {
  it('points Nous users at /topup', () => {
    const text = billingNoticeText(makeBlock({ is_nous: true, provider: 'nous', provider_label: 'Nous Portal' }))
    expect(text).toContain('/topup')
    expect(text.startsWith('✕')).toBe(true)
  })

  it('deep-links a third-party provider by URL', () => {
    const text = billingNoticeText(makeBlock())
    expect(text).toContain('OpenRouter')
    expect(text).toContain('https://openrouter.ai/settings/credits')
  })

  it('degrades to a generic nudge when a provider has no URL', () => {
    const text = billingNoticeText(makeBlock({ billing_url: null, provider_label: 'DeepSeek' }))
    expect(text).toContain('DeepSeek')
    expect(text).not.toContain('http')
  })
})
