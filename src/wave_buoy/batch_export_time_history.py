"""Batch export segmented displacement time histories to PNG and TXT."""

from __future__ import annotations

import argparse
import configparser
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from .plot_displacement import (
    VALID_COMPONENTS,
    count_data_rows,
    discover_buoy_dirs,
    estimate_sampling_frequency_hz,
    infer_per_file_sample_dt,
    list_disp_files,
    load_buoy_series,
    parse_cli_time,
    parse_config_list,
    parse_file_start_timestamp,
)


@dataclass(frozen=True)
class SegmentWindow:
    """A segment window identified by index and UTC start/end."""

    index: int
    start: datetime
    end: datetime


def parse_positive_float(value: str, field_name: str) -> float:
    """Parse a positive float used for durations in seconds."""
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {field_name}: {value}") from exc

    if parsed <= 0:
        raise ValueError(f"{field_name} must be > 0")
    return parsed


def parse_positive_int(value: str, field_name: str) -> int:
    """Parse a positive integer."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {field_name}: {value}") from exc

    if parsed <= 0:
        raise ValueError(f"{field_name} must be > 0")
    return parsed


def load_batch_config(path: Path) -> dict[str, object]:
    """Load [batch] settings from an INI file."""
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")

    if "batch" not in parser:
        raise ValueError(f"Missing [batch] section in config: {path}")

    section = parser["batch"]
    values: dict[str, object] = {}

    if section.get("input_root"):
        values["input_root"] = Path(section.get("input_root", "input_data"))
    if section.get("figure_dir"):
        values["figure_dir"] = Path(section.get("figure_dir", "output_figures"))
    if section.get("disp_dir"):
        values["disp_dir"] = Path(section.get("disp_dir", "output_disp"))
    if section.get("start"):
        values["start"] = parse_cli_time(section.get("start", ""))
    if section.get("end"):
        values["end"] = parse_cli_time(section.get("end", ""))
    if section.get("buoy"):
        values["buoy"] = parse_config_list(section.get("buoy"))
    if section.get("component"):
        values["component"] = section.get("component", "").strip()
    if section.get("series_name"):
        values["series_name"] = section.get("series_name", "").strip()
    if section.get("window_seconds"):
        values["window_seconds"] = parse_positive_float(
            section.get("window_seconds", ""),
            "window_seconds",
        )
    if section.get("step_seconds"):
        values["step_seconds"] = parse_positive_float(
            section.get("step_seconds", ""),
            "step_seconds",
        )
    if section.get("segment_count"):
        values["segment_count"] = parse_positive_int(
            section.get("segment_count", ""),
            "segment_count",
        )
    if section.get("start_serial"):
        values["start_serial"] = parse_positive_int(
            section.get("start_serial", ""),
            "start_serial",
        )

    return values


def merge_args_with_config(args: argparse.Namespace) -> argparse.Namespace:
    """Apply config values with CLI arguments taking precedence."""
    cli_overrides = {
        "input_root": args.input_root,
        "figure_dir": args.figure_dir,
        "disp_dir": args.disp_dir,
        "start": args.start,
        "end": args.end,
        "buoy": args.buoy,
        "component": args.component,
        "series_name": args.series_name,
        "window_seconds": args.window_seconds,
        "step_seconds": args.step_seconds,
        "segment_count": args.segment_count,
        "start_serial": args.start_serial,
    }

    config_values: dict[str, object] = {}
    if args.config is not None:
        if not args.config.exists():
            raise FileNotFoundError(f"Config file not found: {args.config}")
        config_values = load_batch_config(args.config)

    merged: dict[str, object] = {
        "input_root": Path("input_data"),
        "figure_dir": Path("output_figures"),
        "disp_dir": Path("output_disp"),
        "start": None,
        "end": None,
        "buoy": None,
        "component": "Upward",
        "series_name": "series",
        "window_seconds": None,
        "step_seconds": None,
        "segment_count": None,
        "start_serial": 1,
    }
    merged.update(config_values)

    for key, value in cli_overrides.items():
        if value is not None:
            merged[key] = value

    args.input_root = merged["input_root"]
    args.figure_dir = merged["figure_dir"]
    args.disp_dir = merged["disp_dir"]
    args.start = merged["start"]
    args.end = merged["end"]
    args.buoy = merged["buoy"]
    args.component = merged["component"]
    args.series_name = merged["series_name"]
    args.window_seconds = merged["window_seconds"]
    args.step_seconds = merged["step_seconds"]
    args.segment_count = merged["segment_count"]
    args.start_serial = merged["start_serial"]
    return args


def infer_latest_data_end_seconds(buoy_dirs: list[Path]) -> float:
    """Infer latest available UTC timestamp across selected buoy dirs."""
    latest_end = float("-inf")

    for buoy_dir in buoy_dirs:
        files = list_disp_files(buoy_dir)
        if not files:
            continue

        start_times = [parse_file_start_timestamp(path) for path in files]
        sample_counts = [count_data_rows(path) for path in files]
        file_dts = infer_per_file_sample_dt(start_times, sample_counts)

        last_start = start_times[-1]
        last_count = sample_counts[-1]
        last_dt = file_dts[-1] if file_dts else 0.0
        buoy_end = last_start + (last_count * last_dt)
        latest_end = max(latest_end, buoy_end)

    if latest_end == float("-inf"):
        raise FileNotFoundError("No *_disp.txt files found for selected buoy folder(s).")
    return latest_end


def build_segment_windows(
    start: datetime,
    window_seconds: float,
    step_seconds: float,
    segment_count: int | None,
    end: datetime | None,
    inferred_latest_end_seconds: float,
) -> list[SegmentWindow]:
    """Build segment windows from user schedule settings."""
    windows: list[SegmentWindow] = []

    if segment_count is not None:
        for index in range(1, segment_count + 1):
            window_start = start + timedelta(seconds=(index - 1) * step_seconds)
            window_end = window_start + timedelta(seconds=window_seconds)
            windows.append(SegmentWindow(index=index, start=window_start, end=window_end))
        return windows

    limit = end if end is not None else datetime.fromtimestamp(inferred_latest_end_seconds, tz=timezone.utc)
    index = 1
    window_start = start
    while window_start < limit:
        window_end = window_start + timedelta(seconds=window_seconds)
        windows.append(SegmentWindow(index=index, start=window_start, end=window_end))
        index += 1
        window_start = window_start + timedelta(seconds=step_seconds)

    return windows


def build_segment_basename(series_name: str, index: int, start: datetime) -> str:
    """Create file name stem like series001_20260309T180000Z."""
    cleaned = series_name.strip()
    if not cleaned:
        raise ValueError("series_name cannot be empty")

    start_tag = start.strftime("%Y%m%dT%H%M%SZ")
    return f"{cleaned}{index:03d}_{start_tag}"


def format_timestamp_utc(value: float) -> str:
    """Format floating-point Unix timestamp as UTC ISO-8601."""
    dt = datetime.fromtimestamp(value, tz=timezone.utc)
    time_text = dt.strftime("%Y-%m-%dT%H:%M:%S.%f").rstrip("0").rstrip(".")
    return f"{time_text}Z"


def write_time_history_txt(path: Path, timestamps_utc_seconds: list[float], displacement: list[float]) -> None:
    """Write three-column time history text file: time_utc, time_s, displacement."""
    path.parent.mkdir(parents=True, exist_ok=True)
    time_origin = float(timestamps_utc_seconds[0]) if timestamps_utc_seconds else 0.0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_utc", "time_s", "displacement"])
        for timestamp, value in zip(timestamps_utc_seconds, displacement):
            elapsed_seconds = float(timestamp) - time_origin
            writer.writerow(
                [
                    format_timestamp_utc(float(timestamp)),
                    f"{elapsed_seconds:.6f}",
                    f"{float(value):.6f}",
                ]
            )


def plot_segment(series_name: str, buoy_name: str, timestamps: list[float], displacement: list[float], output_path: Path) -> None:
    """Create PNG plot for one segment."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    figure, axis = plt.subplots(figsize=(12, 4.5), constrained_layout=True)
    plot_times = [datetime.fromtimestamp(ts, tz=timezone.utc) for ts in timestamps]
    axis.plot(plot_times, displacement, linewidth=1.0)
    axis.set_title(f"Wave Buoy Displacement - {series_name} ({buoy_name})")
    axis.set_xlabel("Time (UTC)")
    axis.set_ylabel("Displacement (m)")
    axis.grid(True, linestyle="--", linewidth=0.6, alpha=0.7)
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
    axis.xaxis.set_major_locator(mdates.AutoDateLocator())
    figure.autofmt_xdate(rotation=20, ha="right")
    figure.savefig(output_path, dpi=180)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch export segmented buoy displacement time history to PNG and TXT."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional INI config path (section [batch]). CLI flags override config values.",
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=None,
        help="Root folder containing buoy folders (default: input_data).",
    )
    parser.add_argument(
        "--start",
        type=parse_cli_time,
        default=None,
        help="First segment start time in UTC. Example: 2026-03-09T18:00:00Z",
    )
    parser.add_argument(
        "--window-seconds",
        type=float,
        default=None,
        help="Time window in seconds for each segment.",
    )
    parser.add_argument(
        "--step-seconds",
        type=float,
        default=None,
        help="Gap in seconds between adjacent segment start times.",
    )
    parser.add_argument(
        "--segment-count",
        type=int,
        default=None,
        help="Number of segments to export. If omitted, runs until --end or data end.",
    )
    parser.add_argument(
        "--start-serial",
        type=int,
        default=None,
        help="Starting serial number for first segment (default: 1).",
    )
    parser.add_argument(
        "--end",
        type=parse_cli_time,
        default=None,
        help="Optional stop time for segment starts (UTC). Ignored when --segment-count is set.",
    )
    parser.add_argument(
        "--buoy",
        nargs="+",
        default=None,
        help="Optional buoy folder names. If omitted, all buoy folders are used.",
    )
    parser.add_argument(
        "--component",
        type=str,
        default=None,
        help="Displacement component to export (Upward, Westward, Northward). Default: Upward",
    )
    parser.add_argument(
        "--series-name",
        type=str,
        default=None,
        help="Series prefix used in names like <series>001_<UTC start>.",
    )
    parser.add_argument(
        "--figure-dir",
        type=Path,
        default=None,
        help="Output folder for PNG files.",
    )
    parser.add_argument(
        "--disp-dir",
        type=Path,
        default=None,
        help="Output folder for TXT displacement files.",
    )
    return parser.parse_args()


def main() -> int:
    args = merge_args_with_config(parse_args())

    if args.start is None:
        raise ValueError("Missing start time. Provide --start or set start in config.")
    if args.window_seconds is None:
        raise ValueError("Missing window_seconds. Provide --window-seconds or set window_seconds in config.")
    if args.step_seconds is None:
        raise ValueError("Missing step_seconds. Provide --step-seconds or set step_seconds in config.")

    if args.window_seconds <= 0:
        raise ValueError("window_seconds must be > 0")
    if args.step_seconds <= 0:
        raise ValueError("step_seconds must be > 0")
    if args.segment_count is not None and args.segment_count <= 0:
        raise ValueError("segment_count must be > 0")
    if args.start_serial <= 0:
        raise ValueError("start_serial must be > 0")
    if args.component not in VALID_COMPONENTS:
        valid = ", ".join(VALID_COMPONENTS)
        raise ValueError(f"Unsupported component: {args.component}. Valid options: {valid}")

    buoy_dirs = discover_buoy_dirs(args.input_root, args.buoy)
    inferred_latest_end_seconds = infer_latest_data_end_seconds(buoy_dirs)

    windows = build_segment_windows(
        start=args.start,
        window_seconds=args.window_seconds,
        step_seconds=args.step_seconds,
        segment_count=args.segment_count,
        end=args.end,
        inferred_latest_end_seconds=inferred_latest_end_seconds,
    )
    if not windows:
        raise ValueError("No segment windows were generated. Check start/end/segment_count settings.")

    multi_buoy = len(buoy_dirs) > 1
    generated_count = 0
    sampling_hz_values: list[float] = []

    for window in windows:
        for buoy_dir in buoy_dirs:
            series = load_buoy_series(
                buoy_dir=buoy_dir,
                start=window.start,
                end=window.end,
                components=[args.component],
            )
            if series.timestamps_utc_seconds.size == 0:
                print(
                    f"[skip] {buoy_dir.name}: no samples in "
                    f"{window.start.isoformat()} to {window.end.isoformat()}."
                )
                continue

            # Serial index follows segment time propagation via window.index (001, 002, ...).
            serial_index = args.start_serial + window.index - 1
            base_name = build_segment_basename(args.series_name, serial_index, window.start)
            if multi_buoy:
                base_name = f"{base_name}_{buoy_dir.name}"

            figure_path = args.figure_dir / f"{base_name}.png"
            txt_path = args.disp_dir / f"{base_name}.txt"

            timestamps = series.timestamps_utc_seconds.tolist()
            displacement = series.components[args.component].tolist()
            plot_segment(
                series_name=args.series_name,
                buoy_name=buoy_dir.name,
                timestamps=timestamps,
                displacement=displacement,
                output_path=figure_path,
            )
            write_time_history_txt(
                path=txt_path,
                timestamps_utc_seconds=timestamps,
                displacement=displacement,
            )
            generated_count += 1
            sampling_hz = estimate_sampling_frequency_hz(series.timestamps_utc_seconds)
            if sampling_hz is None:
                print(f"[ok] {buoy_dir.name}: {figure_path} | {txt_path} | sampling frequency: unavailable")
            else:
                sampling_hz_values.append(sampling_hz)
                print(
                    f"[ok] {buoy_dir.name}: {figure_path} | {txt_path} | "
                    f"sampling frequency: {sampling_hz:.6f} Hz"
                )

    if generated_count == 0:
        print("No output files were generated.")
        return 1

    print(f"Generated {generated_count} PNG/TXT pair(s).")
    print(f"Figures: {args.figure_dir.resolve()}")
    print(f"TXT files: {args.disp_dir.resolve()}")
    if sampling_hz_values:
        print(
            "Sampling frequency summary (Hz): "
            f"min={min(sampling_hz_values):.6f}, "
            f"max={max(sampling_hz_values):.6f}"
        )
    else:
        print("Sampling frequency summary (Hz): unavailable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
