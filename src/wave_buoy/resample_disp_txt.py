"""Resample displacement TXT files to a target sampling frequency."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

DEFAULT_TARGET_HZ = 6.333333
DEFAULT_SERIES = ("202603_obs_buoy_400", "202603_wave_buoy")


def read_time_and_displacement(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Read time_s and displacement arrays from one TXT file."""
    time_values: list[float] = []
    disp_values: list[float] = []

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"No header in file: {path}")

        if "time_s" not in reader.fieldnames:
            raise ValueError(f"'time_s' column is required in {path}")

        if "displacement" in reader.fieldnames:
            disp_column = "displacement"
        elif "disp_m" in reader.fieldnames:
            disp_column = "disp_m"
        else:
            raise ValueError(f"'displacement' or 'disp_m' column is required in {path}")

        for row in reader:
            time_values.append(float(row["time_s"]))
            disp_values.append(float(row[disp_column]))

    if not time_values:
        return np.array([], dtype=float), np.array([], dtype=float)

    times = np.asarray(time_values, dtype=float)
    displacements = np.asarray(disp_values, dtype=float)
    diffs = np.diff(times)
    if np.any(diffs <= 0):
        raise ValueError(f"time_s must be strictly increasing in {path}")
    return times, displacements


def build_resample_times(input_times: np.ndarray, target_hz: float) -> np.ndarray:
    """Create evenly-spaced sample times within input range."""
    if input_times.size == 0:
        return np.array([], dtype=float)
    if target_hz <= 0:
        raise ValueError("target_hz must be > 0")

    dt = 1.0 / target_hz
    t_start = float(input_times[0])
    t_end = float(input_times[-1])
    count = int(np.floor((t_end - t_start) / dt)) + 1
    return t_start + np.arange(count, dtype=float) * dt


def resample_displacement(input_times: np.ndarray, input_disp: np.ndarray, target_hz: float) -> tuple[np.ndarray, np.ndarray]:
    """Linearly resample displacement onto target frequency timeline."""
    output_times = build_resample_times(input_times, target_hz)
    if output_times.size == 0:
        return output_times, np.array([], dtype=float)
    output_disp = np.interp(output_times, input_times, input_disp)
    return output_times, output_disp


def write_resampled_txt(path: Path, times: np.ndarray, disp: np.ndarray) -> None:
    """Write resampled file with two columns: time_s, disp_m."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_s", "disp_m"])
        for t_value, d_value in zip(times, disp):
            writer.writerow([f"{float(t_value):.6f}", f"{float(d_value):.6f}"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resample displacement TXT files to 6.333333 Hz and write time_s/disp_m outputs."
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path("output_data"),
        help="Input root containing <series>/disp folders (default: output_data).",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("output_6.33hz_resampled"),
        help="Output root for resampled files (default: output_6.33hz_resampled).",
    )
    parser.add_argument(
        "--series",
        nargs="+",
        default=list(DEFAULT_SERIES),
        help="Series folders to process (default: 202603_obs_buoy_400 202603_wave_buoy).",
    )
    parser.add_argument(
        "--target-hz",
        type=float,
        default=DEFAULT_TARGET_HZ,
        help="Target sampling frequency in Hz (default: 6.333333).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.target_hz <= 0:
        raise ValueError("target_hz must be > 0")

    total_written = 0
    for series_name in args.series:
        source_dir = args.source_root / series_name / "disp"
        output_dir = args.output_root / series_name
        if not source_dir.exists():
            raise FileNotFoundError(f"Source folder not found: {source_dir}")

        files = sorted(source_dir.glob("*.txt"))
        if not files:
            print(f"[skip] {series_name}: no TXT files under {source_dir}")
            continue

        for input_path in files:
            input_times, input_disp = read_time_and_displacement(input_path)
            output_times, output_disp = resample_displacement(
                input_times=input_times,
                input_disp=input_disp,
                target_hz=args.target_hz,
            )

            output_path = output_dir / input_path.name
            write_resampled_txt(output_path, output_times, output_disp)
            total_written += 1
            print(
                f"[ok] {series_name}: {output_path} "
                f"(n_in={input_times.size}, n_out={output_times.size})"
            )

    if total_written == 0:
        print("No files were written.")
        return 1

    print(f"Finished. Wrote {total_written} file(s) to {args.output_root.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
