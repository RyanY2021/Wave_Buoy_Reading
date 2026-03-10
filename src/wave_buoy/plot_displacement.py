"""Plot wave buoy displacement time histories from *_disp.txt files."""

from __future__ import annotations

import argparse
import configparser
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

VALID_COMPONENTS = ("Upward", "Westward", "Northward")
DEFAULT_FILE_SPAN_SECONDS = 1800


@dataclass(frozen=True)
class BuoySeries:
    """Time-series data for one buoy."""

    buoy_name: str
    timestamps_utc_seconds: np.ndarray
    components: dict[str, np.ndarray]


def parse_cli_time(value: str) -> datetime:
    """Parse a user time string and normalize to UTC."""
    normalized = value.strip().replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid time '{value}'. Use ISO format like 2026-03-10T00:00:00Z."
        ) from exc

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_file_start_timestamp(path: Path) -> int:
    """Extract the Unix timestamp from a file name like 1772323200_disp.txt."""
    try:
        return int(path.name.split("_", maxsplit=1)[0])
    except ValueError as exc:
        raise ValueError(f"Unable to parse timestamp from file name: {path.name}") from exc


def parse_config_list(value: str | None) -> list[str] | None:
    """Parse list-like config values using comma separators."""
    if value is None:
        return None
    parts = [item.strip() for item in value.split(",")]
    cleaned = [item for item in parts if item]
    return cleaned or None


def build_series_basename(series_name: str, start: datetime) -> str:
    """Build output base name like series_20260309T180000Z."""
    cleaned = series_name.strip().rstrip("_")
    if not cleaned:
        raise ValueError("series_name cannot be empty")
    start_tag = start.strftime("%Y%m%dT%H%M%SZ")
    return f"{cleaned}_{start_tag}"


def load_plot_config(path: Path) -> dict[str, object]:
    """Load [plot] settings from an ini file."""
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")

    if "plot" not in parser:
        raise ValueError(f"Missing [plot] section in config: {path}")

    section = parser["plot"]
    config_values: dict[str, object] = {}

    if section.get("input_root"):
        config_values["input_root"] = Path(section.get("input_root", "input_data"))
    if section.get("output_dir"):
        config_values["output_dir"] = Path(section.get("output_dir", "output_figures"))
    if section.get("start"):
        config_values["start"] = parse_cli_time(section.get("start", ""))
    if section.get("end"):
        config_values["end"] = parse_cli_time(section.get("end", ""))
    if section.get("buoy"):
        config_values["buoy"] = parse_config_list(section.get("buoy"))
    if section.get("components"):
        config_values["components"] = parse_config_list(section.get("components"))
    if section.get("series_name"):
        config_values["series_name"] = section.get("series_name", "").strip()

    return config_values


def merge_args_with_config(args: argparse.Namespace) -> argparse.Namespace:
    """Apply config values and let explicit CLI flags override config values."""
    cli_overrides = {
        "input_root": args.input_root,
        "output_dir": args.output_dir,
        "start": args.start,
        "end": args.end,
        "buoy": args.buoy,
        "components": args.components,
        "series_name": args.series_name,
    }

    config_values: dict[str, object] = {}
    if args.config is not None:
        if not args.config.exists():
            raise FileNotFoundError(f"Config file not found: {args.config}")
        config_values = load_plot_config(args.config)

    merged: dict[str, object] = {
        "input_root": Path("input_data"),
        "output_dir": Path("output_figures"),
        "components": ["Upward"],
        "buoy": None,
        "start": None,
        "end": None,
        "series_name": "series_",
    }
    merged.update(config_values)

    for key, value in cli_overrides.items():
        if value is not None:
            merged[key] = value

    args.input_root = merged["input_root"]
    args.output_dir = merged["output_dir"]
    args.components = merged["components"]
    args.buoy = merged["buoy"]
    args.start = merged["start"]
    args.end = merged["end"]
    args.series_name = merged["series_name"]
    return args


def discover_buoy_dirs(input_root: Path, selected: Iterable[str] | None) -> list[Path]:
    """Return selected buoy directories under the input root."""
    if not input_root.exists():
        raise FileNotFoundError(f"Input root does not exist: {input_root}")

    all_dirs = sorted([p for p in input_root.iterdir() if p.is_dir()], key=lambda p: p.name)
    if not all_dirs:
        raise FileNotFoundError(f"No buoy folders found under: {input_root}")

    if selected is None:
        return all_dirs

    selected_set = set(selected)
    chosen = [p for p in all_dirs if p.name in selected_set]
    missing = sorted(selected_set - {p.name for p in chosen})
    if missing:
        missing_csv = ", ".join(missing)
        raise FileNotFoundError(f"Buoy folder(s) not found: {missing_csv}")
    return chosen


def list_disp_files(buoy_dir: Path) -> list[Path]:
    """List displacement files sorted by timestamp from filename."""
    files = list(buoy_dir.glob("*_disp.txt"))
    return sorted(files, key=parse_file_start_timestamp)


def count_data_rows(path: Path) -> int:
    """Count data rows in a CSV file with a header row."""
    with path.open("r", encoding="utf-8") as handle:
        row_count = sum(1 for _ in handle)
    return max(0, row_count - 1)


def infer_per_file_sample_dt(start_times: list[int], sample_counts: list[int]) -> list[float]:
    """Infer sample interval (seconds) for each file from adjacent files."""
    if len(start_times) != len(sample_counts):
        raise ValueError("start_times and sample_counts must have the same length")
    if not start_times:
        return []

    if len(start_times) == 1:
        if sample_counts[0] <= 0:
            raise ValueError("Cannot infer sample interval from empty file")
        return [DEFAULT_FILE_SPAN_SECONDS / sample_counts[0]]

    dts: list[float] = []
    for idx in range(len(start_times) - 1):
        sample_count = sample_counts[idx]
        if sample_count <= 0:
            raise ValueError(f"File index {idx} is empty; cannot infer interval.")
        delta_t = start_times[idx + 1] - start_times[idx]
        if delta_t <= 0:
            raise ValueError("File timestamps are not strictly increasing")
        dts.append(delta_t / sample_count)

    # Last file does not have a forward neighbor; reuse most recent inferred dt.
    dts.append(dts[-1])
    return dts


def read_disp_components(path: Path, components: list[str]) -> dict[str, np.ndarray]:
    """Read selected displacement components from one file."""
    values = {component: [] for component in components}

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_columns = [component for component in components if component not in reader.fieldnames]
        if missing_columns:
            missing_csv = ", ".join(missing_columns)
            raise ValueError(f"{path.name} is missing column(s): {missing_csv}")

        for row in reader:
            for component in components:
                values[component].append(float(row[component]))

    return {key: np.asarray(series, dtype=float) for key, series in values.items()}


def load_buoy_series(
    buoy_dir: Path,
    start: datetime,
    end: datetime,
    components: list[str],
) -> BuoySeries:
    """Load and filter one buoy's displacement records for the requested time window."""
    if end <= start:
        raise ValueError("End time must be later than start time")

    files = list_disp_files(buoy_dir)
    if not files:
        raise FileNotFoundError(f"No *_disp.txt files found in {buoy_dir}")

    start_times = [parse_file_start_timestamp(path) for path in files]
    sample_counts = [count_data_rows(path) for path in files]
    file_dts = infer_per_file_sample_dt(start_times, sample_counts)

    window_start = start.timestamp()
    window_end = end.timestamp()

    all_timestamps: list[np.ndarray] = []
    component_values: dict[str, list[np.ndarray]] = {component: [] for component in components}

    for idx, path in enumerate(files):
        file_start = start_times[idx]
        file_end = start_times[idx + 1] if idx < len(files) - 1 else file_start + DEFAULT_FILE_SPAN_SECONDS
        if file_end < window_start or file_start > window_end:
            continue

        data = read_disp_components(path, components)
        sample_count = len(next(iter(data.values()))) if data else 0
        if sample_count == 0:
            continue

        dt = file_dts[idx]
        sample_times = file_start + np.arange(sample_count, dtype=float) * dt
        in_window = (sample_times >= window_start) & (sample_times <= window_end)
        if not np.any(in_window):
            continue

        all_timestamps.append(sample_times[in_window])
        for component in components:
            component_values[component].append(data[component][in_window])

    if not all_timestamps:
        return BuoySeries(
            buoy_name=buoy_dir.name,
            timestamps_utc_seconds=np.array([], dtype=float),
            components={component: np.array([], dtype=float) for component in components},
        )

    timestamps_seconds = np.concatenate(all_timestamps)
    merged = {component: np.concatenate(chunks) for component, chunks in component_values.items()}
    return BuoySeries(
        buoy_name=buoy_dir.name,
        timestamps_utc_seconds=timestamps_seconds,
        components=merged,
    )


def estimate_sampling_frequency_hz(timestamps_utc_seconds: np.ndarray) -> float | None:
    """Estimate sampling frequency from median positive time step."""
    if timestamps_utc_seconds.size < 2:
        return None

    diffs = np.diff(timestamps_utc_seconds.astype(float))
    positive_diffs = diffs[diffs > 0]
    if positive_diffs.size == 0:
        return None

    median_dt = float(np.median(positive_diffs))
    if median_dt <= 0:
        return None
    return 1.0 / median_dt


def plot_buoy_series(
    series: BuoySeries,
    components: list[str],
    output_dir: Path,
    start: datetime,
    series_name: str,
    multi_buoy: bool,
) -> Path:
    """Plot selected displacement components and save to PNG."""
    output_dir.mkdir(parents=True, exist_ok=True)

    figure, axis = plt.subplots(figsize=(12, 4.5), constrained_layout=True)
    plot_times = [datetime.fromtimestamp(ts, tz=timezone.utc) for ts in series.timestamps_utc_seconds]

    for component in components:
        axis.plot(plot_times, series.components[component], linewidth=1.0, label=component)

    axis.set_title(f"Wave Buoy Displacement - {series.buoy_name}")
    axis.set_xlabel("Time (UTC)")
    axis.set_ylabel("Displacement (m)")
    axis.grid(True, linestyle="--", linewidth=0.6, alpha=0.7)
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
    axis.xaxis.set_major_locator(mdates.AutoDateLocator())
    figure.autofmt_xdate(rotation=20, ha="right")

    if len(components) > 1:
        axis.legend()

    base_name = build_series_basename(series_name=series_name, start=start)
    if multi_buoy:
        base_name = f"{series.buoy_name}_{base_name}"
    output_path = output_dir / f"{base_name}.png"
    figure.savefig(output_path, dpi=180)
    plt.close(figure)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read buoy *_disp.txt files and plot displacement time history for a UTC time period."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional INI config file path (see plot_config.ini). CLI flags override config values.",
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=None,
        help="Root folder containing buoy subfolders (default: input_data).",
    )
    parser.add_argument(
        "--start",
        type=parse_cli_time,
        default=None,
        help="Start time in UTC. Example: 2026-03-09T12:00:00Z",
    )
    parser.add_argument(
        "--end",
        type=parse_cli_time,
        default=None,
        help="End time in UTC. Example: 2026-03-09T18:00:00Z",
    )
    parser.add_argument(
        "--buoy",
        nargs="+",
        default=None,
        help="Optional buoy folder names. If omitted, all buoy folders are used.",
    )
    parser.add_argument(
        "--components",
        nargs="+",
        default=None,
        help="One or more components to plot (default: Upward). Allowed: Upward Westward Northward",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Folder for PNG outputs (default: output_figures).",
    )
    parser.add_argument(
        "--series-name",
        type=str,
        default=None,
        help="Output naming prefix. Format: <series_name>_<UTC-start>.png",
    )
    return parser.parse_args()


def main() -> int:
    args = merge_args_with_config(parse_args())

    if args.start is None or args.end is None:
        raise ValueError(
            "Start/end time required. Provide --start/--end or set 'start' and 'end' in config."
        )

    invalid_components = [component for component in args.components if component not in VALID_COMPONENTS]
    if invalid_components:
        invalid_csv = ", ".join(invalid_components)
        valid_csv = ", ".join(VALID_COMPONENTS)
        raise ValueError(f"Unsupported component(s): {invalid_csv}. Valid options: {valid_csv}")

    buoy_dirs = discover_buoy_dirs(args.input_root, args.buoy)
    multi_buoy = len(buoy_dirs) > 1
    output_paths: list[Path] = []
    sampling_hz_values: list[float] = []

    for buoy_dir in buoy_dirs:
        series = load_buoy_series(buoy_dir=buoy_dir, start=args.start, end=args.end, components=args.components)
        if series.timestamps_utc_seconds.size == 0:
            print(f"[skip] {buoy_dir.name}: no samples in requested window.")
            continue

        output_path = plot_buoy_series(
            series=series,
            components=args.components,
            output_dir=args.output_dir,
            start=args.start,
            series_name=args.series_name,
            multi_buoy=multi_buoy,
        )
        output_paths.append(output_path)
        sampling_hz = estimate_sampling_frequency_hz(series.timestamps_utc_seconds)
        if sampling_hz is None:
            print(f"[ok] {buoy_dir.name}: {output_path} | sampling frequency: unavailable")
        else:
            sampling_hz_values.append(sampling_hz)
            print(f"[ok] {buoy_dir.name}: {output_path} | sampling frequency: {sampling_hz:.6f} Hz")

    if not output_paths:
        print("No plots were generated.")
        return 1

    print(f"Generated {len(output_paths)} plot(s) in {args.output_dir.resolve()}")
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
