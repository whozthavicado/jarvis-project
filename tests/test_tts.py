"""TTS tests — sentence splitting (pure) and Speaker plumbing with a fake `say`."""
import asyncio
import sys

import pytest

from jarvis.speech import Speaker, split_sentences


def test_split_emits_complete_sentences_only():
    sentences, remainder = split_sentences("Hello there. How are ")
    assert sentences == ["Hello there."]
    assert remainder == "How are "


def test_split_handles_multiple_terminators():
    sentences, remainder = split_sentences("Wait! Really? Yes.\n")
    assert sentences == ["Wait!", "Really?", "Yes."]
    assert remainder == ""


def test_split_holds_back_unterminated_tail():
    sentences, remainder = split_sentences("no terminator yet")
    assert sentences == []
    assert remainder == "no terminator yet"


def test_streaming_reassembly_across_chunks():
    buffer = ""
    spoken = []
    for chunk in ["Hel", "lo wor", "ld. Next", " one here. tail"]:
        buffer += chunk
        sents, buffer = split_sentences(buffer)
        spoken.extend(sents)
    assert spoken == ["Hello world.", "Next one here."]
    assert buffer == "tail"


@pytest.mark.asyncio
async def test_speaker_invokes_say_per_sentence(tmp_path):
    """Replace `say` with a script that records each invocation's text."""
    log = tmp_path / "said.log"
    fake = tmp_path / "fake_say"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"open({str(log)!r}, 'a').write(sys.argv[-1] + '\\n')\n"
    )
    fake.chmod(0o755)

    async with Speaker() as speaker:
        speaker._say_cmd = str(fake)
        speaker.feed("First sentence. Second sentence. And a ")
        speaker.feed("trailing bit")
        await speaker.flush()

    lines = log.read_text().splitlines()
    assert lines == ["First sentence.", "Second sentence.", "And a trailing bit"]


@pytest.mark.asyncio
async def test_say_failure_falls_back_to_notification(tmp_path):
    """§5.4: a failing `say` surfaces the text as an osascript notification."""
    notify_log = tmp_path / "notified.log"
    bad_say = tmp_path / "bad_say"
    bad_say.write_text("#!/usr/bin/env python3\nimport sys\nsys.exit(1)\n")
    bad_say.chmod(0o755)
    fake_osascript = tmp_path / "fake_osascript"
    fake_osascript.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"open({str(notify_log)!r}, 'a').write(sys.argv[-1] + '\\n')\n"
    )
    fake_osascript.chmod(0o755)

    async with Speaker() as speaker:
        speaker._say_cmd = str(bad_say)
        speaker._osascript_cmd = str(fake_osascript)
        speaker.feed("Something important. ")
        await speaker.flush()

    lines = notify_log.read_text().splitlines()
    assert len(lines) == 1
    assert "Something important." in lines[0]
    assert "display notification" in lines[0]


@pytest.mark.asyncio
async def test_missing_say_binary_also_falls_back(tmp_path):
    notify_log = tmp_path / "notified.log"
    fake_osascript = tmp_path / "fake_osascript"
    fake_osascript.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"open({str(notify_log)!r}, 'a').write(sys.argv[-1] + '\\n')\n"
    )
    fake_osascript.chmod(0o755)

    async with Speaker() as speaker:
        speaker._say_cmd = str(tmp_path / "does_not_exist")
        speaker._osascript_cmd = str(fake_osascript)
        speaker.feed("Hello. ")
        await speaker.flush()

    assert "Hello." in notify_log.read_text()


@pytest.mark.asyncio
async def test_interrupt_clears_queue(tmp_path):
    log = tmp_path / "said.log"
    fake = tmp_path / "fake_say"
    # Slow fake so we can interrupt mid-queue.
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import sys, time\n"
        "time.sleep(0.2)\n"
        f"open({str(log)!r}, 'a').write(sys.argv[-1] + '\\n')\n"
    )
    fake.chmod(0o755)

    async with Speaker() as speaker:
        speaker._say_cmd = str(fake)
        speaker.feed("One. Two. Three. Four. ")
        await asyncio.sleep(0.05)  # let the worker pick up the first sentence
        await speaker.interrupt()

    said = log.read_text().splitlines() if log.exists() else []
    # At most the one in-flight sentence should have completed.
    assert len(said) <= 1
