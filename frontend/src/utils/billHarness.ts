/** What the summon endpoint attaches to a `stage: "harness"` failure so the UI can
 * offer a way out instead of just reporting a missing binary. */
export interface HarnessMissingDetail {
  stage: string
  error: string
  help?: string
  harness?: string
  binary?: string
  install_url?: string
  why?: string
  fallback_agent?: string | null
}

export function isHarnessMissing(detail: unknown): detail is HarnessMissingDetail {
  return (
    typeof detail === 'object' &&
    detail !== null &&
    (detail as HarnessMissingDetail).stage === 'harness' &&
    typeof (detail as HarnessMissingDetail).harness === 'string'
  )
}
