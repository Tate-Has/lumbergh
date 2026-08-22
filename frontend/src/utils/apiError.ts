/** What went wrong, in the API's own words when it has any.
 *
 * FastAPI puts the useful sentence in `detail`; a bare "HTTP 404" tells a
 * person nothing they can act on, while "This session's directory no longer
 * exists: /path" tells them exactly what happened.
 */
export async function errorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json()
    const detail = (body as { detail?: unknown })?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
  } catch {
    // Not JSON, or already consumed — the status is all we have.
  }
  return `HTTP ${res.status}`
}
