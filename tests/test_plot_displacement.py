from __future__ import annotations

import argparse
import sys
from datetime import timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wave_buoy.plot_displacement import (
    build_series_basename,
    estimate_sampling_frequency_hz,
    infer_per_file_sample_dt,
    load_plot_config,
    merge_args_with_config,
    load_buoy_series,
    parse_cli_time,
)


def test_parse_cli_time_normalizes_to_utc() -> None:
    parsed = parse_cli_time("2026-03-10T12:30:00+01:00")
    assert parsed.tzinfo == timezone.utc
    assert parsed.hour == 11
    assert parsed.minute == 30


def test_infer_per_file_sample_dt_from_adjacent_files() -> None:
    dts = infer_per_file_sample_dt(
        start_times=[1772323200, 1772325000, 1772326800],
        sample_counts=[1800, 900, 1200],
    )
    assert dts[0] == 1.0
    assert dts[1] == 2.0
    assert dts[2] == dts[1]


def test_load_buoy_series_filters_requested_window(tmp_path: Path) -> None:
    buoy_dir = tmp_path / "sample_buoy"
    buoy_dir.mkdir(parents=True)

    first = buoy_dir / "1000_disp.txt"
    first.write_text(
        "Upward,Westward,Northward\n"
        "1.0,10.0,100.0\n"
        "2.0,20.0,200.0\n"
        "3.0,30.0,300.0\n",
        encoding="utf-8",
    )

    second = buoy_dir / "1003_disp.txt"
    second.write_text(
        "Upward,Westward,Northward\n"
        "4.0,40.0,400.0\n"
        "5.0,50.0,500.0\n"
        "6.0,60.0,600.0\n",
        encoding="utf-8",
    )

    start = parse_cli_time("1970-01-01T00:16:41Z")
    end = parse_cli_time("1970-01-01T00:16:44Z")
    series = load_buoy_series(
        buoy_dir=buoy_dir,
        start=start,
        end=end,
        components=["Upward", "Northward"],
    )

    assert np.allclose(series.timestamps_utc_seconds, np.array([1001.0, 1002.0, 1003.0, 1004.0]))
    assert np.allclose(series.components["Upward"], np.array([2.0, 3.0, 4.0, 5.0]))
    assert np.allclose(series.components["Northward"], np.array([200.0, 300.0, 400.0, 500.0]))


def test_load_plot_config_reads_values(tmp_path: Path) -> None:
    cfg = tmp_path / "plot_config.ini"
    cfg.write_text(
        "[plot]\n"
        "start = 2026-03-09T12:00:00Z\n"
        "end = 2026-03-09T13:00:00Z\n"
        "input_root = input_data\n"
        "output_dir = output_figures\n"
        "buoy = b1, b2\n"
        "components = Upward, Northward\n"
        "series_name = obs_\n",
        encoding="utf-8",
    )

    parsed = load_plot_config(cfg)
    assert parsed["buoy"] == ["b1", "b2"]
    assert parsed["components"] == ["Upward", "Northward"]
    assert parsed["series_name"] == "obs_"
    assert parsed["start"].tzinfo == timezone.utc
    assert parsed["end"].tzinfo == timezone.utc


def test_merge_args_with_config_cli_overrides(tmp_path: Path) -> None:
    cfg = tmp_path / "plot_config.ini"
    cfg.write_text(
        "[plot]\n"
        "start = 2026-03-09T12:00:00Z\n"
        "end = 2026-03-09T13:00:00Z\n"
        "buoy = cfg_buoy\n"
        "components = Upward\n",
        encoding="utf-8",
    )
    args = argparse.Namespace(
        config=cfg,
        input_root=None,
        output_dir=None,
        start=None,
        end=None,
        buoy=["cli_buoy"],
        components=["Northward"],
        series_name="cli_",
    )

    merged = merge_args_with_config(args)
    assert merged.buoy == ["cli_buoy"]
    assert merged.components == ["Northward"]
    assert merged.series_name == "cli_"


def test_build_series_basename_matches_plot_style() -> None:
    start = parse_cli_time("2026-03-09T18:00:00Z")
    assert build_series_basename("series_", start) == "series_20260309T180000Z"


def test_estimate_sampling_frequency_hz_from_regular_time_steps() -> None:
    timestamps = np.array([1000.0, 1000.5, 1001.0, 1001.5], dtype=float)
    sampling_hz = estimate_sampling_frequency_hz(timestamps)
    assert sampling_hz == 2.0
