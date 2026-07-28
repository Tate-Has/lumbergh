import type { ActivityItem } from '../../hooks/useCombinedActivitySocket'

/**
 * A `tool_call` item merged with the `status` (and output `text`) of its
 * matching `tool_result`, once that result has arrived.
 *
 * This extends the hook's flat `ActivityItem` shape rather than mirroring
 * upstream's nested `{ result: {...} }` field on `ToolItem` — that keeps every
 * existing `ActivityCards` field access (`item.status`, `item.tool_detail`)
 * working unchanged for a merged item. `resultText` is the one genuinely new
 * field: it carries the `tool_result` event's `text` (the tool's output),
 * since the hook's `tool_detail` field is reserved for the call's *input*
 * JSON (see `ConversationEvent` in `backend/lumbergh/activity/events.py`) and
 * must not be overwritten or `EditCard`'s diff rendering breaks.
 */
export interface PairedActivityItem extends ActivityItem {
  resultText?: string | null
}

/**
 * Merges each `tool_result` into its originating `tool_call`, matched by
 * `session` + `tool_use_id` — matching must be scoped per-session because
 * `tool_use_id` is only unique within one session's transcript (same
 * reasoning as the hook's own `key` field).
 *
 * Input and output are both oldest-first (the hook's native order — callers
 * that want newest-first should reverse the result, same as they'd reverse
 * the hook's raw `items`). A merged item keeps the position of its
 * `tool_call` rather than moving to where its `tool_result` landed, so the
 * feed doesn't visually jump once a result arrives after other events.
 *
 * A `tool_call` with no result yet is left with `status`/`resultText`
 * unset — `ActivityCards`'s existing `hasResult = item.status != null` check
 * already renders that as pending ("…"), no new convention needed. A
 * `tool_result` that never finds a matching `tool_call` in the current buffer
 * (e.g. the call happened before the socket connected — this feed has no
 * history) is left in the output as a standalone item, which
 * `ActivityCards`'s `ToolResultChip` renders as a small chip.
 */
export function pairToolEvents(items: ActivityItem[]): PairedActivityItem[] {
  // session -> tool_use_id -> index of that call's slot in `merged`
  const callSlotBySession = new Map<string, Map<string, number>>()
  const merged: PairedActivityItem[] = []

  for (const item of items) {
    if (item.type === 'tool_call' && item.tool_use_id) {
      let slots = callSlotBySession.get(item.session)
      if (!slots) {
        slots = new Map()
        callSlotBySession.set(item.session, slots)
      }
      slots.set(item.tool_use_id, merged.length)
      merged.push(item)
      continue
    }

    if (item.type === 'tool_result' && item.tool_use_id) {
      const slot = callSlotBySession.get(item.session)?.get(item.tool_use_id)
      if (slot !== undefined) {
        merged[slot] = {
          ...merged[slot],
          status: item.status,
          resultText: item.text,
        }
        continue // merged into its tool_call — don't also render standalone
      }
      // No matching call in the current buffer — graceful degradation.
      merged.push(item)
      continue
    }

    merged.push(item)
  }

  return merged
}
