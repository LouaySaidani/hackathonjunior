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


def test_split_long_gaps_prefers_shot_changes():
    from app.pipeline.vad import split_long_gaps

    # short gaps are untouched, splitting can be disabled
    assert split_long_gaps([(0.0, 8.0)], [4.0]) == [(0.0, 8.0)]
    assert split_long_gaps([(0.0, 40.0)], [], max_len=0) == [(0.0, 40.0)]
    # a 30 s silence with shot changes at 7 s and 18 s is cut there
    slots = split_long_gaps([(0.0, 30.0)], [7.0, 16.0, 29.5], max_len=10)
    assert slots[:2] == [(0.0, 7.0), (7.0, 16.0)]  # cut at the shot changes
    assert slots[-1][1] == 30.0 and all(b - a >= 1.5 for a, b in slots)  # 29.5 is too close to the end
    # no shot change: regular slots, contiguous, each <= max_len and >= min_len, covering the whole gap
    slots = split_long_gaps([(5.0, 36.0)], [], max_len=10, min_len=1.5)
    assert len(slots) == 4 and slots[0][0] == 5.0 and slots[-1][1] == 36.0  # 4 equal slots of 7.75 s
    assert all(b - a <= 10 + 1e-6 and b - a >= 1.5 for a, b in slots)
    assert all(slots[i][1] == slots[i + 1][0] for i in range(len(slots) - 1))
