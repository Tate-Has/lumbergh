"""Tests for priority and project filter dropdowns on the task board."""
from conftest import seed_tasks, make_task, BASE_URL


class TestPriorityFilter:
    def test_filter_deselect_med_hides_med_cards(self, page):
        """Deselecting Med priority hides med-priority cards, leaves high visible."""
        seed_tasks({"tasks": [
            make_task("High Task", priority="high", status="backlog"),
            make_task("Med Task", priority="med", status="backlog"),
        ]})
        page.goto(BASE_URL)
        page.evaluate("localStorage.setItem('backlogCollapsed', 'false')")
        page.reload()
        page.wait_for_timeout(500)

        # Both cards should be visible initially (default: high=true, med=true)
        high_card = page.locator('.kanban-card[data-task-id="test-high-task"]')
        med_card = page.locator('.kanban-card[data-task-id="test-med-task"]')
        high_card.wait_for(state='visible', timeout=5000)
        med_card.wait_for(state='visible', timeout=5000)

        # Open priority filter dropdown
        page.click('#priorityFilterBtn')
        page.wait_for_timeout(200)

        # Deselect "Med" (it's currently selected; clicking toggles it off)
        page.locator('#priorityFilterMenu .filter-menu-item').filter(has_text='Med').click()
        page.wait_for_timeout(300)

        # Close filter by pressing Escape
        page.keyboard.press('Escape')
        page.wait_for_timeout(200)

        # High card should still be visible; Med card should be hidden
        assert high_card.is_visible(), "High-priority card should remain visible"
        assert not med_card.is_visible(), "Med-priority card should be hidden after deselecting Med filter"

    def test_filter_deselect_high_hides_high_cards(self, page):
        """Deselecting High priority hides high-priority cards, leaves med visible."""
        seed_tasks({"tasks": [
            make_task("High Task B", priority="high", status="in-progress"),
            make_task("Med Task B", priority="med", status="in-progress"),
        ]})
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        high_card = page.locator('.kanban-card[data-task-id="test-high-task-b"]')
        med_card = page.locator('.kanban-card[data-task-id="test-med-task-b"]')
        high_card.wait_for(state='visible', timeout=5000)
        med_card.wait_for(state='visible', timeout=5000)

        # Open priority filter and deselect High
        page.click('#priorityFilterBtn')
        page.wait_for_timeout(200)
        page.locator('#priorityFilterMenu .filter-menu-item').filter(has_text='High').click()
        page.wait_for_timeout(300)

        page.keyboard.press('Escape')
        page.wait_for_timeout(200)

        assert med_card.is_visible(), "Med-priority card should remain visible"
        assert not high_card.is_visible(), "High-priority card should be hidden after deselecting High filter"

    def test_priority_filter_button_shows_active_count(self, page):
        """Priority filter button shows active count when a filter is applied."""
        seed_tasks({"tasks": [
            make_task("Task X", priority="high", status="in-progress"),
        ]})
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        # Open and deselect Med to apply a filter (2 of 3 now selected)
        page.click('#priorityFilterBtn')
        page.wait_for_timeout(200)
        page.locator('#priorityFilterMenu .filter-menu-item').filter(has_text='Med').click()
        page.wait_for_timeout(200)
        page.keyboard.press('Escape')
        page.wait_for_timeout(200)

        btn_text = page.locator('#priorityFilterBtn').text_content()
        assert '(' in btn_text, f"Filter button should show count when filter is active, got: '{btn_text}'"


class TestProjectFilter:
    def test_filter_by_project_hides_other_projects(self, page):
        """Selecting a project filter shows only matching cards."""
        seed_tasks({"tasks": [
            make_task("Alpha Work", project="Alpha", priority="high", status="in-progress"),
            make_task("Beta Work", project="Beta", priority="high", status="in-progress"),
        ]})
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        alpha_card = page.locator('.kanban-card[data-task-id="test-alpha-work"]')
        beta_card = page.locator('.kanban-card[data-task-id="test-beta-work"]')
        alpha_card.wait_for(state='visible', timeout=5000)
        beta_card.wait_for(state='visible', timeout=5000)

        # Open project filter dropdown
        page.click('#projectFilterBtn')
        page.wait_for_timeout(200)

        # Click "Alpha" project item to select it
        page.locator('#projectFilterMenu .filter-menu-item').filter(has_text='Alpha').click()
        page.wait_for_timeout(300)

        page.keyboard.press('Escape')
        page.wait_for_timeout(200)

        assert alpha_card.is_visible(), "Alpha card should be visible when Alpha filter is active"
        assert not beta_card.is_visible(), "Beta card should be hidden when only Alpha filter is active"

    def test_clear_project_filter_shows_all(self, page):
        """'Show all' clears project filter and restores all cards."""
        seed_tasks({"tasks": [
            make_task("Clear Alpha", project="Alpha", priority="high", status="in-progress"),
            make_task("Clear Beta", project="Beta", priority="high", status="in-progress"),
        ]})
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        alpha_card = page.locator('.kanban-card[data-task-id="test-clear-alpha"]')
        beta_card = page.locator('.kanban-card[data-task-id="test-clear-beta"]')
        alpha_card.wait_for(state='visible', timeout=5000)

        # Apply Alpha filter
        page.click('#projectFilterBtn')
        page.wait_for_timeout(200)
        page.locator('#projectFilterMenu .filter-menu-item').filter(has_text='Alpha').click()
        page.wait_for_timeout(300)
        assert not beta_card.is_visible(), "Beta should be hidden after selecting Alpha filter"

        # Close the menu (it stays open after selecting a project item)
        page.keyboard.press('Escape')
        page.wait_for_timeout(200)

        # Re-open and click 'Show all' to clear
        page.click('#projectFilterBtn')
        page.wait_for_timeout(200)
        page.locator('#projectFilterMenu .filter-menu-item').filter(has_text='Show all').click()
        page.wait_for_timeout(300)

        page.keyboard.press('Escape')
        page.wait_for_timeout(200)

        assert alpha_card.is_visible(), "Alpha card should be visible after clearing filter"
        assert beta_card.is_visible(), "Beta card should be visible after clearing filter"

    def test_project_filters_are_mutually_exclusive_dropdowns(self, page):
        """Opening the project filter closes the priority filter."""
        seed_tasks({"tasks": [make_task("Filter Test", priority="high", status="in-progress")]})
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        # Open priority filter
        page.click('#priorityFilterBtn')
        page.wait_for_timeout(200)
        assert page.locator('#priorityFilterMenu').is_visible(), "Priority menu should be open"

        # Open project filter — should close priority filter
        page.click('#projectFilterBtn')
        page.wait_for_timeout(200)
        assert page.locator('#projectFilterMenu').is_visible(), "Project menu should be open"
        assert not page.locator('#priorityFilterMenu').is_visible(), \
            "Priority menu should be closed when project menu opens"
