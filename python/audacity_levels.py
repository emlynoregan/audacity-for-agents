"""Shared Audacity working level: peak-normalize clips (default −6 dB)."""

from __future__ import annotations

import time

from audacity_pipe import AudacityPipe

PEAK_DB = -6.0
SELECT_END = 100000.0


def select_track(pipe: AudacityPipe, index: int) -> None:
    pipe.do_ok(
        f"Select: Track={index} TrackCount=1 Mode=Set Start=0 End={SELECT_END}"
    )


def normalize_track(pipe: AudacityPipe, index: int, *, peak_db: float = PEAK_DB) -> None:
    select_track(pipe, index)
    time.sleep(0.1)
    pipe.do_ok(
        f"Normalize: PeakLevel={peak_db} ApplyGain=True RemoveDcOffset=True"
    )
    select_track(pipe, index)
    time.sleep(0.1)
    pipe.do("SetTrackAudio: Volume=0")
