# 202603_Wave_Buoy

Wave buoy displacement plotting workflow.

## What this script does

It reads `*_disp.txt` files from buoy folders under `input_data/`, filters samples by a user-defined UTC time range, and writes `.png` time-history plots to `output_figures/`.

The project also includes a segmented batch exporter that writes both `.png` and `.txt` files.

## Run

Install dependencies first:

```bash
python -m pip install -e .
```

Then run:

```bash
python plot_displacement.py \
  --start 2026-03-09T12:00:00Z \
  --end 2026-03-09T18:00:00Z \
  --buoy 202603_wave_buoy \
  --components Upward
```

## Run With Config + BAT

1. Edit `plot_config.ini`.
2. From project root, run:

```bat
run_plot_displacement.bat
```

Optional custom config path:

```bat
run_plot_displacement.bat path\to\my_config.ini
```

After execution, sampling frequency (Hz) is printed in terminal output.  
The BAT launcher keeps the terminal open and waits for `EXIT`.

## Batch Segmented Time History (PNG + TXT)

Use this when you need repeated windows from one start schedule.

1. Edit `batch_time_history_config.ini`.
2. Run:

```bat
run_batch_time_history.bat
```

Optional custom config path:

```bat
run_batch_time_history.bat path\to\my_batch_config.ini
```

After execution, sampling frequency (Hz) is printed in terminal output.  
The BAT launcher keeps the terminal open and waits for `EXIT`.

### Batch Config Fields

- `start`: first segment start time (UTC ISO).
- `window_seconds`: segment window length.
- `step_seconds`: gap between adjacent segment start times.
- `start_serial`: starting serial number for first segment (`001`, `002`, ...).
- `segment_count`: optional fixed number of segments.
- `end`: optional stop limit for segment starts when `segment_count` is empty.
- `figure_dir`: output folder for `.png`.
- `disp_dir`: output folder for `.txt` time history.
- `series_name`: output naming prefix, producing `<series_name>001_<UTC start>.png/.txt`.

## Options

- `--start` and `--end`: UTC period to extract.
- `--buoy`: Optional one or more buoy folder names. If omitted, all buoy folders are used.
- `--components`: Optional component list (`Upward`, `Westward`, `Northward`). Default is `Upward`.
- `--output-dir`: Optional output folder (default: `output_figures`).
- `--series-name`: Naming prefix for plot output, formatted as `<series_name>_<UTC-start>.png`.
- `--config`: Optional INI config file. CLI arguments override config values.
