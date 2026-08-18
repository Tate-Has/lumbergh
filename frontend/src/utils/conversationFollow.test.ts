import { describe, expect, it } from 'vitest'
import { decideFollow } from './conversationFollow'
import type { FollowDecision, ScrollSample } from './conversationFollow'

/** A tall-ish desktop feed pane. Half of this is the backstop's threshold: 398px. */
const CLIENT_HEIGHT = 796

/** A sample with the fields a given test doesn't care about defaulted. */
function sample(over: Partial<ScrollSample>): ScrollSample {
  return {
    scrollTop: 0,
    scrollHeight: 0,
    clientHeight: CLIENT_HEIGHT,
    lastScrollTop: 0,
    lastScrollHeight: 0,
    userDriven: false,
    following: true,
    ...over,
  }
}

const detach: FollowDecision = { type: 'detach' }
const attach: FollowDecision = { type: 'attach' }
const restick: FollowDecision = { type: 'restick' }
const none: FollowDecision = { type: 'none' }

describe('decideFollow', () => {
  describe('initial measurement settle', () => {
    it('does not detach when the feed grows out from under a barely-moved viewport', () => {
      // Captured from a real fresh load of a long transcript: one settle frame
      // moved scrollTop 7657 -> 7465 (up 192px) while scrollHeight went
      // 8454 -> 9105 (up 651px), leaving 843px of "distance from bottom"
      // against a 398px threshold. Reading that as the user scrolling away
      // stranded the feed 27,000px short of the end with the jump-to-latest
      // pill already showing. The height moved, so the distance means nothing.
      expect(
        decideFollow(
          sample({
            scrollTop: 7465,
            scrollHeight: 9105,
            lastScrollTop: 7657,
            lastScrollHeight: 8454,
          })
        )
      ).not.toEqual(detach)
    })

    it('leaves a growing feed to the re-pin effect rather than fighting it', () => {
      // Same frame: it also moved up, so it must not restick either - the
      // total-size effect is what puts it back on the bottom.
      expect(
        decideFollow(
          sample({
            scrollTop: 7465,
            scrollHeight: 9105,
            lastScrollTop: 7657,
            lastScrollHeight: 8454,
          })
        )
      ).toEqual(none)
    })

    it('re-sticks a small settle correction near the bottom', () => {
      // 60px short of the bottom, stable height, no gesture: pure layout.
      expect(
        decideFollow(
          sample({
            scrollTop: 30_000,
            scrollHeight: 30_856,
            lastScrollTop: 29_990,
            lastScrollHeight: 30_856,
          })
        )
      ).toEqual(restick)
    })

    it('does not detach on a small settle correction near the bottom', () => {
      expect(
        decideFollow(
          sample({
            scrollTop: 30_000,
            scrollHeight: 30_856,
            lastScrollTop: 30_010,
            lastScrollHeight: 30_856,
          })
        )
      ).not.toEqual(detach)
    })

    it('does not detach on the very first scroll event, with no previous sample', () => {
      // lastScrollHeight starts at 0, so the first event always reads as growth.
      expect(
        decideFollow(sample({ scrollTop: 1255, scrollHeight: 33_462, lastScrollTop: 0 }))
      ).not.toEqual(detach)
    })
  })

  describe('the backstop: scrolls we cannot attribute to a gesture', () => {
    it('detaches on a PageUp-sized jump with a stable height', () => {
      // Keyboard aimed at the document fires no wheel, touch or key event on the
      // scroller, so direction detection never sees it. ~0.9 of a viewport up
      // from the bottom (29204 is the bottom for this feed).
      expect(
        decideFollow(
          sample({
            scrollTop: 28_488,
            scrollHeight: 30_000,
            lastScrollTop: 29_204,
            lastScrollHeight: 30_000,
          })
        )
      ).toEqual(detach)
    })

    it('detaches exactly at half a viewport but not just short of it', () => {
      const atThreshold = sample({
        scrollTop: 30_000 - CLIENT_HEIGHT - CLIENT_HEIGHT / 2,
        scrollHeight: 30_000,
        lastScrollTop: 30_000,
        lastScrollHeight: 30_000,
      })
      expect(decideFollow(atThreshold)).toEqual(detach)
      expect(decideFollow({ ...atThreshold, scrollTop: atThreshold.scrollTop + 1 })).not.toEqual(
        detach
      )
    })

    it('holds a 150px floor for viewports too short for half of one to mean much', () => {
      const short = { clientHeight: 120, scrollHeight: 30_000, lastScrollHeight: 30_000 }
      expect(
        decideFollow(sample({ ...short, scrollTop: 30_000 - 120 - 150, lastScrollTop: 30_000 }))
      ).toEqual(detach)
      expect(
        decideFollow(sample({ ...short, scrollTop: 30_000 - 120 - 149, lastScrollTop: 30_000 }))
      ).not.toEqual(detach)
    })

    it('does not fire once follow has already been given up', () => {
      expect(
        decideFollow(
          sample({
            following: false,
            scrollTop: 10_000,
            scrollHeight: 30_000,
            lastScrollTop: 30_000,
            lastScrollHeight: 30_000,
          })
        )
      ).toEqual(none)
    })

    it('still detaches when the feed shrinks under a real jump', () => {
      // A shrink moves the bottom toward the viewport, so it can never
      // manufacture the backstop's condition - and must not blind it either.
      // The trailing `thinking` item dropping out is the everyday shrink.
      expect(
        decideFollow(
          sample({
            scrollTop: 28_488,
            scrollHeight: 29_940,
            lastScrollTop: 29_204,
            lastScrollHeight: 30_000,
          })
        )
      ).toEqual(detach)
    })
  })

  describe('gestures', () => {
    it('detaches on an upward gesture', () => {
      expect(
        decideFollow(
          sample({
            userDriven: true,
            scrollTop: 28_000,
            scrollHeight: 30_000,
            lastScrollTop: 29_204,
            lastScrollHeight: 30_000,
          })
        )
      ).toEqual(detach)
    })

    it('does not detach on a downward scroll inside the gesture window', () => {
      // Expanding a tool card adds height above the viewport and scroll
      // anchoring pushes scrollTop *down* to compensate. The click sits inside
      // the gesture window, so the gesture alone cannot decide - direction must.
      expect(
        decideFollow(
          sample({
            userDriven: true,
            scrollTop: 24_000,
            scrollHeight: 30_000,
            lastScrollTop: 23_400,
            lastScrollHeight: 29_400,
          })
        )
      ).toEqual(none)
    })

    it('does not detach on a zero-delta scroll inside the gesture window', () => {
      expect(
        decideFollow(
          sample({
            userDriven: true,
            scrollTop: 24_000,
            scrollHeight: 30_000,
            lastScrollTop: 24_000,
            lastScrollHeight: 30_000,
          })
        )
      ).toEqual(none)
    })

    it('re-attaches when a gesture lands back on the bottom', () => {
      expect(
        decideFollow(
          sample({
            userDriven: true,
            following: false,
            scrollTop: 29_190,
            scrollHeight: 30_000,
            lastScrollTop: 20_000,
            lastScrollHeight: 30_000,
          })
        )
      ).toEqual(attach)
    })

    it('re-attaches even when the last motion of the gesture was upward', () => {
      // Overshooting the bottom and easing back up still ends at the bottom.
      expect(
        decideFollow(
          sample({
            userDriven: true,
            following: false,
            scrollTop: 29_190,
            scrollHeight: 30_000,
            lastScrollTop: 29_204,
            lastScrollHeight: 30_000,
          })
        )
      ).toEqual(attach)
    })

    it('never re-sticks under a gesture, however far from the bottom', () => {
      expect(
        decideFollow(
          sample({
            userDriven: true,
            scrollTop: 5_000,
            scrollHeight: 30_000,
            lastScrollTop: 5_000,
            lastScrollHeight: 30_000,
          })
        )
      ).toEqual(none)
    })
  })

  describe('momentum', () => {
    it('does not fight a feed drifting upward on its own', () => {
      // Touch momentum after a flick: past the gesture window, short of the
      // bottom, still moving up. Re-sticking here would yank it back.
      expect(
        decideFollow(
          sample({
            scrollTop: 29_004,
            scrollHeight: 30_000,
            lastScrollTop: 29_104,
            lastScrollHeight: 30_000,
          })
        )
      ).toEqual(none)
    })
  })
})
