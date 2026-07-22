import { useStore } from '@nanostores/react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { useI18n } from '@/i18n'
import { CreditCard } from '@/lib/icons'
import { cn } from '@/lib/utils'
import { $billingBlock, billingCtaLabel, clearBillingBlock, runBillingRecovery } from '@/store/billing-block'

function firstLine(text: string): string {
  return (text || '').split('\n')[0]?.trim() ?? ''
}

/**
 * Persistent, in-chat billing wall. Renders only when the active billing block
 * belongs to THIS session. It never disables the composer — slash commands
 * (`/topup`, `/model`, `/login`) must stay usable — it just offers recovery:
 * Nous opens Settings → Billing in-app, other providers deep-link out.
 */
export function BillingBanner({ sessionId }: { sessionId: null | string }) {
  const active = useStore($billingBlock)
  const { t } = useI18n()

  if (!active || !sessionId || active.sessionId !== sessionId) {
    return null
  }

  const { block } = active
  const copy = t.billingBlock
  const title = block.is_nous ? copy.titleNous : copy.titleProvider(block.provider_label)
  const message = firstLine(block.message) || copy.fallbackMessage

  return (
    <Alert
      className={cn('m-1 grid-cols-[auto_minmax(0,1fr)_auto] border-(--stroke-nous) bg-popover/80 pr-2.5')}
      role="status"
      variant="warning"
    >
      <CreditCard className="text-primary" />
      <div className="col-start-2 min-w-0">
        <AlertTitle className="col-start-auto">{title}</AlertTitle>
        <AlertDescription className="col-start-auto">
          <p className="m-0">{message}</p>
          <Button
            className="mt-1.5"
            onClick={() => runBillingRecovery(block)}
            size="xs"
            type="button"
            variant="textStrong"
          >
            {billingCtaLabel(block, copy)}
          </Button>
        </AlertDescription>
      </div>
      <Button
        aria-label={copy.dismiss}
        className="col-start-3 -mr-1 text-muted-foreground"
        onClick={() => clearBillingBlock(sessionId)}
        size="icon-xs"
        type="button"
        variant="ghost"
      >
        <Codicon name="close" size="0.875rem" />
      </Button>
    </Alert>
  )
}
