"""Tests for NotesBar UI — open, type, save, persist, collapse."""
from conftest import BASE_URL, wait_for_save, read_notes, seed_tasks


class TestNotesBar:
    def test_type_and_save(self, page):
        """Type in notes bar and verify it saves to the API."""
        seed_tasks({"tasks": []})
        # Open notes bar via localStorage so it's expanded on load
        page.goto(BASE_URL)
        page.evaluate("localStorage.setItem('lumbergh:focus:notes_open', 'true')")
        page.reload()
        page.wait_for_timeout(500)

        textarea = page.locator('#notesTextarea')
        textarea.wait_for(state='visible', timeout=3000)
        textarea.fill('Hello from test')

        # Wait for the debounced save (500ms debounce → use response wait)
        wait_for_save(page, endpoint='/api/focus/notes', timeout=5000)
        data = read_notes()
        assert 'Hello from test' in data.get('content', ''), \
            f"Expected 'Hello from test' in notes content, got: {data}"

    def test_notes_persist_after_reload(self, page):
        """Notes written to the server should appear after a page reload."""
        seed_tasks({"tasks": []})
        page.goto(BASE_URL)
        page.evaluate("localStorage.setItem('lumbergh:focus:notes_open', 'true')")
        page.reload()
        page.wait_for_timeout(500)

        textarea = page.locator('#notesTextarea')
        textarea.wait_for(state='visible', timeout=3000)
        textarea.fill('Persistent note')

        wait_for_save(page, endpoint='/api/focus/notes', timeout=5000)

        # Reload the page (keep localStorage so notes bar stays open)
        page.reload()
        page.wait_for_timeout(500)

        textarea = page.locator('#notesTextarea')
        textarea.wait_for(state='visible', timeout=3000)
        assert 'Persistent note' in textarea.input_value(), \
            f"Expected 'Persistent note' in textarea after reload, got: '{textarea.input_value()}'"

    def test_notes_bar_toggle_opens_and_closes(self, page):
        """Clicking the notes header toggles the bar open and closed."""
        seed_tasks({"tasks": []})
        page.goto(BASE_URL)
        # Start with notes closed
        page.evaluate("localStorage.setItem('lumbergh:focus:notes_open', 'false')")
        page.reload()
        page.wait_for_timeout(400)

        # Bar should be collapsed; textarea not visible
        textarea = page.locator('#notesTextarea')
        notes_bar = page.locator('#notesBar')
        assert 'collapsed' in (notes_bar.get_attribute('class') or ''), \
            "Notes bar should start collapsed"

        # Click header to open
        page.click('#notesHeader')
        page.wait_for_timeout(300)
        notes_bar_class = notes_bar.get_attribute('class') or ''
        assert 'collapsed' not in notes_bar_class, \
            "Notes bar should be open after clicking header"
        assert textarea.is_visible(), "Textarea should be visible when notes bar is open"

        # Click header again to close
        page.click('#notesHeader')
        page.wait_for_timeout(300)
        notes_bar_class2 = notes_bar.get_attribute('class') or ''
        assert 'collapsed' in notes_bar_class2, \
            "Notes bar should be collapsed after clicking header again"
