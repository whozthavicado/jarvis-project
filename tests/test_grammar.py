"""T0 grammar matcher tests (ARCHITECTURE.md §2, RULE 0)."""
from jarvis.routing.grammar import load_grammar, match
from jarvis.tools.types import ToolCall

_COMMANDS = load_grammar()


def test_open_app_captures_app_name():
    assert match("open Safari", _COMMANDS) == ToolCall(name="open_app", args={"app": "safari"})


def test_close_app_matches_close_and_quit():
    assert match("quit Spotify", _COMMANDS) == ToolCall(name="close_app", args={"app": "spotify"})
    assert match("close Spotify", _COMMANDS) == ToolCall(name="close_app", args={"app": "spotify"})


def test_volume_up_variants():
    for phrase in ["volume up", "turn the volume up", "increase the volume"]:
        assert match(phrase, _COMMANDS) == ToolCall(name="volume", args={"direction": "up"})


def test_volume_mute():
    assert match("mute", _COMMANDS) == ToolCall(name="volume", args={"direction": "mute"})
    assert match("mute the volume", _COMMANDS) == ToolCall(name="volume", args={"direction": "mute"})


def test_lock_screen():
    assert match("lock screen", _COMMANDS) == ToolCall(name="lock_screen", args={})
    assert match("lock the screen", _COMMANDS) == ToolCall(name="lock_screen", args={})


def test_set_timer_coerces_minutes_to_int():
    result = match("set a timer for 10 minutes", _COMMANDS)
    assert result == ToolCall(name="set_timer", args={"minutes": 10})
    assert isinstance(result.args["minutes"], int)


def test_what_time_variants():
    assert match("what time is it", _COMMANDS) == ToolCall(name="what_time", args={})
    assert match("what's the time?", _COMMANDS) == ToolCall(name="what_time", args={})


def test_trailing_punctuation_and_case_are_normalized():
    assert match("Open Safari.", _COMMANDS) == ToolCall(name="open_app", args={"app": "safari"})
    assert match("  VOLUME UP  ", _COMMANDS) == ToolCall(name="volume", args={"direction": "up"})


def test_no_match_falls_through():
    assert match("what's the weather like today", _COMMANDS) is None
    assert match("", _COMMANDS) is None
