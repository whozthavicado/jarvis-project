from jarvis.routing.heuristics import classify


def test_escalation_phrase_routes_t3():
    assert classify("this is important, think hard about it") == "t3_complex"


def test_code_signal_routes_t2():
    assert classify("can you debug this stack trace for me") == "t2_medium"


def test_long_transcript_routes_t2():
    text = " ".join(["word"] * 81)
    assert classify(text) == "t2_medium"


def test_planning_verb_routes_t2():
    assert classify("please design a plan for the migration") == "t2_medium"


def test_tool_work_signal_routes_t1_standard():
    assert classify("can you draft an email to the team") == "t1_standard"


def test_short_chit_chat_routes_t1_simple():
    assert classify("what's the capital of France") == "t1_simple"


def test_mid_length_no_signals_is_ambiguous():
    text = " ".join(["word"] * 40)
    assert classify(text) is None
