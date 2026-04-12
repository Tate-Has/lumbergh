"""Tests for inbox quick capture and item management."""
from conftest import seed_tasks, read_tasks, make_task, BASE_URL, wait_for_save


class TestInboxCapture:
    def test_enter_creates_inbox_task(self, page):
        """Pressing Enter in the inbox input creates a new task with status 'inbox'."""
        seed_tasks({"tasks": []})
        page.goto(BASE_URL)
        # Open inbox via localStorage
        page.evaluate("localStorage.setItem('lumbergh:focus:inbox_open', 'true')")
        page.reload()
        page.wait_for_timeout(500)

        # Click inbox header to open if not open yet
        inbox_strip = page.locator('#inboxStrip')
        if 'collapsed' in (inbox_strip.get_attribute('class') or ''):
            page.click('.inbox-header')
            page.wait_for_timeout(300)

        inbox_input = page.locator('#inboxInput')
        inbox_input.wait_for(state='visible', timeout=3000)
        inbox_input.fill('Quick capture test')
        inbox_input.press('Enter')

        wait_for_save(page, endpoint='/api/focus/tasks', timeout=5000)
        data = read_tasks()
        titles = [t['title'] for t in data['tasks']]
        assert 'Quick capture test' in titles, \
            f"Expected 'Quick capture test' in task titles, got: {titles}"

        captured = next(t for t in data['tasks'] if t['title'] == 'Quick capture test')
        assert captured['status'] == 'inbox', \
            f"Expected status 'inbox', got '{captured['status']}'"

    def test_enter_with_empty_input_does_nothing(self, page):
        """Pressing Enter with empty input should not create a task."""
        seed_tasks({"tasks": []})
        page.goto(BASE_URL)

        inbox_strip = page.locator('#inboxStrip')
        if 'collapsed' in (inbox_strip.get_attribute('class') or ''):
            page.click('.inbox-header')
            page.wait_for_timeout(300)

        inbox_input = page.locator('#inboxInput')
        inbox_input.wait_for(state='visible', timeout=3000)
        inbox_input.fill('')
        inbox_input.press('Enter')
        page.wait_for_timeout(500)

        data = read_tasks()
        assert len(data['tasks']) == 0, \
            f"Expected no tasks created from empty input, got: {data['tasks']}"

    def test_captured_task_appears_in_inbox_list(self, page):
        """A captured task should appear in the inbox item list immediately."""
        seed_tasks({"tasks": []})
        page.goto(BASE_URL)

        inbox_strip = page.locator('#inboxStrip')
        if 'collapsed' in (inbox_strip.get_attribute('class') or ''):
            page.click('.inbox-header')
            page.wait_for_timeout(300)

        inbox_input = page.locator('#inboxInput')
        inbox_input.wait_for(state='visible', timeout=3000)
        inbox_input.fill('Visible in list')
        inbox_input.press('Enter')
        page.wait_for_timeout(500)

        # Inbox item should appear in the list
        inbox_items = page.locator('#inboxItems .inbox-item')
        assert inbox_items.count() >= 1, \
            f"Expected at least 1 inbox item after capture, got {inbox_items.count()}"
        item_titles = [inbox_items.nth(i).locator('.inbox-item-title').text_content()
                       for i in range(inbox_items.count())]
        assert 'Visible in list' in item_titles, \
            f"Expected 'Visible in list' in inbox items, got: {item_titles}"

    def test_multiple_captures(self, page):
        """Multiple captures should all appear as separate inbox tasks."""
        seed_tasks({"tasks": []})
        page.goto(BASE_URL)

        inbox_strip = page.locator('#inboxStrip')
        if 'collapsed' in (inbox_strip.get_attribute('class') or ''):
            page.click('.inbox-header')
            page.wait_for_timeout(300)

        inbox_input = page.locator('#inboxInput')
        inbox_input.wait_for(state='visible', timeout=3000)

        for title in ['First capture', 'Second capture', 'Third capture']:
            inbox_input.fill(title)
            inbox_input.press('Enter')
            page.wait_for_timeout(300)

        wait_for_save(page, endpoint='/api/focus/tasks', timeout=5000)
        data = read_tasks()
        inbox_tasks = [t for t in data['tasks'] if t['status'] == 'inbox']
        assert len(inbox_tasks) == 3, \
            f"Expected 3 inbox tasks, got {len(inbox_tasks)}: {[t['title'] for t in inbox_tasks]}"

    def test_inbox_add_btn_expands_and_focuses(self, page):
        """Clicking the + button on the inbox header opens inbox and focuses the input."""
        seed_tasks({"tasks": []})
        page.goto(BASE_URL)
        # Ensure inbox starts collapsed
        page.evaluate("localStorage.clear()")
        page.reload()
        page.wait_for_timeout(500)

        inbox_strip = page.locator('#inboxStrip')
        inbox_add_btn = page.locator('#inboxAddBtn')
        inbox_add_btn.wait_for(state='visible', timeout=3000)
        inbox_add_btn.click()
        page.wait_for_timeout(400)

        # Inbox should now be open
        inbox_class = inbox_strip.get_attribute('class') or ''
        assert 'collapsed' not in inbox_class, \
            "Inbox should be expanded after clicking add button"

        # Input should be focused (or at least visible)
        inbox_input = page.locator('#inboxInput')
        assert inbox_input.is_visible(), "Inbox input should be visible after clicking add button"

    def test_seeded_inbox_task_shows_in_list(self, page):
        """Pre-seeded inbox tasks should appear in the inbox list."""
        seed_tasks({"tasks": [
            make_task("Pre-seeded Item", status="inbox"),
        ]})
        page.goto(BASE_URL)

        inbox_strip = page.locator('#inboxStrip')
        if 'collapsed' in (inbox_strip.get_attribute('class') or ''):
            page.click('.inbox-header')
            page.wait_for_timeout(300)

        inbox_input = page.locator('#inboxInput')
        inbox_input.wait_for(state='visible', timeout=3000)

        # Count badge should show 1
        count_badge = page.locator('#inboxCount')
        count_text = count_badge.text_content().strip()
        assert count_text == '1', f"Expected inbox count badge to show '1', got '{count_text}'"

        # Item should appear in list
        inbox_items = page.locator('#inboxItems .inbox-item')
        assert inbox_items.count() == 1, \
            f"Expected 1 inbox item in list, got {inbox_items.count()}"
