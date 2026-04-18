import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";

import {
  calculateDensity,
  createMeasurement,
  deleteMeasurement,
  explainComparison,
  getDeviceStatus,
  getMeasurement,
  getSettings,
  listMeasurements,
} from "./api";
import type {
  AIComparisonResponse,
  CaptureSettings,
  DensityRequest,
  DensityResponse,
  DeviceStatusResponse,
  MeasurementCreate,
  MeasurementStored,
  MeasurementSummary,
  SettingsResponse,
} from "./types";

const hzFormatter = new Intl.NumberFormat("uk-UA", {
  maximumFractionDigits: 2,
});

const dbFormatter = new Intl.NumberFormat("uk-UA", {
  maximumFractionDigits: 3,
});

const scientificFormatter = new Intl.NumberFormat("uk-UA", {
  maximumSignificantDigits: 6,
  notation: "scientific",
});

const initialRequest: DensityRequest = {
  frequency_from_hz: 2_400_000_000,
  frequency_to_hz: 2_500_000_000,
  bins: 1024,
  capture_seconds: 0.25,
  reference_level_dbm: null,
  occupancy_threshold_db: 6,
  apply_to_device: true,
  include_bins: true,
  window: "hann",
};

const helpSections = [
  {
    title: "Поля розрахунку",
    items: [
      {
        term: "Частота з, Hz",
        description:
          "Початок частотного діапазону. Звідси backend починає збір і розрахунок щільності сигналу.",
      },
      {
        term: "Частота по, Hz",
        description:
          "Кінець діапазону. Різниця між кінцевою та початковою частотою утворює span виміру.",
      },
      {
        term: "Bins",
        description:
          "Кількість клітинок частотної сітки. Кожен bin відповідає маленькій частині діапазону, для якої рахується щільність і потужність.",
      },
      {
        term: "Час IQ, sec",
        description:
          "Скільки секунд збирати IQ-дані. Більший час дає більше семплів і стабільнішу оцінку, але розрахунок триває довше.",
      },
      {
        term: "Reference level, dBm",
        description:
          "Опційний рівень опори для приймача Aaronia. Він допомагає приладу вибрати коректний рівень тракту, але не перетворює результат у калібрований dBm/Hz без калібрування всього тракту.",
      },
      {
        term: "Поріг зайнятості, dB",
        description:
          "На скільки dB щільність у bin має бути вищою за noise floor, щоб цей bin вважався зайнятим сигналом.",
      },
      {
        term: "Window",
        description:
          "Вікно FFT. Hann зменшує витік спектра між сусідніми bins, Rectangular залишає сире вікно без згладжування.",
      },
      {
        term: "Передавати налаштування на Aaronia",
        description:
          "Коли увімкнено, backend перед розрахунком відправляє діапазон, центр, span, bins і reference level на прилад.",
      },
      {
        term: "Повернути числові дані по bins",
        description:
          "Коли увімкнено, відповідь містить рядок для кожної клітинки частоти. Це потрібно для таблиці, CSV і детального аналізу.",
      },
    ],
  },
  {
    title: "Головні показники",
    items: [
      {
        term: "Range density",
        description:
          "Відсоток діапазону, де bins перевищили поріг зайнятості. Це головний індикатор, наскільки діапазон заповнений сигналом.",
      },
      {
        term: "Assessment",
        description:
          "Словесна оцінка Range density: тихий, рідкий, помірний або щільний. Вона швидко показує стан діапазону без читання всіх чисел.",
      },
      {
        term: "Mean density",
        description:
          "Середня спектральна щільність потужності по всьому діапазону. Корисна для порівняння загального рівня шуму або сигналу між вимірами.",
      },
      {
        term: "Peak density",
        description:
          "Найвища спектральна щільність серед усіх bins. Показує найсильнішу ділянку в обраному діапазоні.",
      },
      {
        term: "Peak frequency",
        description:
          "Частота bin, де знайдено Peak density. Допомагає швидко знайти, де саме знаходиться найсильніший сигнал.",
      },
      {
        term: "Integrated power",
        description:
          "Сумарна потужність по всьому діапазону: density множиться на ширину bin і підсумовується. Це загальна енергія в обраному span.",
      },
      {
        term: "Bin width",
        description:
          "Ширина однієї частотної клітинки: span поділений на bins. Менша ширина дає детальнішу сітку.",
      },
    ],
  },
  {
    title: "Оцінка щільності діапазону",
    items: [
      {
        term: "Noise floor",
        description:
          "Локальна базова щільність шуму, взята як медіана PSD по bins. Від неї система рахує поріг зайнятості.",
      },
      {
        term: "Threshold",
        description:
          "Noise floor плюс Поріг зайнятості. Bins вище цього рівня вважаються зайнятими.",
      },
      {
        term: "Occupied bins",
        description:
          "Скільки bins перевищили Threshold. Наприклад, 300 / 1024 означає, що 300 клітинок частоти були зайняті.",
      },
      {
        term: "Occupied bandwidth",
        description:
          "Оцінена ширина зайнятої смуги: Occupied bins множиться на Bin width.",
      },
      {
        term: "Peak over floor",
        description:
          "Наскільки найсильніший bin вищий за noise floor. Велике значення означає виразний пік сигналу.",
      },
      {
        term: "Mean excess",
        description:
          "Середнє перевищення зайнятих bins над Threshold. Показує, наскільки впевнено зайняті клітинки виходять за поріг.",
      },
    ],
  },
  {
    title: "Клітинки таблиці bins",
    items: [
      {
        term: "#",
        description:
          "Порядковий номер bin у частотній сітці. Це індекс клітинки, а не частота.",
      },
      {
        term: "Frequency, Hz",
        description:
          "Центральна частота конкретного bin. За нею можна знайти, де саме в спектрі лежить значення.",
      },
      {
        term: "Density",
        description:
          "Лінійне значення спектральної щільності потужності для bin. Якщо IQ має unit=volt, одиниця буде V^2/Hz; інакше normalized unit^2/Hz.",
      },
      {
        term: "Density, dB/Hz",
        description:
          "Те саме значення Density у логарифмічній dB-шкалі. Так легше порівнювати слабкі й сильні сигнали.",
      },
      {
        term: "Power",
        description:
          "Потужність у конкретному bin: Density множиться на ширину bin.",
      },
      {
        term: "Power, dB",
        description:
          "Power у dB-шкалі. Це зручно для порівняння окремих частотних клітинок.",
      },
    ],
  },
  {
    title: "Налаштування Aaronia і stream",
    items: [
      {
        term: "Start / End",
        description:
          "Поточні межі діапазону, які backend бачить у stream header або відправляє на прилад.",
      },
      {
        term: "Center / Span",
        description:
          "Центральна частота і повна ширина діапазону. Для приладу це альтернативний спосіб задати ті самі межі Start / End.",
      },
      {
        term: "RBW з FFT size / RBW / bin",
        description:
          "Оцінка частотної роздільної здатності. У цьому проєкті вона відповідає ширині однієї FFT-клітинки.",
      },
      {
        term: "Sample frequency / Sample rate",
        description:
          "Частота дискретизації IQ-потоку. Вона визначає, скільки IQ-семплів приходить за секунду.",
      },
      {
        term: "Samples/packet",
        description:
          "Скільки IQ-семплів приходить в одному пакеті stream. Це допоміжна діагностика потоку.",
      },
      {
        term: "Payload / Unit",
        description:
          "Payload описує формат IQ-даних, Unit показує одиницю семплів. Unit важливий для правильного підпису Density.",
      },
      {
        term: "Remote config",
        description:
          "Поточні значення конфігурації, які backend читає з RTSA remote API: reference level, FFT size, window, clock та інші параметри.",
      },
    ],
  },
  {
    title: "Експорт, snapshot і порівняння",
    items: [
      {
        term: "Snapshot",
        description:
          "Збережений вимір із summary, оцінкою діапазону, bins і статусом приладу. Snapshot потрібен для повторного аналізу та порівняння.",
      },
      {
        term: "База",
        description:
          "Вимір, який береться як початкова точка порівняння. У таблиці delta рахується від нього.",
      },
      {
        term: "Порівняти з",
        description:
          "Другий вимір. Його значення порівнюються з базою, щоб побачити, що стало щільніше, слабше або зсунулось по частоті.",
      },
      {
        term: "Δ",
        description:
          "Різниця між другим виміром і базою. Додатне число означає, що показник у другому snapshot більший.",
      },
      {
        term: "Export JSON",
        description:
          "Повний експорт виміру. Його можна імпортувати назад у застосунок без втрати деталей.",
      },
      {
        term: "Export CSV",
        description:
          "Табличний експорт для Excel, LibreOffice або Python. Містить summary, оцінку діапазону і rows по bins, якщо bins були повернуті.",
      },
      {
        term: "Як зробити CSV файл",
        description:
          "CSV має бути plain text у кодуванні UTF-8 з комою як роздільником. Перший рядок - назви колонок: record_type, name, value, unit, index, frequency_hz, density_linear, density_db_per_hz, power_linear, power_db. Для summary-рядків ставте record_type capture, range або summary і заповнюйте name, value, unit. Для частотних клітинок ставте record_type bin і заповнюйте index, frequency_hz, density_linear, density_db_per_hz, power_linear, power_db.",
      },
      {
        term: "CSV і імпорт",
        description:
          "У цьому інтерфейсі кнопка Імпорт JSON приймає повний JSON snapshot, бо тільки JSON зберігає всі дані для порівняння без втрат. CSV використовуйте як табличний файл для аналізу або передачі чисел; щоб повернути вимір назад у застосунок, експортуйте й імпортуйте JSON.",
      },
      {
        term: "AI пояснення",
        description:
          "Опційний текстовий висновок по двох snapshot-ах. Він не замінює числову таблицю, а пояснює її людською мовою.",
      },
    ],
  },
] as const;

export default function App() {
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [deviceStatus, setDeviceStatus] = useState<DeviceStatusResponse | null>(null);
  const [form, setForm] = useState<DensityRequest>(initialRequest);
  const [result, setResult] = useState<DensityResponse | null>(null);
  const [measurements, setMeasurements] = useState<MeasurementSummary[]>([]);
  const [baselineId, setBaselineId] = useState<string>("");
  const [comparisonId, setComparisonId] = useState<string>("");
  const [baseline, setBaseline] = useState<MeasurementStored | null>(null);
  const [comparison, setComparison] = useState<MeasurementStored | null>(null);
  const [aiExplanation, setAiExplanation] = useState<AIComparisonResponse | null>(null);
  const [aiExplanationError, setAiExplanationError] = useState<string | null>(null);
  const [aiExplanationLoading, setAiExplanationLoading] = useState(false);
  const [measurementName, setMeasurementName] = useState("");
  const [storageNotice, setStorageNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  useEffect(() => {
    getSettings()
      .then((data) => {
        setSettings(data);
        setForm((current) => ({
          ...current,
          frequency_from_hz: data.default_frequency_from_hz,
          frequency_to_hz: data.default_frequency_to_hz,
          bins: data.default_bins,
          capture_seconds: data.default_capture_seconds,
        }));
      })
      .catch((requestError: unknown) => {
        setError(requestError instanceof Error ? requestError.message : "Backend недоступний");
      });
    refreshDeviceStatus();
    void refreshMeasurements();
  }, []);

  useEffect(() => {
    void loadSelectedMeasurement(baselineId, setBaseline);
  }, [baselineId]);

  useEffect(() => {
    void loadSelectedMeasurement(comparisonId, setComparison);
  }, [comparisonId]);

  useEffect(() => {
    setAiExplanation(null);
    setAiExplanationError(null);
  }, [baselineId, comparisonId]);

  useEffect(() => {
    if (!helpOpen) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setHelpOpen(false);
      }
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [helpOpen]);

  const rangeIsValid = useMemo(
    () => form.frequency_to_hz > form.frequency_from_hz && form.bins >= 16,
    [form.bins, form.frequency_from_hz, form.frequency_to_hz],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!rangeIsValid) {
      setError("Кінцева частота має бути більшою за початкову, bins >= 16.");
      return;
    }

    setLoading(true);
    try {
      const payload = {
        ...form,
        reference_level_dbm: Number.isFinite(form.reference_level_dbm)
          ? form.reference_level_dbm
          : null,
      };
      const data = await calculateDensity(payload);
      setResult(data);
      void refreshDeviceStatus();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Не вдалося отримати дані");
    } finally {
      setLoading(false);
    }
  }

  async function refreshDeviceStatus() {
    try {
      const data = await getDeviceStatus();
      setDeviceStatus(data);
    } catch {
      setDeviceStatus(null);
    }
  }

  async function refreshMeasurements() {
    try {
      const data = await listMeasurements();
      setMeasurements(data);
    } catch (requestError) {
      setStorageNotice(
        requestError instanceof Error ? requestError.message : "Не вдалося прочитати БД.",
      );
    }
  }

  async function loadSelectedMeasurement(
    measurementId: string,
    setter: (measurement: MeasurementStored | null) => void,
  ) {
    if (!measurementId) {
      setter(null);
      return;
    }

    try {
      setter(await getMeasurement(measurementId));
    } catch (requestError) {
      setter(null);
      setStorageNotice(
        requestError instanceof Error ? requestError.message : "Не вдалося прочитати snapshot.",
      );
    }
  }

  function handleExportJson() {
    if (!result) {
      return;
    }

    const snapshot = createExportSnapshot(result, deviceStatus, measurementName);
    downloadText(
      `${exportBaseName(result)}.json`,
      "application/json",
      `${JSON.stringify(snapshot, null, 2)}\n`,
    );
  }

  function handleExportCsv() {
    if (!result) {
      return;
    }

    downloadText(`${exportBaseName(result)}.csv`, "text/csv;charset=utf-8", resultToCsv(result));
  }

  async function handleSaveSnapshot() {
    if (!result) {
      return;
    }

    try {
      const saved = await createMeasurement({
        name: measurementName.trim() || null,
        result,
        device_status: deviceStatus,
      });
      setMeasurementName("");
      await refreshMeasurements();
      setBaselineId((current) => current || saved.id);
      setComparisonId(saved.id);
      setComparison(saved);
      setStorageNotice("Snapshot збережено в БД для порівняння.");
    } catch (requestError) {
      setStorageNotice(
        requestError instanceof Error ? requestError.message : "Не вдалося зберегти snapshot.",
      );
    }
  }

  async function handleDeleteSnapshot(id: string) {
    try {
      await deleteMeasurement(id);
      await refreshMeasurements();
      if (baselineId === id) {
        setBaselineId("");
      }
      if (comparisonId === id) {
        setComparisonId("");
      }
    } catch (requestError) {
      setStorageNotice(
        requestError instanceof Error ? requestError.message : "Не вдалося видалити snapshot.",
      );
    }
  }

  async function handleImportJson(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    try {
      const parsed = JSON.parse(await file.text()) as unknown;
      const payload = importedMeasurementPayload(parsed, file.name);
      const saved = await createMeasurement(payload);
      await refreshMeasurements();
      setComparisonId(saved.id);
      setComparison(saved);
      setStorageNotice("JSON snapshot імпортовано в БД для порівняння.");
    } catch (importError) {
      setStorageNotice(
        importError instanceof Error ? importError.message : "Не вдалося імпортувати JSON.",
      );
    } finally {
      event.target.value = "";
    }
  }

  async function handleExplainComparison() {
    if (!baseline || !comparison) {
      return;
    }

    setAiExplanationLoading(true);
    setAiExplanationError(null);
    setAiExplanation(null);
    try {
      const explanation = await explainComparison({
        baseline_name: baseline.name,
        comparison_name: comparison.name,
        baseline: baseline.result,
        comparison: comparison.result,
      });
      setAiExplanation(explanation);
    } catch (requestError) {
      setAiExplanationError(
        requestError instanceof Error ? requestError.message : "AI пояснення недоступне.",
      );
    } finally {
      setAiExplanationLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="topline">
        <div>
          <p className="eyebrow">SPECTRAN V6 IQ</p>
          <h1>Щільність сигналу за діапазоном</h1>
        </div>
        <div className="top-actions">
          <button
            aria-controls="project-help"
            aria-expanded={helpOpen}
            aria-label="Відкрити довідку"
            className="help-trigger"
            type="button"
            onClick={() => setHelpOpen(true)}
          >
            ?
          </button>
          <div className="mode-pill">
            <span>Джерело</span>
            <strong>{settings?.source_mode ?? "..."}</strong>
          </div>
        </div>
      </section>

      {helpOpen ? <HelpDialog onClose={() => setHelpOpen(false)} /> : null}

      <section className="workspace">
        <form className="control-surface" onSubmit={handleSubmit}>
          <label>
            Частота з, Hz
            <input
              type="number"
              min="1"
              step="1"
              value={form.frequency_from_hz}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  frequency_from_hz: Number(event.target.value),
                }))
              }
            />
          </label>

          <label>
            Частота по, Hz
            <input
              type="number"
              min="1"
              step="1"
              value={form.frequency_to_hz}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  frequency_to_hz: Number(event.target.value),
                }))
              }
            />
          </label>

          <label>
            Bins
            <input
              type="number"
              min="16"
              max="65536"
              step="1"
              value={form.bins}
              onChange={(event) =>
                setForm((current) => ({ ...current, bins: Number(event.target.value) }))
              }
            />
          </label>

          <label>
            Час IQ, sec
            <input
              type="number"
              min="0.01"
              max="30"
              step="0.01"
              value={form.capture_seconds}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  capture_seconds: Number(event.target.value),
                }))
              }
            />
          </label>

          <label>
            Reference level, dBm
            <input
              type="number"
              step="1"
              placeholder="опційно"
              value={form.reference_level_dbm ?? ""}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  reference_level_dbm:
                    event.target.value === "" ? null : Number(event.target.value),
                }))
              }
            />
          </label>

          <label>
            Поріг зайнятості, dB
            <input
              type="number"
              min="0.1"
              max="60"
              step="0.5"
              value={form.occupancy_threshold_db}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  occupancy_threshold_db: Number(event.target.value),
                }))
              }
            />
          </label>

          <label>
            Window
            <select
              value={form.window}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  window: event.target.value as DensityRequest["window"],
                }))
              }
            >
              <option value="hann">Hann</option>
              <option value="rectangular">Rectangular</option>
            </select>
          </label>

          <label className="inline-control">
            <input
              type="checkbox"
              checked={form.apply_to_device}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  apply_to_device: event.target.checked,
                }))
              }
            />
            Передавати налаштування на Aaronia
          </label>

          <label className="inline-control">
            <input
              type="checkbox"
              checked={form.include_bins}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  include_bins: event.target.checked,
                }))
              }
            />
            Повернути числові дані по bins
          </label>

          <button disabled={loading || !rangeIsValid} type="submit">
            {loading ? "Рахую..." : "Розрахувати"}
          </button>
        </form>

        <section className="results" aria-live="polite">
          {error ? <div className="error-box">{error}</div> : null}

          <DeviceStatusPanel status={deviceStatus} />

          {!result ? (
            <div className="empty-state">
              <strong>Готово до розрахунку.</strong>
              <span>Введіть діапазон частот і кількість bins.</span>
            </div>
          ) : (
            <>
              <div className="status-row">
                <span>Пристрій налаштовано: {result.configured_device ? "так" : "ні"}</span>
                <span>Packets: {result.metadata.packet_count ?? 0}</span>
              </div>

              <div className="metrics-grid">
                <Metric
                  label="Range density"
                  value={`${dbFormatter.format(result.range_assessment.occupancy_percent)}%`}
                />
                <Metric label="Assessment" value={assessmentLabel(result.range_assessment.label)} />
                <Metric label="Mean density" value={formatDb(result.summary.mean_density_db_per_hz)} />
                <Metric label="Peak density" value={formatDb(result.summary.peak_density_db_per_hz)} />
                <Metric label="Peak frequency" value={`${formatHz(result.summary.peak_frequency_hz)} Hz`} />
                <Metric label="Integrated power" value={formatDb(result.summary.integrated_power_db)} />
                <Metric label="Bin width" value={`${formatHz(result.summary.bin_width_hz)} Hz`} />
              </div>

              <RangeAssessmentPanel result={result} />
              <CaptureSettingsPanel settings={result.capture_settings} />
              <ExportPanel
                result={result}
                measurementName={measurementName}
                storageNotice={storageNotice}
                onNameChange={setMeasurementName}
                onExportJson={handleExportJson}
                onExportCsv={handleExportCsv}
                onSaveSnapshot={handleSaveSnapshot}
                onImportJson={handleImportJson}
              />
              <ComparisonPanel
                measurements={measurements}
                baselineId={baselineId}
                comparisonId={comparisonId}
                baseline={baseline}
                comparison={comparison}
                aiExplanation={aiExplanation}
                aiExplanationError={aiExplanationError}
                aiExplanationLoading={aiExplanationLoading}
                onBaselineChange={setBaselineId}
                onComparisonChange={setComparisonId}
                onDeleteSnapshot={handleDeleteSnapshot}
                onExplainComparison={handleExplainComparison}
              />

              <div className="unit-line">
                Density: {result.summary.density_unit}; power: {result.summary.power_unit}; samples:{" "}
                {result.summary.sample_count}
              </div>

              {result.bins.length > 0 ? (
                <div className="table-shell">
                  <table>
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Frequency, Hz</th>
                        <th>Density</th>
                        <th>Density, dB/Hz</th>
                        <th>Power</th>
                        <th>Power, dB</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.bins.map((bin) => (
                        <tr key={bin.index}>
                          <td>{bin.index}</td>
                          <td>{formatHz(bin.frequency_hz)}</td>
                          <td>{scientificFormatter.format(bin.density_linear)}</td>
                          <td>{dbFormatter.format(bin.density_db_per_hz)}</td>
                          <td>{scientificFormatter.format(bin.power_linear)}</td>
                          <td>{dbFormatter.format(bin.power_db)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </>
          )}
        </section>
      </section>
    </main>
  );
}

function HelpDialog({ onClose }: { onClose: () => void }) {
  return (
    <div
      className="help-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <section
        aria-labelledby="project-help-title"
        aria-modal="true"
        className="help-dialog"
        id="project-help"
        role="dialog"
      >
        <div className="help-header">
          <div>
            <p className="eyebrow">Довідка</p>
            <h2 id="project-help-title">Що вимірює проєкт</h2>
          </div>
          <button className="help-close" type="button" onClick={onClose}>
            Закрити
          </button>
        </div>

        <div className="help-body">
          <div className="help-intro">
            <p>
              Spectrana Density вимірює, як енергія сигналу розподілена всередині обраного
              частотного діапазону. Backend бере IQ-дані, розбиває діапазон на bins, рахує FFT і
              спектральну щільність потужності для кожної частотної клітинки.
            </p>
            <p>
              Головний практичний результат - Range density: яка частина діапазону має щільність
              вище локального noise floor на заданий поріг. Без калібрування всього тракту ці числа
              слід читати як стабільну оцінку для порівняння вимірів, а не як абсолютний dBm/Hz.
            </p>
          </div>

          {helpSections.map((section) => (
            <section className="help-section" key={section.title}>
              <h3>{section.title}</h3>
              <dl className="help-list">
                {section.items.map((item) => (
                  <div className="help-term" key={item.term}>
                    <dt>{item.term}</dt>
                    <dd>{item.description}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}
        </div>
      </section>
    </div>
  );
}

function ExportPanel({
  result,
  measurementName,
  storageNotice,
  onNameChange,
  onExportJson,
  onExportCsv,
  onSaveSnapshot,
  onImportJson,
}: {
  result: DensityResponse;
  measurementName: string;
  storageNotice: string | null;
  onNameChange: (name: string) => void;
  onExportJson: () => void;
  onExportCsv: () => void;
  onSaveSnapshot: () => void;
  onImportJson: (event: ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <section className="settings-panel compact">
      <h2>Експорт і збереження</h2>
      <label>
        Назва snapshot
        <input
          placeholder="наприклад: antenna A, 745 MHz, before filter"
          value={measurementName}
          onChange={(event) => onNameChange(event.target.value)}
        />
      </label>
      <div className="action-row">
        <button type="button" onClick={onSaveSnapshot}>
          Зберегти snapshot
        </button>
        <button type="button" onClick={onExportJson}>
          Export JSON
        </button>
        <button type="button" onClick={onExportCsv}>
          Export CSV
        </button>
        <label className="file-button">
          Імпорт JSON
          <input accept="application/json,.json" type="file" onChange={onImportJson} />
        </label>
      </div>
      <p className="helper-text">
        JSON зберігає повний результат. CSV містить summary, оцінку діапазону і bins для
        табличного порівняння.
      </p>
      {result.bins.length === 0 ? (
        <p className="helper-text">
          У цьому результаті немає rows по bins. Увімкніть “Повернути числові дані по bins” перед
          наступним розрахунком, якщо потрібен bin-level CSV.
        </p>
      ) : null}
      {storageNotice ? <p className="helper-text strong">{storageNotice}</p> : null}
    </section>
  );
}

function ComparisonPanel({
  measurements,
  baselineId,
  comparisonId,
  baseline,
  comparison,
  aiExplanation,
  aiExplanationError,
  aiExplanationLoading,
  onBaselineChange,
  onComparisonChange,
  onDeleteSnapshot,
  onExplainComparison,
}: {
  measurements: MeasurementSummary[];
  baselineId: string;
  comparisonId: string;
  baseline: MeasurementStored | null;
  comparison: MeasurementStored | null;
  aiExplanation: AIComparisonResponse | null;
  aiExplanationError: string | null;
  aiExplanationLoading: boolean;
  onBaselineChange: (id: string) => void;
  onComparisonChange: (id: string) => void;
  onDeleteSnapshot: (id: string) => void;
  onExplainComparison: () => void;
}) {
  return (
    <section className="settings-panel compact">
      <h2>Порівняння snapshot-ів</h2>
      {measurements.length === 0 ? (
        <p className="helper-text">Збережіть перший snapshot у БД після розрахунку.</p>
      ) : (
        <>
          <div className="compare-controls">
            <label>
              База
              <select value={baselineId} onChange={(event) => onBaselineChange(event.target.value)}>
                <option value="">оберіть snapshot</option>
                {measurements.map((measurement) => (
                  <option key={measurement.id} value={measurement.id}>
                    {measurement.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Порівняти з
              <select
                value={comparisonId}
                onChange={(event) => onComparisonChange(event.target.value)}
              >
                <option value="">оберіть snapshot</option>
                {measurements.map((measurement) => (
                  <option key={measurement.id} value={measurement.id}>
                    {measurement.name}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {baseline && comparison ? (
            <>
              <ComparisonMetrics baseline={baseline} comparison={comparison} />
              <AIComparisonPanel
                explanation={aiExplanation}
                error={aiExplanationError}
                loading={aiExplanationLoading}
                onExplain={onExplainComparison}
              />
            </>
          ) : (
            <p className="helper-text">Оберіть два snapshot-и для числового порівняння.</p>
          )}

          <div className="snapshot-list">
            {measurements.map((measurement) => (
              <div className="snapshot-item" key={measurement.id}>
                <div>
                  <strong>{measurement.name}</strong>
                  <span>
                    {formatDateTime(measurement.created_at)} · {formatHz(measurement.frequency_from_hz)}-
                    {formatHz(measurement.frequency_to_hz)} Hz · density{" "}
                    {dbFormatter.format(measurement.occupancy_percent)}% · bins:{" "}
                    {measurement.bins_count}
                  </span>
                </div>
                <button type="button" onClick={() => onDeleteSnapshot(measurement.id)}>
                  Видалити
                </button>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function AIComparisonPanel({
  explanation,
  error,
  loading,
  onExplain,
}: {
  explanation: AIComparisonResponse | null;
  error: string | null;
  loading: boolean;
  onExplain: () => void;
}) {
  return (
    <div className="ai-explanation">
      <div className="ai-explanation-header">
        <h3>AI пояснення</h3>
        <button disabled={loading} type="button" onClick={onExplain}>
          {loading ? "AI аналізує..." : "Пояснити через AI"}
        </button>
      </div>
      <p className="helper-text">Потрібен backend API key та інтернет-з'єднання.</p>
      {error ? <p className="ai-error">{error}</p> : null}
      {explanation ? (
        <div className="ai-result">
          <p>
            <strong>Висновок:</strong> {comparisonWinnerLabel(explanation)}
          </p>
          <p>
            <strong>Числова база:</strong> {explanation.numeric_basis}
          </p>
          {explanation.caveats.length > 0 ? (
            <ul className="ai-caveats">
              {explanation.caveats.map((caveat) => (
                <li key={caveat}>{caveat}</li>
              ))}
            </ul>
          ) : null}
          <div className="ai-text">{explanation.explanation}</div>
        </div>
      ) : null}
    </div>
  );
}

function ComparisonMetrics({
  baseline,
  comparison,
}: {
  baseline: MeasurementStored;
  comparison: MeasurementStored;
}) {
  const base = baseline.result;
  const next = comparison.result;
  const rows = [
    {
      label: "Range density",
      base: `${dbFormatter.format(base.range_assessment.occupancy_percent)}%`,
      next: `${dbFormatter.format(next.range_assessment.occupancy_percent)}%`,
      delta: `${signed(next.range_assessment.occupancy_percent - base.range_assessment.occupancy_percent)} pp`,
    },
    {
      label: "Occupied bandwidth",
      base: `${formatHz(base.range_assessment.occupied_bandwidth_hz)} Hz`,
      next: `${formatHz(next.range_assessment.occupied_bandwidth_hz)} Hz`,
      delta: `${signed(next.range_assessment.occupied_bandwidth_hz - base.range_assessment.occupied_bandwidth_hz)} Hz`,
    },
    {
      label: "Mean density",
      base: formatDb(base.summary.mean_density_db_per_hz),
      next: formatDb(next.summary.mean_density_db_per_hz),
      delta: `${signed(next.summary.mean_density_db_per_hz - base.summary.mean_density_db_per_hz)} dB`,
    },
    {
      label: "Peak density",
      base: formatDb(base.summary.peak_density_db_per_hz),
      next: formatDb(next.summary.peak_density_db_per_hz),
      delta: `${signed(next.summary.peak_density_db_per_hz - base.summary.peak_density_db_per_hz)} dB`,
    },
    {
      label: "Integrated power",
      base: formatDb(base.summary.integrated_power_db),
      next: formatDb(next.summary.integrated_power_db),
      delta: `${signed(next.summary.integrated_power_db - base.summary.integrated_power_db)} dB`,
    },
    {
      label: "Peak frequency",
      base: `${formatHz(base.summary.peak_frequency_hz)} Hz`,
      next: `${formatHz(next.summary.peak_frequency_hz)} Hz`,
      delta: `${signed(next.summary.peak_frequency_hz - base.summary.peak_frequency_hz)} Hz`,
    },
  ];

  return (
    <div className="compare-table-shell">
      <table>
        <thead>
          <tr>
            <th>Metric</th>
            <th>База</th>
            <th>Порівняння</th>
            <th>Δ</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <td>{row.label}</td>
              <td>{row.base}</td>
              <td>{row.next}</td>
              <td>{row.delta}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RangeAssessmentPanel({ result }: { result: DensityResponse }) {
  const assessment = result.range_assessment;
  return (
    <section className="settings-panel compact">
      <h2>Оцінка щільності діапазону</h2>
      <div className="assessment-line">
        <strong>{assessmentLabel(assessment.label)}</strong>
        <span>
          {dbFormatter.format(assessment.occupancy_percent)}% діапазону вище noise floor на{" "}
          {dbFormatter.format(assessment.threshold_offset_db)} dB
        </span>
      </div>
      <div className="settings-grid">
        <InfoItem label="Noise floor" value={formatDb(assessment.noise_floor_db_per_hz)} />
        <InfoItem label="Threshold" value={formatDb(assessment.threshold_db_per_hz)} />
        <InfoItem label="Occupied bins" value={`${assessment.occupied_bins} / ${result.summary.bin_count}`} />
        <InfoItem label="Occupied bandwidth" value={`${formatHz(assessment.occupied_bandwidth_hz)} Hz`} />
        <InfoItem label="Peak over floor" value={`${dbFormatter.format(assessment.peak_to_floor_db)} dB`} />
        <InfoItem label="Mean excess" value={`${dbFormatter.format(assessment.mean_excess_db)} dB`} />
      </div>
    </section>
  );
}

function DeviceStatusPanel({ status }: { status: DeviceStatusResponse | null }) {
  if (!status) {
    return (
      <section className="settings-panel">
        <h2>Налаштування Aaronia</h2>
        <div className="settings-grid">
          <InfoItem label="Status" value="чекаю backend" />
        </div>
      </section>
    );
  }

  const stream = status.stream;
  const currentValues = [
    ["Start", stream?.frequency_from_hz, "Hz"],
    ["End", stream?.frequency_to_hz, "Hz"],
    ["Center", stream?.center_frequency_hz, "Hz"],
    ["Span", stream?.span_hz, "Hz"],
    ["RBW з FFT size", stream?.rbw_from_fft_size_hz, "Hz"],
    ["Sample frequency", stream?.sample_frequency_hz, "Hz"],
    ["Samples/packet", stream?.samples_per_packet, null],
    ["Unit", stream?.unit, null],
  ] as const;

  const remoteSettings = [
    "center_frequency_hz",
    "span",
    "reference_level_dbm",
    "fft_size",
    "fft_size_mode",
    "fft_window",
    "receiver_clock",
    "frequency_range",
  ];

  return (
    <section className="settings-panel">
      <div className="panel-title-row">
        <h2>Налаштування Aaronia</h2>
        <span className={status.reachable ? "ok-chip" : "bad-chip"}>
          {status.reachable ? status.health_state ?? "online" : "offline"}
        </span>
      </div>

      <div className="settings-grid">
        <InfoItem label="Mission" value={status.info.mission ?? "невідомо"} />
        <InfoItem label="Input" value={status.inputs.join(", ") || "main"} />
        <InfoItem label="Payload" value={stream?.payload ?? "невідомо"} />
        <InfoItem label="Control" value={status.endpoints.control ?? "mock"} />
      </div>

      <h3>Поточний stream header</h3>
      <div className="settings-grid">
        {currentValues.map(([label, value, unit]) => (
          <InfoItem key={label} label={label} value={formatMaybeNumber(value, unit)} />
        ))}
      </div>

      <h3>Remote config</h3>
      <div className="settings-grid">
        {remoteSettings.map((key) => {
          const setting = status.settings[key];
          return (
            <InfoItem
              key={key}
              label={setting?.label ?? key}
              value={formatSettingValue(setting?.value, setting?.unit)}
            />
          );
        })}
      </div>
    </section>
  );
}

function CaptureSettingsPanel({ settings }: { settings: CaptureSettings }) {
  return (
    <section className="settings-panel compact">
      <h2>Налаштування цього розрахунку</h2>
      <div className="settings-grid">
        <InfoItem label="Start" value={`${formatHz(settings.frequency_from_hz)} Hz`} />
        <InfoItem label="End" value={`${formatHz(settings.frequency_to_hz)} Hz`} />
        <InfoItem label="Center" value={`${formatHz(settings.center_frequency_hz)} Hz`} />
        <InfoItem label="Span" value={`${formatHz(settings.span_hz)} Hz`} />
        <InfoItem label="RBW / bin" value={`${formatHz(settings.rbw_estimate_hz)} Hz`} />
        <InfoItem label="Sample rate" value={`${formatHz(settings.sample_rate_hz)} Hz`} />
        <InfoItem label="Bins" value={settings.bins} />
        <InfoItem label="Occupancy threshold" value={`${settings.occupancy_threshold_db} dB`} />
        <InfoItem
          label="Reference"
          value={
            settings.reference_level_dbm === null ? "не задано" : `${settings.reference_level_dbm} dBm`
          }
        />
      </div>
    </section>
  );
}

function InfoItem({ label, value }: { label: string; value: string | number | boolean | null }) {
  return (
    <div className="info-item">
      <span>{label}</span>
      <strong>{String(value ?? "немає даних")}</strong>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatHz(value: number) {
  return hzFormatter.format(value);
}

function formatDb(value: number) {
  return `${dbFormatter.format(value)} dB`;
}

function formatMaybeNumber(value: string | number | boolean | null | undefined, unit: string | null) {
  if (typeof value === "number") {
    return unit === "Hz" ? `${formatHz(value)} Hz` : dbFormatter.format(value);
  }
  return value ?? "немає даних";
}

function formatSettingValue(value: string | number | boolean | null | undefined, unit?: string | null) {
  if (typeof value === "number" && unit === "Frequency") {
    return `${formatHz(value)} Hz`;
  }
  if (typeof value === "number" && unit) {
    return `${dbFormatter.format(value)} ${unit}`;
  }
  return value ?? "немає даних";
}

function createExportSnapshot(
  result: DensityResponse,
  deviceStatus: DeviceStatusResponse | null,
  name?: string,
) {
  const createdAt = new Date().toISOString();
  return {
    name: name?.trim() || automaticSnapshotName(result, createdAt),
    created_at: createdAt,
    device_status: deviceStatus,
    result,
  };
}

function importedMeasurementPayload(parsed: unknown, fileName: string): MeasurementCreate {
  const record = isRecord(parsed) ? parsed : {};
  const maybeResult = isDensityResponse(record.result) ? record.result : parsed;

  if (!isDensityResponse(maybeResult)) {
    throw new Error("JSON не схожий на Spectrana Density export.");
  }

  return {
    name: typeof record.name === "string" ? record.name : fileName.replace(/\.json$/i, ""),
    result: maybeResult,
    device_status: isRecord(record.device_status)
      ? (record.device_status as DeviceStatusResponse)
      : null,
  };
}

function isDensityResponse(value: unknown): value is DensityResponse {
  if (!isRecord(value)) {
    return false;
  }
  return (
    isRecord(value.summary) &&
    isRecord(value.capture_settings) &&
    isRecord(value.range_assessment) &&
    Array.isArray(value.bins)
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function automaticSnapshotName(result: DensityResponse, createdAt: string) {
  const startMhz = result.capture_settings.frequency_from_hz / 1_000_000;
  const endMhz = result.capture_settings.frequency_to_hz / 1_000_000;
  const density = result.range_assessment.occupancy_percent;
  return `${formatDateTime(createdAt)} · ${dbFormatter.format(startMhz)}-${dbFormatter.format(endMhz)} MHz · ${dbFormatter.format(density)}%`;
}

function exportBaseName(result: DensityResponse) {
  const startMhz = Math.round(result.capture_settings.frequency_from_hz / 1_000_000);
  const endMhz = Math.round(result.capture_settings.frequency_to_hz / 1_000_000);
  return `spectrana_${startMhz}_${endMhz}_mhz_${new Date().toISOString().replace(/[:.]/g, "-")}`;
}

function resultToCsv(result: DensityResponse) {
  const rows: Array<Array<string | number | boolean | null>> = [
    [
      "record_type",
      "name",
      "value",
      "unit",
      "index",
      "frequency_hz",
      "density_linear",
      "density_db_per_hz",
      "power_linear",
      "power_db",
    ],
  ];

  const addMetric = (section: string, name: string, value: string | number | boolean | null, unit = "") => {
    rows.push([section, name, value, unit, "", "", "", "", "", ""]);
  };

  addMetric("capture", "frequency_from_hz", result.capture_settings.frequency_from_hz, "Hz");
  addMetric("capture", "frequency_to_hz", result.capture_settings.frequency_to_hz, "Hz");
  addMetric("capture", "center_frequency_hz", result.capture_settings.center_frequency_hz, "Hz");
  addMetric("capture", "span_hz", result.capture_settings.span_hz, "Hz");
  addMetric("capture", "rbw_estimate_hz", result.capture_settings.rbw_estimate_hz, "Hz");
  addMetric("capture", "bins", result.capture_settings.bins);
  addMetric("capture", "reference_level_dbm", result.capture_settings.reference_level_dbm, "dBm");
  addMetric("range", "occupancy_percent", result.range_assessment.occupancy_percent, "%");
  addMetric("range", "occupied_bins", result.range_assessment.occupied_bins);
  addMetric("range", "occupied_bandwidth_hz", result.range_assessment.occupied_bandwidth_hz, "Hz");
  addMetric("range", "noise_floor_db_per_hz", result.range_assessment.noise_floor_db_per_hz, "dB/Hz");
  addMetric("range", "threshold_db_per_hz", result.range_assessment.threshold_db_per_hz, "dB/Hz");
  addMetric("range", "label", result.range_assessment.label);
  addMetric("summary", "mean_density_db_per_hz", result.summary.mean_density_db_per_hz, "dB/Hz");
  addMetric("summary", "peak_density_db_per_hz", result.summary.peak_density_db_per_hz, "dB/Hz");
  addMetric("summary", "peak_frequency_hz", result.summary.peak_frequency_hz, "Hz");
  addMetric("summary", "integrated_power_db", result.summary.integrated_power_db, "dB");

  for (const bin of result.bins) {
    rows.push([
      "bin",
      "",
      "",
      "",
      bin.index,
      bin.frequency_hz,
      bin.density_linear,
      bin.density_db_per_hz,
      bin.power_linear,
      bin.power_db,
    ]);
  }

  return `${rows.map(csvRow).join("\n")}\n`;
}

function csvRow(row: Array<string | number | boolean | null>) {
  return row.map(csvCell).join(",");
}

function csvCell(value: string | number | boolean | null) {
  if (value === null) {
    return "";
  }
  const text = String(value);
  if (/[",\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function downloadText(fileName: string, mimeType: string, content: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

function signed(value: number) {
  const formatted = dbFormatter.format(value);
  return value > 0 ? `+${formatted}` : formatted;
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("uk-UA", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(value));
}

function assessmentLabel(label: DensityResponse["range_assessment"]["label"]) {
  const labels = {
    quiet: "тихий",
    sparse: "рідкий",
    moderate: "помірний",
    dense: "щільний",
  };
  return labels[label];
}

function comparisonWinnerLabel(explanation: AIComparisonResponse) {
  if (explanation.winner === "tie") {
    return "сигнали приблизно однакові за щільністю";
  }
  if (explanation.winner === "unclear") {
    return "недостатньо даних для точного висновку";
  }
  return `${explanation.winner_name} щільніший`;
}
