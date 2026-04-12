"""Phase 14 — Styling alignment tests.

Verifies theme mechanism, token system, and responsive layout after
converting from hand-written CSS to Tailwind utility classes.
"""
from conftest import BASE_URL, seed_tasks, clear_tasks, clear_localstorage, make_task

SAMPLE_TASKS = {"tasks": [
    make_task("Style task A", project="Alpha", status="today"),
    make_task("Style task B", project="Beta", status="backlog"),
]}


class TestThemeMechanism:
    """Theme switching uses .dark class and lumbergh:theme localStorage key."""

    def test_dark_class_toggles(self, page):
        """Pressing 'd' toggles .dark class on <html>."""
        seed_tasks(SAMPLE_TASKS)
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        initial = page.evaluate("document.documentElement.classList.contains('dark')")
        page.keyboard.press("d")
        page.wait_for_timeout(100)
        after = page.evaluate("document.documentElement.classList.contains('dark')")
        assert initial != after
        clear_tasks()

    def test_theme_persists_in_localstorage(self, page):
        """Theme is stored under 'lumbergh:theme' key."""
        seed_tasks(SAMPLE_TASKS)
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        # Set to dark
        page.evaluate("localStorage.setItem('lumbergh:theme', 'dark')")
        page.reload()
        page.wait_for_load_state("networkidle")
        assert page.evaluate("document.documentElement.classList.contains('dark')") is True

        # Set to light
        page.evaluate("localStorage.setItem('lumbergh:theme', 'light')")
        page.reload()
        page.wait_for_load_state("networkidle")
        assert page.evaluate("document.documentElement.classList.contains('dark')") is False
        clear_tasks()

    def test_no_data_theme_attribute(self, page):
        """The old data-theme attribute should not be set."""
        seed_tasks(SAMPLE_TASKS)
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        attr = page.evaluate("document.documentElement.getAttribute('data-theme')")
        assert attr is None
        clear_tasks()


class TestDarkModeColors:
    """Dark mode renders with workstation's warm charcoal palette."""

    def test_dark_body_background(self, page):
        """Body background should be warm charcoal (#2a2d33) in dark mode."""
        seed_tasks(SAMPLE_TASKS)
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        # Ensure dark mode
        page.evaluate("localStorage.setItem('lumbergh:theme', 'dark')")
        page.reload()
        page.wait_for_load_state("networkidle")

        bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
        # #2A2D33 = rgb(42, 45, 51)
        assert "42, 45, 51" in bg, f"Dark bg should be warm charcoal, got {bg}"
        clear_tasks()

    def test_light_body_background(self, page):
        """Body background should be neutral (#f5f5f3) in light mode."""
        seed_tasks(SAMPLE_TASKS)
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        page.evaluate("localStorage.setItem('lumbergh:theme', 'light')")
        page.reload()
        page.wait_for_load_state("networkidle")

        bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
        # #F5F5F3 = rgb(245, 245, 243)
        assert "245, 245, 243" in bg, f"Light bg should be neutral, got {bg}"
        clear_tasks()


class TestResponsiveLayout:
    """Responsive breakpoints still work after Tailwind conversion."""

    def test_desktop_two_column(self, page):
        """At desktop width, top-split should be two columns."""
        seed_tasks(SAMPLE_TASKS)
        clear_localstorage(page)
        page.set_viewport_size({"width": 1200, "height": 800})
        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        cols = page.locator(".top-split").evaluate(
            "el => getComputedStyle(el).gridTemplateColumns"
        )
        col_values = cols.strip().split()
        assert len(col_values) == 2, f"Expected 2 columns at 1200px, got: {cols}"
        clear_tasks()

    def test_tablet_single_column(self, page):
        """At tablet width (768px), top-split should be single column."""
        seed_tasks(SAMPLE_TASKS)
        clear_localstorage(page)
        page.set_viewport_size({"width": 768, "height": 1024})
        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        cols = page.locator(".top-split").evaluate(
            "el => getComputedStyle(el).gridTemplateColumns"
        )
        col_values = cols.strip().split()
        assert len(col_values) == 1, f"Expected 1 column at 768px, got: {cols}"
        clear_tasks()


class TestAccentColor:
    """capSpire orange accent is preserved."""

    def test_accent_on_topbar_hover(self, page):
        """Topbar buttons should use accent color on hover (via CSS variable)."""
        seed_tasks(SAMPLE_TASKS)
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        # Verify the accent CSS variable is set
        accent = page.evaluate(
            "getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()"
        )
        assert accent.startswith("#F1") or accent.startswith("#f1"), \
            f"Accent should be capSpire orange, got {accent}"
        clear_tasks()
