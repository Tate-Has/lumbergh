/**
 * Follow policy for the conversation feed.
 *
 * The feed sticks to the bottom as events stream in, and must let go the moment
 * the user goes looking through scrollback - without ever reading its own
 * layout churn as user intent. A virtualized feed re-measures constantly: rows
 * grow as markdown, fonts and images land, our own stick-to-bottom writes fire
 * scroll events of their own, and the whole transcript can gain thousands of
 * pixels in the first second after mount.
 *
 * Three mechanisms interact, and this function is all of them:
 *
 * - A gesture window (the caller decides what counts) marks scrolls the user
 *   plausibly caused. Inside it, only *direction* detaches: expanding a tool
 *   card adds height above the viewport and scroll anchoring pushes scrollTop
 *   down to compensate, so a downward move inside the window is layout, not
 *   intent.
 * - A position backstop catches every scroll we cannot attribute to a gesture -
 *   keyboard aimed at the document, a Firefox scrollbar drag, find-in-page.
 * - Everything else is layout settling, and gets re-stuck to the bottom.
 *
 * The backstop reads distance from the bottom, which is only meaningful once
 * the feed has stopped growing: during initial settle a single event can add
 * ~650px of height under a barely-moved scrollTop, which puts the viewport
 * hundreds of pixels "away" from a bottom that did not exist a frame ago. That
 * is why growth suppresses the backstop - see `grew` below.
 */

export interface ScrollSample {
  scrollTop: number
  scrollHeight: number
  clientHeight: number
  /** scrollTop as of the previous sample. */
  lastScrollTop: number
  /** scrollHeight as of the previous sample. */
  lastScrollHeight: number
  /** Did a gesture (wheel, touch, key, pointer drag) plausibly cause this scroll? */
  userDriven: boolean
  /** Is the feed currently following the bottom? */
  following: boolean
}

export type FollowDecision =
  /** Stop following; show the jump-to-latest affordance. */
  | { type: 'detach' }
  /** Start (or stay) following without moving the feed. */
  | { type: 'attach' }
  /** Still following, but short of the bottom: scroll back down. */
  | { type: 'restick' }
  /** Leave everything alone. */
  | { type: 'none' }

const DETACH: FollowDecision = { type: 'detach' }
const ATTACH: FollowDecision = { type: 'attach' }
const RESTICK: FollowDecision = { type: 'restick' }
const NONE: FollowDecision = { type: 'none' }

/** Slack for sub-pixel rounding and the last row's bottom padding. */
const AT_BOTTOM_PX = 40

/**
 * Floor on the backstop's threshold, for viewports too short for half of one to
 * mean anything.
 */
const MIN_BACKSTOP_PX = 150

export function decideFollow({
  scrollTop,
  scrollHeight,
  clientHeight,
  lastScrollTop,
  lastScrollHeight,
  userDriven,
  following,
}: ScrollSample): FollowDecision {
  const distanceFromBottom = scrollHeight - scrollTop - clientHeight
  const atBottom = distanceFromBottom < AT_BOTTOM_PX
  const movedUp = scrollTop < lastScrollTop
  // Only growth is disqualifying. A feed that shrinks (the trailing `thinking`
  // item dropping out, items being filtered) moves the bottom *toward* the
  // viewport, so it can only reduce distanceFromBottom - it can never
  // manufacture the backstop's condition, and suppressing the backstop for it
  // would just blind us to a real gesture that happened to land on the same
  // frame.
  const grew = scrollHeight > lastScrollHeight

  if (userDriven) {
    // Never fight an upward scroll - and never mistake anything else for one.
    if (atBottom) return ATTACH
    if (movedUp) return DETACH
    return NONE
  }

  // Half a viewport, not a whole one: PageUp deliberately keeps a strip of
  // overlap for context and moves only ~0.9 of the viewport, so a full-viewport
  // threshold would miss the very case this exists for. Every way of scrolling
  // this catches leaves scrollHeight untouched, so requiring a stable height
  // costs it nothing.
  if (following && !grew && distanceFromBottom >= Math.max(MIN_BACKSTOP_PX, clientHeight / 2)) {
    return DETACH
  }
  // Otherwise this is layout settling under us. Re-stick unless the feed is
  // drifting upward on its own (touch momentum after a flick), which would
  // fight the user.
  if (following && !atBottom && !movedUp) return RESTICK
  return NONE
}
