import type { BillingBlock } from '@hermes/shared/billing'

/**
 * Sticky status-bar CTA text for a billing wall (out of credits). The text
 * carries its own ✕ glyph per the `Notice` convention (the renderer only
 * colours by level). Nous routes to the native `/topup` overlay; other
 * providers get their derived billing page (or a generic nudge when we have no
 * URL). Pure + exported so the copy is unit-tested without driving the gateway.
 */
export function billingNoticeText(block: BillingBlock): string {
  if (block.is_nous) {
    return '✕ Out of Nous credits · run /topup to add credits'
  }

  const label = block.provider_label || 'your provider'

  return block.billing_url
    ? `✕ Out of credits (${label}) · add credits at ${block.billing_url}`
    : `✕ Out of credits (${label}) · add credits with your provider`
}
