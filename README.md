# Wave_Buoy_Reading

Wave buoy displacement processing workflow for segment discovery, extraction, and resampling.

## 1. Purpose

This project supports a 3-step workflow:

1. Use `plot_displacement` for rough inspection of long time ranges.
2. Use `run_plot_displacement` for fine segment confirmation.
3. Resample segment TXT data to `6.333333 Hz` for downstream processing.

If you need serially named segment TXT/PNG exports, use `run_batch_time_history` after Step 2.

## 2. Environment Setup

Run from project root:

```bat
python -m pip install -e .
```

Minimum requirements are defined in `pyproject.toml` (`numpy`, `matplotlib`, Python >= 3.10).

## 3. Data Layout

Expected inputs:

- `input_data/<buoy_folder>/*_disp.txt`

Main generated outputs:

- `output_figures/*.png` from `plot_displacement`
- `output_data/<series>/figure/*.png` and `output_data/<series>/disp/*.txt` from `run_batch_time_history`
- `output_6.33hz_resampled/<series>/*.txt` from `resample_disp_txt`

## 4. End-to-End Workflow

### Step 1: Rough Insight with `plot_displacement.py`

Goal:

- Quickly inspect a broad UTC period and identify potential target segments.

Typical command:

```bat
python plot_displacement.py ^
  --start 2026-03-09T12:00:00Z ^
  --end 2026-03-09T18:00:00Z ^
  --buoy 202603_wave_buoy ^
  --components Upward ^
  --series-name rough_view
```

Key options:

- `--start`, `--end`: UTC bounds (required).
- `--buoy`: one or more buoy folder names.
- `--components`: `Upward`, `Westward`, `Northward`.
- `--series-name`: output prefix.
- `--config plot_config.ini`: optional config-driven run.

Output:

- PNG files in `output_figures/`
- Naming format: `<series_name>_<UTC-start>.png`
- Terminal prints estimated sampling frequency (Hz).

### Step 2: Fine Segment Extraction with `run_plot_displacement.bat`

Goal:

- Narrow the time window and validate exact segment ranges before export/resampling.

Procedure:

1. Edit `plot_config.ini`.
2. Set precise `start` and `end` in UTC.
3. Run:

```bat
run_plot_displacement.bat
```

Optional custom config:

```bat
run_plot_displacement.bat path\to\my_config.ini
```

Behavior:

- BAT remains open and waits for typing `EXIT`.
- Terminal shows sampling frequency summary.

### Optional Step 2B: Segment Export to TXT+PNG with `run_batch_time_history.bat`

Use this when you need many fixed windows and serial file naming.

Procedure:

1. Edit `batch_time_history_config.ini`.
2. Configure `start`, `window_seconds`, and `step_seconds`.
3. Configure `start_serial` (first serial number, e.g. `22` gives `022`).
4. Configure `segment_count` or `end`.
5. Configure `figure_dir`, `disp_dir`, `series_name`, and `buoy`.
6. Run:

```bat
run_batch_time_history.bat
```

Output naming:

- `<series_name>001_<UTC-start>.png/.txt` (serial increases with segment propagation).

Batch TXT columns:

- `time_utc,time_s,displacement`

### Step 3: Resample Segment TXT Data (`6.333333 Hz`)

Goal:

- Standardize all segment TXT files to fixed sampling interval for further processing.

Run:

```bat
python resample_disp_txt.py
```

or:

```bat
run_resample_disp.bat
```

Defaults:

- Source root: `output_data`
- Series: `202603_obs_buoy_400`, `202603_wave_buoy`
- Target frequency: `6.333333 Hz`
- Output root: `output_6.33hz_resampled`

Produced files:

- `output_6.33hz_resampled/202603_obs_buoy_400/*.txt`
- `output_6.33hz_resampled/202603_wave_buoy/*.txt`

Resampled TXT format:

- `time_s,disp_m`

## 5. Recommended Handover Checklist

Before handing data to another user:

1. Confirm target windows in Step 2 plots.
2. Verify batch TXT exists for every intended segment.
3. Run resampling and confirm output file counts match expected segments.
4. Spot-check one file header is `time_s,disp_m`.
5. Record the exact run date/time and config files used.

## 6. Troubleshooting

- `No plots were generated`
  Check UTC start/end and buoy folder name.
- `No *_disp.txt files found`
  Confirm `input_data/<buoy_folder>/` contains source files.
- Resample fails with non-increasing `time_s`
  Recreate batch TXT using latest `run_batch_time_history` flow.
