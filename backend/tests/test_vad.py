from app.pipeline.vad import compute_gaps, detect_speech, merge_intervals, overlaps


def test_merge_intervals_sorts_and_joins():
    assert merge_intervals([(5, 6), (1, 2), (1.5, 3)]) == [(1, 3), (5, 6)]
    assert merge_intervals([(1, 2), (2.1, 3)], join_within=0.2) == [(1, 3)]


def test_gaps_respect_min_gap_and_padding():
    speech = [(3.0, 5.8), (12.0, 14.4), (21.0, 23.5), (30.0, 32.7)]
    gaps = compute_gaps(speech, 36.0, min_gap=1.5, padding=0.25)
    assert gaps[0] == (0.0, 2.75)  # no padding at film start
    assert gaps[-1] == (32.95, 36.0)  # no padding at film end
    assert len(gaps) == 5
    for a, b in gaps:
        assert b - a >= 1.5
        assert not overlaps((a, b), speech)


def test_short_silences_are_dropped():
    speech = [(0.0, 2.0), (3.0, 5.0)]  # 1 s silence - too short
    assert compute_gaps(speech, 5.0, min_gap=1.5) == []


def test_no_speech_means_whole_film_is_a_gap():
    assert compute_gaps([], 10.0) == [(0.0, 10.0)]


def test_overlapping_speech_is_merged():
    gaps = compute_gaps([(1, 4), (2, 6), (9, 10)], 12, min_gap=1.0, padding=0.0)
    assert gaps == [(0.0, 1.0), (6.0, 9.0), (10.0, 12.0)]


def test_overlaps_tolerance():
    assert overlaps((1, 3), [(2.9, 5)])
    assert not overlaps((1, 3), [(3.0, 5)])


def test_real_vad_on_sample(sample_video, tmp_path):
    from app.pipeline.media import extract_audio

    wav = extract_audio(sample_video, tmp_path / "a.wav")
    for engine in ("silero", "webrtc"):
        speech, used = detect_speech(wav, engine)
        assert speech, used
        # first dialogue line starts at 3.0 s in the synthetic clip
        assert any(abs(a - 3.0) < 0.6 for a, _ in speech), (used, speech)
        # nothing detected in the opening silence
        assert all(a > 2.0 for a, _ in speech), (used, speech)
