from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wave_buoy.batch_export_time_history import (
    build_segment_basename,
    build_segment_windows,
    format_timestamp_utc,
    merge_args_with_config,
    parse_cli_time,
    write_time_history_txt,
)


def test_build_segment_basename_matches_rule() -> None:
    start = parse_cli_time("2026-03-09T18:00:00Z")
    output = build_segment_basename("series_", 1, start)
    assert output == "series_001_20260309T180000Z"


def test_build_segment_basename_serial_increments() -> None:
    start = parse_cli_time("2026-03-09T18:30:00Z")
    output = build_segment_basename("series_", 2, start)
    assert output == "series_002_20260309T183000Z"


def test_build_segment_windows_with_segment_count() -> None:
    start = parse_cli_time("2026-03-09T18:00:00Z")
    windows = build_segment_windows(
        start=start,
        window_seconds=1200,
        step_seconds=1800,
        segment_count=3,
        end=None,
        inferred_latest_end_seconds=0.0,
    )
    assert len(windows) == 3
    assert windows[0].start == parse_cli_time("2026-03-09T18:00:00Z")
    assert windows[1].start == parse_cli_time("2026-03-09T18:30:00Z")
    assert windows[2].start == parse_cli_time("2026-03-09T19:00:00Z")


def test_write_time_history_txt_has_time_seconds_column(tmp_path: Path) -> None:
    output = tmp_path / "segment.txt"
    write_time_history_txt(
        path=output,
        timestamps_utc_seconds=[1000.0, 1001.5],
        displacement=[1.234, 5.678],
    )

    lines = output.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == "time_utc,time_s,displacement"
    assert lines[1] == "1970-01-01T00:16:40Z,0.000000,1.234000"
    assert lines[2] == "1970-01-01T00:16:41.5Z,1.500000,5.678000"


def test_format_timestamp_utc_keeps_utc_suffix() -> None:
    assert format_timestamp_utc(1773057600.0).endswith("Z")


def test_merge_args_with_config_start_serial(tmp_path: Path) -> None:
    cfg = tmp_path / "batch_config.ini"
    cfg.write_text(
        "[batch]\n"
        "start = 2026-03-09T18:00:00Z\n"
        "window_seconds = 1200\n"
        "step_seconds = 1800\n"
        "start_serial = 7\n",
        encoding="utf-8",
    )
    args = argparse.Namespace(
        config=cfg,
        input_root=None,
        figure_dir=None,
        disp_dir=None,
        start=None,
        end=None,
        buoy=None,
        component=None,
        series_name=None,
        window_seconds=None,
        step_seconds=None,
        segment_count=None,
        start_serial=None,
    )
    merged = merge_args_with_config(args)
    assert merged.start_serial == 7

    args.start_serial = 13
    merged_override = merge_args_with_config(args)
    assert merged_override.start_serial == 13
