# Density Analyzer AI

Backend and frontend for numerical signal density analysis from Aaronia SPECTRAN V6 / RTSA Suite PRO IQ data. The frontend accepts a frequency range, bin count, IQ capture duration, and optional reference level. The backend can send capture settings to the device, read the IQ stream, calculate power spectral density across FFT bins, and return numerical data for analysis, export, and comparison.

## What It Calculates

The backend estimates PSD for complex IQ data:

- range: `frequency_to_hz - frequency_from_hz`;
- bin width: `span / bins`;
- FFT: complex IQ, `fftshift`, Hann window by default;
- density: `unit^2/Hz`, or `V^2/Hz` when the stream header reports `unit=volt`;
- integrated power: sum of `density * bin_width_hz`.

The backend also estimates how occupied the selected frequency range is:

- `noise_floor_db_per_hz`: median PSD across all bins;
- `threshold_db_per_hz`: `noise_floor + occupancy_threshold_db`, default `+6 dB`;
- `occupied_bins`: number of bins above the threshold;
- `occupancy_percent`: `occupied_bins / bins * 100`;
- `occupied_bandwidth_hz`: `occupied_bins * bin_width_hz`;
- `label`: `quiet`, `sparse`, `moderate`, or `dense`.

For practical range assessment, the main field is `occupancy_percent`. For example, `30%` means that roughly one third of the selected frequency range has PSD above the local noise floor by the configured threshold.

Without calibration coefficients for the full RF chain, this is not an absolute `dBm/Hz` measurement. If IQ data from RTSA is reported in volts, the backend returns `V^2/Hz`; otherwise it returns normalized `unit^2/Hz`.

## Project Structure

```text
backend/   FastAPI, uv, Ruff, ty, pytest, numpy FFT/bin logic
frontend/  Vite + React + TypeScript, input form, numerical tables, help modal
```

The frontend uses `i18next` and `react-i18next` for localization. English is the default language, and Ukrainian can be selected from the language switcher in the header.

## Run Backend

```bash
cd backend
cp .env.example .env
uv sync
uv run uvicorn spectrana_density.main:app --app-dir src --host 0.0.0.0 --port 8001 --reload --reload-dir src
```

The API will be available at `http://localhost:8001`.

Checks:

```bash
cd backend
uv run ruff check .
uv run ty check .
uv run pytest
```

## Run Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173`.

Checks:

```bash
cd frontend
npm run typecheck
npm run build
```

## IQ Source Modes

By default, the backend runs with `SOURCE_MODE=mock`, so the FFT/bin calculation can be tested without a SPECTRAN device.

For a real device:

```env
SOURCE_MODE=aaronia
AARONIA_STREAM_URL=http://192.168.1.178:54664/stream?format=raw32
AARONIA_CONTROL_URL=http://192.168.1.178:54664/control
AARONIA_CONTROL_METHOD=PUT
```

Create `backend/.env` from `backend/.env.example` and set the IP address and ports for the current Aaronia installation. Basic checks from this machine:

```bash
ping -c 3 192.168.1.178
curl --connect-timeout 2 http://192.168.1.178:54664/remoteconfig
curl -X PUT -H 'Content-Type: application/json' \
  -d '{"frequencyCenter":776500000,"frequencySpan":153000000,"type":"capture"}' \
  http://192.168.1.178:54664/control
```

`POST /api/density` sends a JSON payload to `/control` with:

- `frequencyStart`
- `frequencyEnd`
- `frequencyCenter`
- `frequencySpan`
- `frequencyBins`
- `referenceLevel`, when provided

If your RTSA installation expects `POST`, set `AARONIA_CONTROL_METHOD=POST`. If a different control payload is required for a specific RTSA workflow, only the adapter in `backend/src/spectrana_density/sources/aaronia.py` needs to change.

## API

`GET /api/settings`

Returns default values for the frontend form.

`POST /api/density`

```json
{
  "frequency_from_hz": 2400000000,
  "frequency_to_hz": 2500000000,
  "bins": 1024,
  "capture_seconds": 0.25,
  "reference_level_dbm": null,
  "occupancy_threshold_db": 6,
  "apply_to_device": true,
  "include_bins": true,
  "window": "hann"
}
```

The response contains `summary` and a `bins` array with:

- `frequency_hz`
- `density_linear`
- `density_db_per_hz`
- `power_linear`
- `power_db`

## Export And Comparison

After each calculation, the frontend provides:

- `Export JSON`: full snapshot with summary, range assessment, capture settings, metadata, and bins.
- `Export CSV`: table file for Excel, LibreOffice, or Python with summary rows and bin rows.
- `Save snapshot`: saves a measurement in the backend SQLite database for comparison.
- `Import JSON`: imports a previously exported snapshot into the backend SQLite database.

Before saving, a snapshot name can be entered. If the name is empty, the backend creates one automatically from the measurement time, MHz range, and `occupancy_percent`.

Default SQLite file:

```text
backend/data/spectrana_density.sqlite3
```

Database API:

- `GET /api/measurements`: list saved snapshots.
- `POST /api/measurements`: save a snapshot.
- `GET /api/measurements/{id}`: read a full snapshot for comparison.
- `DELETE /api/measurements/{id}`: delete a snapshot.

## CSV Format

CSV files exported by the frontend use UTF-8 text with commas as separators.

Header:

```csv
record_type,name,value,unit,index,frequency_hz,density_linear,density_db_per_hz,power_linear,power_db
```

Summary rows use `record_type` values such as `capture`, `range`, or `summary`, and fill the `name`, `value`, and `unit` columns. Bin rows use `record_type=bin` and fill `index`, `frequency_hz`, `density_linear`, `density_db_per_hz`, `power_linear`, and `power_db`.

The current import flow accepts JSON snapshots, not CSV files. CSV is intended for spreadsheet or script analysis. To bring a measurement back into the app with all comparison data preserved, export and import JSON.

## AI Comparison Explanation

The `Snapshot comparison` block includes an `Explain with AI` button. The frontend sends two snapshots to the backend endpoint:

- `POST /api/comparisons/ai-explanation`: generates a Ukrainian explanation of which signal is denser and why.

The backend does not expose the API key to the browser. Internet access and a key in `backend/.env` are required:

```text
OPENAI_API_KEY=...
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-5-mini
AI_TIMEOUT_SECONDS=90
```

If there is no key or internet access, the AI explanation is not generated and the frontend shows the error reason. Numerical table comparison still works without AI.

## In-App Help

The frontend includes a `?` help button. It explains what the project measures, what each form field means, how bins and table cells should be interpreted, how CSV rows are structured, and how snapshots are compared.

## Aaronia References

The integration is based on public Aaronia materials:

- [Aaronia forum: C# just IQ data streaming](https://v6-forum.aaronia.de/forum/topic/c-just-iq-data-streaming/) describes RTSA HTTP stream data as a JSON header plus binary IQ payload with interleaved I/Q raw values.
- [Aaronia forum: control endpoint](https://v6-forum.aaronia.de/forum/topic/about-control-endpoint/) mentions capture setting control through a control endpoint, including frequency center/start/bins/reference level.
- [Aaronia Open Source RTSA HTTP API sequence example](https://github.com/Aaronia-Open-source/python_RTSA_HTTP_API_Sequence_Example) shows practical HTTP remote configuration for RTSA.

The exact control payload may depend on the RTSA Suite PRO version and graph/configuration. The backend isolates this behavior in one adapter, while mock mode allows the rest of the system to be tested independently from the device.
