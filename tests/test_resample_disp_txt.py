from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wave_buoy.resample_disp_txt import (
    build_resample_times,
    read_time_and_displacement,
    resample_displacement,
    write_resampled_txt,
)


def test_build_resample_times_from_frequency() -> None:
    input_times = np.array([0.0, 1.0], dtype=float)
    out = build_resample_times(input_times, target_hz=2.0)
    assert np.allclose(out, np.array([0.0, 0.5, 1.0], dtype=float))


def test_resample_displacement_linear_interpolation() -> None:
    input_times = np.array([0.0, 1.0, 2.0], dtype=float)
    input_disp = np.array([0.0, 1.0, 0.0], dtype=float)
    out_t, out_d = resample_displacement(input_times, input_disp, target_hz=2.0)
    assert np.allclose(out_t, np.array([0.0, 0.5, 1.0, 1.5, 2.0], dtype=float))
    assert np.allclose(out_d, np.array([0.0, 0.5, 1.0, 0.5, 0.0], dtype=float))


def test_read_and_write_resampled_txt_format(tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
    src.write_text(
        "time_utc,time_s,displacement\n"
        "2026-03-09T00:00:00Z,0.000000,1.000000\n"
        "2026-03-09T00:00:00.500000Z,0.500000,2.000000\n",
        encoding="utf-8",
    )
    times, disp = read_time_and_displacement(src)
    assert np.allclose(times, np.array([0.0, 0.5]))
    assert np.allclose(disp, np.array([1.0, 2.0]))

    out = tmp_path / "out.txt"
    write_resampled_txt(out, times, disp)
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == "time_s,disp_m"
    assert lines[1] == "0.000000,1.000000"
    assert lines[2] == "0.500000,2.000000"
