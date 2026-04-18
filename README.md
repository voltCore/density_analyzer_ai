# Spectrana Density

Backend + frontend для числового розрахунку щільності сигналу з IQ-даних Aaronia SPECTRAN V6 / RTSA Suite PRO. Frontend приймає частоту `з` та `по`, кількість `bins`, час збору IQ і reference level. Backend передає налаштування на прилад, читає IQ-потік, рахує power spectral density по FFT-бінах і повертає тільки числові дані.

## Що рахується

Backend оцінює PSD для complex IQ:

- діапазон: `frequency_to_hz - frequency_from_hz`;
- ширина біна: `span / bins`;
- FFT: complex IQ, `fftshift`, Hann window за замовчуванням;
- density: `unit^2/Hz`, або `V^2/Hz`, якщо stream header має `unit=volt`;
- integrated power: сума `density * bin_width_hz`.

Також backend дає оцінку щільності діапазону:

- `noise_floor_db_per_hz`: медіана PSD по всіх bins;
- `threshold_db_per_hz`: `noise_floor + occupancy_threshold_db`, за замовчуванням `+6 dB`;
- `occupied_bins`: кількість bins вище порогу;
- `occupancy_percent`: `occupied_bins / bins * 100`;
- `occupied_bandwidth_hz`: `occupied_bins * bin_width_hz`;
- `label`: `quiet`, `sparse`, `moderate`, або `dense`.

Для практичної оцінки діапазону головне поле: `occupancy_percent`. Наприклад, `30%` означає, що приблизно третина вибраного частотного діапазону має PSD вище локального noise floor на заданий поріг.

Без калібрувальних коефіцієнтів конкретного тракту це не `dBm/Hz`. Якщо IQ з RTSA приходить у volts, backend чесно показує `V^2/Hz`; якщо ні, показує normalized `unit^2/Hz`.

## Структура

```text
backend/   FastAPI, uv, Ruff, ty, pytest, numpy FFT/bin logic
frontend/  Vite + React + TypeScript, форма та числові таблиці
```

## Запуск backend

```bash
cd backend
cp .env.example .env
uv sync
uv run uvicorn spectrana_density.main:app --app-dir src --host 0.0.0.0 --port 8001 --reload --reload-dir src
```

API буде на `http://localhost:8001`.

Перевірки:

```bash
cd backend
uv run ruff check .
uv run ty check .
uv run pytest
```

## Запуск frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Frontend буде на `http://localhost:5173`.

Перевірки:

```bash
cd frontend
npm run typecheck
npm run build
```

## Режими джерела IQ

За замовчуванням backend працює в `SOURCE_MODE=mock`, щоб можна було перевірити FFT/bin-розрахунок без SPECTRAN.

Для реального приладу:

```env
SOURCE_MODE=aaronia
AARONIA_STREAM_URL=http://192.168.1.178:54664/stream?format=raw32
AARONIA_CONTROL_URL=http://192.168.1.178:54664/control
AARONIA_CONTROL_METHOD=PUT
```

Для поточної Aaronia IP вже записаний у [backend/.env](/Users/hliblaskin/Documents/spectrana_density/backend/.env). Перевірка з цієї машини:

```bash
ping -c 3 192.168.1.178
curl --connect-timeout 2 http://192.168.1.178:54664/remoteconfig
curl -X PUT -H 'Content-Type: application/json' \
  -d '{"frequencyCenter":776500000,"frequencySpan":153000000,"type":"capture"}' \
  http://192.168.1.178:54664/control
```

`POST /api/density` надсилає на `/control` JSON з:

- `frequencyStart`
- `frequencyEnd`
- `frequencyCenter`
- `frequencySpan`
- `frequencyBins`
- `referenceLevel`, якщо вказано

Якщо у вашій інсталяції RTSA очікує `POST`, змініть `AARONIA_CONTROL_METHOD=POST`. Якщо потрібен інший payload для конкретного workflow RTSA, змінюється тільки адаптер [aaronia.py](/Users/hliblaskin/Documents/spectrana_density/backend/src/spectrana_density/sources/aaronia.py).

## API

`GET /api/settings`

Повертає default values для форми.

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

Відповідь містить `summary` і масив `bins` з:

- `frequency_hz`
- `density_linear`
- `density_db_per_hz`
- `power_linear`
- `power_db`

## Експорт і порівняння

Frontend після кожного розрахунку дає:

- `Export JSON`: повний snapshot з summary, range assessment, налаштуваннями capture, metadata і bins.
- `Export CSV`: табличний файл для Excel/LibreOffice/Python, з summary rows і bin rows.
- `Зберегти snapshot`: зберігає вимір у backend SQLite БД для порівняння.
- `Імпорт JSON`: додає раніше експортований snapshot у backend SQLite БД.

Перед збереженням можна ввести назву snapshot-а. Якщо назва порожня, backend створить її автоматично з часу виміру, діапазону MHz і `occupancy_percent`.

SQLite файл за замовчуванням:

```text
backend/data/spectrana_density.sqlite3
```

API для БД:

- `GET /api/measurements`: список збережених snapshot-ів.
- `POST /api/measurements`: зберегти snapshot.
- `GET /api/measurements/{id}`: прочитати повний snapshot для порівняння.
- `DELETE /api/measurements/{id}`: видалити snapshot.

## AI пояснення порівняння

У блоці `Порівняння snapshot-ів` є кнопка `Пояснити через AI`. Frontend відправляє два
snapshot-и на backend endpoint:

- `POST /api/comparisons/ai-explanation`: генерує українське пояснення, який сигнал
  щільніший і чому.

Backend не передає API-ключ у браузер. Для роботи потрібні інтернет і ключ у
`backend/.env`:

```text
OPENAI_API_KEY=...
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-5-mini
AI_TIMEOUT_SECONDS=90
```

Якщо ключа або інтернету немає, AI-пояснення не генерується, а frontend показує причину
помилки. Числове табличне порівняння при цьому працює без AI.

## Джерела по Aaronia

Я орієнтував інтеграцію на відкриті матеріали Aaronia:

- [Aaronia forum: C# just IQ data streaming](https://v6-forum.aaronia.de/forum/topic/c-just-iq-data-streaming/) описує RTSA HTTP stream як JSON header + binary IQ data payload, з I/Q interleaved raw values.
- [Aaronia forum: control endpoint](https://v6-forum.aaronia.de/forum/topic/about-control-endpoint/) згадує керування capture settings через control endpoint, включно з frequency center/start/bins/reference level.
- [Aaronia Open Source RTSA HTTP API sequence example](https://github.com/Aaronia-Open-source/python_RTSA_HTTP_API_Sequence_Example) показує практику HTTP remote configuration для RTSA.

Точний control payload може залежати від версії RTSA Suite PRO і вашого graph/config. Тому backend ізолює це в одному адаптері, а mock-режим дозволяє тестувати решту системи незалежно від приладу.
