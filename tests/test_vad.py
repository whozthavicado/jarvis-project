"""VAD segmentation tests — pure state machine, no audio hardware."""
from jarvis.config import get_settings
from jarvis.audio.vad import LOW_ENERGY_RMS_THRESHOLD, VadSegmenter, VoicedSegment, _energy_speech


def _frame(voiced: bool, frame_ms=30, sample_rate=16000) -> bytes:
    n = sample_rate * frame_ms // 1000
    return (b"\xff\xff" if voiced else b"\x00\x00") * n


def _segmenter():
    # Inject a deterministic detector: a frame is "speech" iff its first byte is set.
    return VadSegmenter(get_settings(), is_speech=lambda f: f[:1] == b"\xff")


def test_speech_then_silence_yields_segment():
    seg = _segmenter()
    s = get_settings()
    end_frames = s.vad.end_silence_ms // s.audio.frame_ms

    out = None
    # 3 voiced (trigger) + 10 voiced (body)
    for _ in range(13):
        assert seg.push(_frame(True)) is None
    # trailing silence to close the segment
    for _ in range(end_frames):
        out = seg.push(_frame(False))
    assert out is not None
    assert isinstance(out, VoicedSegment)
    # Segment length is a whole number of frames.
    assert len(out.pcm) % len(_frame(True)) == 0


def test_pure_silence_yields_nothing():
    seg = _segmenter()
    for _ in range(200):
        assert seg.push(_frame(False)) is None
    assert seg.flush() is None


def test_flush_closes_in_progress_segment():
    seg = _segmenter()
    for _ in range(20):
        seg.push(_frame(True))  # triggered, still open (no trailing silence)
    out = seg.flush()
    assert out is not None
    # A second flush has nothing to return.
    assert seg.flush() is None


def test_max_segment_cap():
    seg = _segmenter()
    s = get_settings()
    max_frames = s.vad.max_segment_ms // s.audio.frame_ms
    out = None
    for _ in range(max_frames + 5):
        r = seg.push(_frame(True))  # never any silence
        if r is not None:
            out = r
            break
    assert out is not None  # capped, not buffered forever


def test_energy_fallback_discriminates_loud_from_silent():
    loud = (b"\xff\x7f") * 480   # ~max int16 amplitude
    quiet = (b"\x00\x00") * 480
    assert _energy_speech(loud) is True
    assert _energy_speech(quiet) is False


def _loud_frame(frame_ms=30, sample_rate=16000) -> bytes:
    n = sample_rate * frame_ms // 1000
    return (b"\xff\x7f") * n  # ~max int16 amplitude


def _quiet_frame(frame_ms=30, sample_rate=16000) -> bytes:
    n = sample_rate * frame_ms // 1000
    return (b"\x00\x00") * n


def test_loud_segment_yields_high_mean_rms():
    # Use energy-based detection so loud frames both trigger and stay voiced.
    seg = VadSegmenter(get_settings(), is_speech=lambda f: f[:2] == b"\xff\x7f")
    s = get_settings()
    end_frames = s.vad.end_silence_ms // s.audio.frame_ms

    out = None
    for _ in range(13):
        seg.push(_loud_frame())
    for _ in range(end_frames):
        out = seg.push(_quiet_frame())

    assert out is not None
    assert out.mean_rms >= LOW_ENERGY_RMS_THRESHOLD


def test_quiet_segment_yields_low_mean_rms():
    # Force-trigger with an injected detector so a quiet segment can still
    # be captured (energy-based detection alone would never trigger it).
    calls = {"n": 0}

    def detector(frame: bytes) -> bool:
        calls["n"] += 1
        return calls["n"] <= 13  # first 13 frames "speech", rest silence

    seg = VadSegmenter(get_settings(), is_speech=detector)
    s = get_settings()
    end_frames = s.vad.end_silence_ms // s.audio.frame_ms

    out = None
    for _ in range(13):
        seg.push(_quiet_frame())
    for _ in range(end_frames):
        out = seg.push(_quiet_frame())

    assert out is not None
    assert out.mean_rms < LOW_ENERGY_RMS_THRESHOLD


async def test_segment_stream_yields_voiced_segments(monkeypatch):
    import jarvis.audio.vad as vad_mod

    # Deterministic detector -- real webrtcvad analyzes frequency content, not
    # just amplitude, so synthetic byte patterns aren't reliably classified.
    monkeypatch.setattr(
        vad_mod, "_make_speech_detector", lambda *a, **kw: (lambda f: f[:2] == b"\xff\x7f")
    )

    s = get_settings()
    end_frames = s.vad.end_silence_ms // s.audio.frame_ms

    async def frames():
        for _ in range(13):
            yield _loud_frame()
        for _ in range(end_frames):
            yield _quiet_frame()

    results = [seg async for seg in vad_mod.segment_stream(frames(), s)]

    assert len(results) == 1
    assert isinstance(results[0], VoicedSegment)
