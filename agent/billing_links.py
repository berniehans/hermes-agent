"""Provider-agnostic billing/credit recovery links.

When an inference call fails with :attr:`FailoverReason.billing` (credits
exhausted, payment required, subscription/entitlement gap), every Hermes
surface — CLI, TUI, desktop app, messaging gateway — needs the *same*
actionable information:

* which provider ran out,
* a billing / top-up URL to send the user to, and
* whether it is the Nous-managed route (which has in-app billing UI) or a
  third-party provider (which we deep-link to their own dashboard).

Detection is NOT done here — that lives in :mod:`agent.error_classifier`
(``FailoverReason.billing``), the single source of truth for "is this a
billing wall vs. a rate limit / auth / transport failure". This module only
maps a ``(provider, base_url, model)`` triple into a recovery link + label.

The resulting :class:`BillingBlock` is serialized into the turn result and
forwarded on the gateway ``message.complete`` / ``error`` events so the CLI,
TUI, and desktop app all render from one structured signal instead of
re-parsing free-form error text on each surface.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from utils import base_url_host_matches


@dataclass
class BillingBlock:
    """Structured billing-wall descriptor shared across every surface.

    ``is_nous`` is the important routing bit: Nous is the managed route with a
    first-class in-app billing surface (desktop Settings → Billing, the TUI
    ``/topup`` overlay, the CLI ``/topup`` command), so surfaces should prefer
    that flow over ``billing_url``. For third-party providers there is no
    in-app billing, so ``billing_url`` is the deep link the user actually needs.
    """

    provider: str
    provider_label: str
    model: str
    billing_url: Optional[str]
    is_nous: bool
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


# ── Provider → (label, billing URL) ─────────────────────────────────────
# Keyed by the internal provider slug. Kept deliberately small and curated —
# these are the "add credits / manage billing" landing pages, not marketing
# home pages. A missing provider degrades gracefully to ``billing_url=None``
# (surfaces still show the provider name + the server's error text).
_PROVIDER_BILLING: dict[str, tuple[str, str]] = {
    "openai": ("OpenAI", "https://platform.openai.com/settings/organization/billing"),
    "anthropic": ("Anthropic", "https://console.anthropic.com/settings/billing"),
    "openrouter": ("OpenRouter", "https://openrouter.ai/settings/credits"),
    "xai": ("xAI", "https://console.x.ai/team/default/billing"),
    "xai-oauth": ("xAI", "https://console.x.ai/team/default/billing"),
    "deepseek": ("DeepSeek", "https://platform.deepseek.com/top_up"),
    "groq": ("Groq", "https://console.groq.com/settings/billing"),
    "mistral": ("Mistral", "https://console.mistral.ai/billing"),
    "together": ("Together AI", "https://api.together.ai/settings/billing"),
    "fireworks": ("Fireworks AI", "https://fireworks.ai/account/billing"),
    "perplexity": ("Perplexity", "https://www.perplexity.ai/settings/api"),
    "google": ("Google AI", "https://aistudio.google.com/app/billing"),
    "gemini": ("Google AI", "https://aistudio.google.com/app/billing"),
    "cohere": ("Cohere", "https://dashboard.cohere.com/billing"),
    "moonshot": ("Moonshot AI", "https://platform.moonshot.ai/console/pay"),
    "nvidia": ("NVIDIA", "https://build.nvidia.com/settings/billing"),
}

# ── base_url host substring → (label, billing URL) ──────────────────────
# Fallback for OpenAI-compatible custom routes where the provider slug is a
# generic bucket (e.g. "openai_compatible") but the base_url reveals who the
# upstream really is.
_HOST_BILLING: tuple[tuple[str, str, str], ...] = (
    ("openrouter.ai", "OpenRouter", "https://openrouter.ai/settings/credits"),
    ("api.openai.com", "OpenAI", "https://platform.openai.com/settings/organization/billing"),
    ("api.anthropic.com", "Anthropic", "https://console.anthropic.com/settings/billing"),
    ("api.x.ai", "xAI", "https://console.x.ai/team/default/billing"),
    ("api.deepseek.com", "DeepSeek", "https://platform.deepseek.com/top_up"),
    ("api.groq.com", "Groq", "https://console.groq.com/settings/billing"),
    ("api.mistral.ai", "Mistral", "https://console.mistral.ai/billing"),
    ("api.together.xyz", "Together AI", "https://api.together.ai/settings/billing"),
    ("api.together.ai", "Together AI", "https://api.together.ai/settings/billing"),
    ("fireworks.ai", "Fireworks AI", "https://fireworks.ai/account/billing"),
    ("perplexity.ai", "Perplexity", "https://www.perplexity.ai/settings/api"),
    ("generativelanguage.googleapis.com", "Google AI", "https://aistudio.google.com/app/billing"),
)


def is_nous_inference_route(provider: str, base_url: str) -> bool:
    """True when the failing route is the Nous-managed inference gateway.

    Kept here (not imported from conversation_loop) so this module has no
    dependency on the agent loop and can be unit-tested in isolation.
    """
    if (provider or "").strip().lower() == "nous":
        return True
    return base_url_host_matches(str(base_url or ""), "inference-api.nousresearch.com")


def _nous_billing_url() -> Optional[str]:
    """Best-effort Nous portal billing URL (no network — uses the default base).

    For Nous the in-app flow (``is_nous=True``) is what surfaces should use;
    this URL is only a fallback for text surfaces / messaging.
    """
    try:
        from hermes_cli.nous_account import nous_portal_billing_url

        return nous_portal_billing_url(None)
    except Exception:
        return "https://portal.nousresearch.com/billing"


def _resolve_provider_link(provider_slug: str, base_url: str) -> tuple[str, Optional[str]]:
    """Resolve ``(label, billing_url)`` for a non-Nous provider.

    Order: exact provider slug → base_url host substring → generic fallback
    (label derived from the slug, no URL).
    """
    if provider_slug in _PROVIDER_BILLING:
        label, url = _PROVIDER_BILLING[provider_slug]
        return label, url

    base = str(base_url or "")
    for host, label, url in _HOST_BILLING:
        if base_url_host_matches(base, host):
            return label, url

    # Unknown provider — surface a readable label, no invented URL.
    label = provider_slug.replace("_", " ").replace("-", " ").strip().title() or "your provider"
    return label, None


def build_billing_block(
    *,
    provider: str,
    base_url: str,
    model: str,
    message: str = "",
) -> BillingBlock:
    """Build the structured billing descriptor for a billing-classified failure.

    ``message`` is the human-facing guidance already assembled by the agent
    loop (:func:`agent.conversation_loop._billing_or_entitlement_message`); it
    is carried through unchanged so every surface shows identical copy.
    """
    provider_slug = (provider or "").strip().lower()

    if is_nous_inference_route(provider_slug, base_url):
        return BillingBlock(
            provider=provider_slug or "nous",
            provider_label="Nous Portal",
            model=(model or "").strip(),
            billing_url=_nous_billing_url(),
            is_nous=True,
            message=message or "",
        )

    label, url = _resolve_provider_link(provider_slug, base_url)
    return BillingBlock(
        provider=provider_slug,
        provider_label=label,
        model=(model or "").strip(),
        billing_url=url,
        is_nous=False,
        message=message or "",
    )
