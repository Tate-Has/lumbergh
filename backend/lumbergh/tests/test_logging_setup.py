"""Application logs have to actually go somewhere.

Nothing configured logging, so every `logger.info` in the app vanished: the root
logger has no handler and the fallback only prints WARNING and above. Debugging
the idle monitor meant editing the source to write to a file by hand.
"""

import logging

from lumbergh.logging_setup import configure_logging, resolve_level


class TestResolveLevel:
    def test_defaults_to_info(self):
        assert resolve_level(None) == logging.INFO
        assert resolve_level("") == logging.INFO

    def test_reads_a_name_in_any_case(self):
        assert resolve_level("debug") == logging.DEBUG
        assert resolve_level("DEBUG") == logging.DEBUG
        assert resolve_level(" Warning ") == logging.WARNING

    def test_a_nonsense_level_falls_back_rather_than_crashing_startup(self):
        assert resolve_level("chatty") == logging.INFO


class TestConfigureLogging:
    def test_the_app_logger_gets_a_handler_and_the_asked_for_level(self):
        logger = logging.getLogger("lumbergh")
        for handler in list(logger.handlers):
            logger.removeHandler(handler)

        configure_logging("debug")

        assert logger.level == logging.DEBUG
        assert logger.handlers, "without a handler the records go nowhere"

    def test_calling_it_twice_does_not_double_every_line(self):
        configure_logging("info")
        configure_logging("info")

        assert len(logging.getLogger("lumbergh").handlers) == 1

    def test_it_leaves_uvicorns_own_logging_alone(self):
        before = list(logging.getLogger("uvicorn.access").handlers)

        configure_logging("debug")

        assert list(logging.getLogger("uvicorn.access").handlers) == before


def test_records_still_reach_listeners_further_up():
    """Silencing propagation would blind pytest's caplog and any other handler."""
    configure_logging("info")

    assert logging.getLogger("lumbergh").propagate is True
