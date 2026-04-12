"""Tests for Phase 08: Mobile / Responsive Polish."""
import pytest
from conftest import BASE_URL, seed_tasks, clear_tasks, clear_localstorage, read_tasks


SAMPLE_TASKS = {"tasks": [
    {"id": "t1", "title": "Quick thought", "project": "", "priority": "med", "status": "inbox", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t2", "title": "Write report", "project": "", "priority": "high", "status": "today", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t3", "title": "Review PR", "project": "", "priority": "med", "status": "today", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t4", "title": "Background sync", "project": "Alpha", "priority": "med", "status": "running", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t5", "title": "Backlog task 1", "project": "Beta", "priority": "low", "status": "backlog", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t6", "title": "Backlog task 2", "project": "Beta", "priority": "med", "status": "backlog", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t7", "title": "Feature work", "project": "Alpha", "priority": "high", "status": "in-progress", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t8", "title": "Code review", "project": "Alpha", "priority": "med", "status": "review", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t9", "title": "Done thing", "project": "Beta", "priority": "low", "status": "done", "completed": True, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
]}


class TestMobileLayout:
    """Test responsive layout at mobile viewport (375x667)."""

    def test_today_and_inflight_stack_vertically(self, page):
        """At mobile width, Today and In Flight panels should stack (single column)."""
        seed_tasks(SAMPLE_TASKS)
        clear_localstorage(page)
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        # Check grid-template-columns is a single column
        cols = page.locator(".top-split").evaluate(
            "el => getComputedStyle(el).gridTemplateColumns"
        )
        # Single column: should be one value (e.g., "345px" or "355px"), not two
        col_values = cols.strip().split()
        assert len(col_values) == 1, f"Expected single column, got: {cols}"
        clear_tasks()

    def test_board_columns_horizontally_scrollable(self, page):
        """Board columns should be scrollable horizontally on mobile."""
        seed_tasks(SAMPLE_TASKS)
        clear_localstorage(page)
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(BASE_URL)
        page.wait_for_selector(".kanban-card")

        # The board-columns container should have overflow and its
        # scrollWidth should exceed its clientWidth
        is_scrollable = page.locator(".board-columns").evaluate(
            "el => el.scrollWidth > el.clientWidth"
        )
        assert is_scrollable, "Board columns should be horizontally scrollable on mobile"
        clear_tasks()

    def test_date_hidden_on_mobile(self, page):
        """The date text in the topbar should be hidden on mobile."""
        seed_tasks(SAMPLE_TASKS)
        clear_localstorage(page)
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(BASE_URL)
        page.wait_for_selector(".topbar")

        date_el = page.locator(".topbar .date")
        assert not date_el.is_visible(), "Date should be hidden on mobile"
        clear_tasks()

    def test_swimlane_toggle_hidden_on_mobile(self, page):
        """The swimlane toggle button should be hidden on mobile."""
        seed_tasks(SAMPLE_TASKS)
        clear_localstorage(page)
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(BASE_URL)
        page.wait_for_selector(".board-section")

        # Expand the board section first if collapsed
        board = page.locator("#boardSection")
        if board.evaluate("el => el.classList.contains('collapsed')"):
            page.locator("#boardHeaderRow").click()
            page.wait_for_timeout(300)

        toggle = page.locator("#swimlaneToggle")
        assert not toggle.is_visible(), "Swimlane toggle should be hidden on mobile"
        clear_tasks()

    def test_modal_fullscreen_on_mobile(self, page):
        """Modals should be full-screen (nearly full width) on mobile."""
        seed_tasks(SAMPLE_TASKS)
        clear_localstorage(page)
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        # Open the add-today modal
        page.locator("#addTodayBtn").click()
        page.wait_for_selector(".modal-overlay.active")

        modal = page.locator("#taskModal .modal")
        box = modal.bounding_box()
        assert box is not None, "Modal should be visible"
        # Modal should be at least 90% of viewport width
        assert box["width"] >= 375 * 0.9, (
            f"Modal width {box['width']} should be >= {375 * 0.9} on mobile"
        )
        page.locator("#modalCancel").click()
        clear_tasks()


class TestTabletLayout:
    """Test responsive layout at tablet viewport (768x1024)."""

    def test_tablet_stacks_panels(self, page):
        """At tablet width (768px), Today and In Flight should stack vertically."""
        seed_tasks(SAMPLE_TASKS)
        clear_localstorage(page)
        page.set_viewport_size({"width": 768, "height": 1024})
        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        cols = page.locator(".top-split").evaluate(
            "el => getComputedStyle(el).gridTemplateColumns"
        )
        col_values = cols.strip().split()
        assert len(col_values) == 1, f"Expected single column at 768px, got: {cols}"
        clear_tasks()

    def test_desktop_side_by_side(self, page):
        """At desktop width (1200px), Today and In Flight should be side by side."""
        seed_tasks(SAMPLE_TASKS)
        clear_localstorage(page)
        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        cols = page.locator(".top-split").evaluate(
            "el => getComputedStyle(el).gridTemplateColumns"
        )
        col_values = cols.strip().split()
        assert len(col_values) == 2, f"Expected two columns at 1200px, got: {cols}"
        clear_tasks()


class TestMobileTouchTargets:
    """Test that interactive elements have adequate sizing on mobile."""

    def test_promote_buttons_visible_on_mobile(self, page):
        """Kanban promote buttons should be visible (not hover-gated) on mobile."""
        seed_tasks(SAMPLE_TASKS)
        clear_localstorage(page)
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(BASE_URL)
        page.wait_for_selector(".kanban-card")

        # Find the first promote button (should be in a non-done column)
        promote_btn = page.locator(".kanban-promote-btn").first
        # On mobile, opacity should be 1 (always visible) without hovering
        opacity = promote_btn.evaluate("el => getComputedStyle(el).opacity")
        assert opacity == "1", f"Promote button opacity should be 1 on mobile, got: {opacity}"
        clear_tasks()

    def test_check_icon_larger_on_mobile(self, page):
        """Today card check icons should be larger on mobile (28px)."""
        seed_tasks(SAMPLE_TASKS)
        clear_localstorage(page)
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        check_icon = page.locator(".today-card .check-icon").first
        box = check_icon.bounding_box()
        assert box is not None
        assert box["width"] >= 26, f"Check icon should be at least 26px wide, got: {box['width']}"
        clear_tasks()


class TestMobileFilterDropdowns:
    """Test filter dropdowns behave as bottom sheets on mobile."""

    def test_filter_menu_fixed_bottom_on_mobile(self, page):
        """Filter menu should be fixed to the bottom of the screen on mobile."""
        seed_tasks(SAMPLE_TASKS)
        clear_localstorage(page)
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(BASE_URL)
        page.wait_for_selector(".board-section")

        # Expand board if collapsed
        board = page.locator("#boardSection")
        if board.evaluate("el => el.classList.contains('collapsed')"):
            page.locator("#boardHeaderRow").click()
            page.wait_for_timeout(300)

        # Click the project filter button to open the dropdown
        page.locator("#projectFilterBtn").click()
        page.wait_for_selector(".filter-menu.open")

        # Check the filter menu's position is 'fixed'
        position = page.locator("#projectFilterMenu").evaluate(
            "el => getComputedStyle(el).position"
        )
        assert position == "fixed", f"Filter menu should be fixed on mobile, got: {position}"
        clear_tasks()


class TestMobileActionBar:
    """Test the fixed-bottom mobile action bar."""

    def test_action_bar_hidden_on_desktop(self, page):
        """Action bar should not be visible at desktop width."""
        seed_tasks(SAMPLE_TASKS)
        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto(BASE_URL)
        page.wait_for_timeout(300)

        bar = page.locator("#mobileActionBar")
        assert not bar.is_visible(), "Action bar should be hidden on desktop"
        clear_tasks()

    def test_action_bar_visible_on_mobile(self, page):
        """Action bar should be visible at mobile width."""
        seed_tasks(SAMPLE_TASKS)
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(BASE_URL)
        page.wait_for_timeout(300)

        bar = page.locator("#mobileActionBar")
        assert bar.is_visible(), "Action bar should be visible on mobile"

        # All three buttons should be present
        assert page.locator("#mobileAddToday").is_visible()
        assert page.locator("#mobileAddInbox").is_visible()
        assert page.locator("#mobileScrollBoard").is_visible()
        clear_tasks()

    def test_today_button_opens_modal(self, page):
        """+ Today button should open the new-task modal with status=today."""
        seed_tasks(SAMPLE_TASKS)
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(BASE_URL)
        page.wait_for_timeout(300)

        page.locator("#mobileAddToday").click()
        page.wait_for_selector(".modal-overlay.active")

        status = page.locator("#modalTaskStatus").input_value()
        assert status == "today", f"Expected status 'today', got '{status}'"
        page.locator("#modalCancel").click()
        clear_tasks()

    def test_inbox_button_opens_modal(self, page):
        """+ Inbox button should open the new-task modal with status=inbox."""
        seed_tasks(SAMPLE_TASKS)
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(BASE_URL)
        page.wait_for_timeout(300)

        page.locator("#mobileAddInbox").click()
        page.wait_for_selector(".modal-overlay.active")

        status = page.locator("#modalTaskStatus").input_value()
        assert status == "inbox", f"Expected status 'inbox', got '{status}'"
        page.locator("#modalCancel").click()
        clear_tasks()

    def test_board_button_scrolls_to_board(self, page):
        """Board button should scroll the board section into view."""
        seed_tasks(SAMPLE_TASKS)
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(BASE_URL)
        page.wait_for_timeout(300)

        # Board should be below the fold initially
        board_before = page.locator("#boardSection").bounding_box()
        # Click the board button
        page.locator("#mobileScrollBoard").click()
        page.wait_for_timeout(500)

        # After scrolling, the board section should be in the viewport
        board_after = page.locator("#boardSection").bounding_box()
        assert board_after is not None
        # Board top should now be near the top of the viewport
        assert board_after["y"] < 667, "Board should be scrolled into view"
        clear_tasks()


class TestTouchDragManager:
    """Test touch drag-and-drop functionality via CDP touch events."""

    def _dispatch_touch(self, page, event_type, x, y):
        """Dispatch a touch event via JavaScript."""
        page.evaluate(f"""() => {{
            const el = document.elementFromPoint({x}, {y});
            if (!el) return;
            const touch = new Touch({{
                identifier: 1,
                target: el,
                clientX: {x},
                clientY: {y},
                pageX: {x},
                pageY: {y}
            }});
            const evt = new TouchEvent('{event_type}', {{
                touches: {('[]' if event_type == 'touchend' else '[touch]')},
                changedTouches: [touch],
                bubbles: true,
                cancelable: true
            }});
            el.dispatchEvent(evt);
        }}""")

    def test_touch_drag_card_to_today(self, page):
        """Long-press a kanban card and drag it to the Today panel."""
        seed_tasks(SAMPLE_TASKS)
        clear_localstorage(page)
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(BASE_URL)
        page.wait_for_selector(".kanban-card")

        # Scroll to board to find a backlog card
        page.locator("#boardSection").scroll_into_view_if_needed()
        page.wait_for_timeout(300)

        # Get the first kanban card (should be a backlog/in-progress card)
        card = page.locator(".kanban-card").first
        card_box = card.bounding_box()
        assert card_box is not None

        card_id = card.evaluate("el => el.dataset.taskId")
        cx = card_box["x"] + card_box["width"] / 2
        cy = card_box["y"] + card_box["height"] / 2

        # Simulate long-press: touchstart, wait 350ms, then touchmove to Today panel
        self._dispatch_touch(page, "touchstart", cx, cy)
        page.wait_for_timeout(350)

        # Check ghost element appeared
        ghost_count = page.locator(".touch-ghost").count()
        assert ghost_count == 1, f"Expected ghost element after long-press, got {ghost_count}"

        # Get today panel position (scroll to top first)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(100)
        today_panel = page.locator("#todayPanel")
        today_box = today_panel.bounding_box()
        assert today_box is not None
        tx = today_box["x"] + today_box["width"] / 2
        ty = today_box["y"] + today_box["height"] / 2

        # Move to Today panel
        self._dispatch_touch(page, "touchmove", tx, ty)
        page.wait_for_timeout(100)

        # Drop
        self._dispatch_touch(page, "touchend", tx, ty)
        page.wait_for_timeout(500)

        # Ghost should be cleaned up
        assert page.locator(".touch-ghost").count() == 0, "Ghost should be removed after drop"

        # Verify the task moved to today status
        data = read_tasks()
        today_count = len([t for t in data['tasks'] if t['status'] == 'today'])
        assert today_count == 3, f"Expected 3 today tasks after drag, got {today_count}"
        clear_tasks()

    def test_touch_cancel_before_threshold(self, page):
        """Moving finger before 300ms should cancel drag (allow scrolling)."""
        seed_tasks(SAMPLE_TASKS)
        clear_localstorage(page)
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(BASE_URL)
        page.wait_for_selector(".kanban-card")

        page.locator("#boardSection").scroll_into_view_if_needed()
        page.wait_for_timeout(300)

        card = page.locator(".kanban-card").first
        card_box = card.bounding_box()
        cx = card_box["x"] + card_box["width"] / 2
        cy = card_box["y"] + card_box["height"] / 2

        # touchstart then immediately move (scroll gesture)
        self._dispatch_touch(page, "touchstart", cx, cy)
        page.wait_for_timeout(50)
        # Move more than scrollThreshold (10px)
        self._dispatch_touch(page, "touchmove", cx, cy + 30)
        page.wait_for_timeout(300)

        # Ghost should NOT appear
        assert page.locator(".touch-ghost").count() == 0, "Ghost should not appear on scroll"

        self._dispatch_touch(page, "touchend", cx, cy + 30)
        clear_tasks()

    def test_touch_cleanup_on_cancel(self, page):
        """Touch cancel should clean up ghost and drag state."""
        seed_tasks(SAMPLE_TASKS)
        clear_localstorage(page)
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(BASE_URL)
        page.wait_for_selector(".kanban-card")

        page.locator("#boardSection").scroll_into_view_if_needed()
        page.wait_for_timeout(300)

        card = page.locator(".kanban-card").first
        card_box = card.bounding_box()
        cx = card_box["x"] + card_box["width"] / 2
        cy = card_box["y"] + card_box["height"] / 2

        # Start long-press
        self._dispatch_touch(page, "touchstart", cx, cy)
        page.wait_for_timeout(350)

        # Ghost should exist
        assert page.locator(".touch-ghost").count() == 1

        # Cancel
        self._dispatch_touch(page, "touchcancel", cx, cy)
        page.wait_for_timeout(100)

        # Everything should be cleaned up
        assert page.locator(".touch-ghost").count() == 0, "Ghost should be removed on cancel"
        dragging = page.locator(".dragging").count()
        assert dragging == 0, "No elements should have .dragging class"
        clear_tasks()
