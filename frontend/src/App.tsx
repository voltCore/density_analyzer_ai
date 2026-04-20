import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";

import {
  calculateDensity,
  compareConductedJammers,
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
  AaroniaSpanMode,
  CaptureSettings,
  ConductedJammerComparisonResponse,
  ConductedJammerWinner,
  DensityRequest,
  DensityResponse,
  DeviceStatusResponse,
  MeasurementCreate,
  MeasurementStored,
  MeasurementSummary,
  SettingsResponse,
} from "./types";
import i18nInstance, { persistLanguage } from "./i18n";

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
  aaronia_span_mode: "auto",
};

const aaroniaSpanModes: AaroniaSpanMode[] = [
  "auto",
  "full",
  "1/2",
  "1/4",
  "1/8",
  "1/16",
  "1/32",
  "1/64",
  "1/128",
  "1/256",
  "1/512",
];

const initialConductedForm = {
  thresholdDb: 6,
  attenuationDb: 60,
  targetFrequencyFromHz: "",
  targetFrequencyToHz: "",
  topBinsLimit: 10,
};

type ConductedForm = typeof initialConductedForm;

type HelpSection = {
  title: string;
  items: Array<{
    term: string;
    description: string;
  }>;
};

export default function App() {
  const { i18n, t } = useTranslation();
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [deviceStatus, setDeviceStatus] = useState<DeviceStatusResponse | null>(null);
  const [form, setForm] = useState<DensityRequest>(initialRequest);
  const [result, setResult] = useState<DensityResponse | null>(null);
  const [measurements, setMeasurements] = useState<MeasurementSummary[]>([]);
  const [baselineId, setBaselineId] = useState<string>("");
  const [comparisonId, setComparisonId] = useState<string>("");
  const [baseline, setBaseline] = useState<MeasurementStored | null>(null);
  const [comparison, setComparison] = useState<MeasurementStored | null>(null);
  const [conductedBaselineId, setConductedBaselineId] = useState<string>("");
  const [conductedJammerAId, setConductedJammerAId] = useState<string>("");
  const [conductedJammerBId, setConductedJammerBId] = useState<string>("");
  const [conductedBaseline, setConductedBaseline] = useState<MeasurementStored | null>(null);
  const [conductedJammerA, setConductedJammerA] = useState<MeasurementStored | null>(null);
  const [conductedJammerB, setConductedJammerB] = useState<MeasurementStored | null>(null);
  const [conductedForm, setConductedForm] = useState<ConductedForm>(initialConductedForm);
  const [conductedResult, setConductedResult] =
    useState<ConductedJammerComparisonResponse | null>(null);
  const [conductedError, setConductedError] = useState<string | null>(null);
  const [conductedLoading, setConductedLoading] = useState(false);
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
        setError(requestError instanceof Error ? requestError.message : t("errors.backendUnavailable"));
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
    void loadSelectedMeasurement(conductedBaselineId, setConductedBaseline);
  }, [conductedBaselineId]);

  useEffect(() => {
    void loadSelectedMeasurement(conductedJammerAId, setConductedJammerA);
  }, [conductedJammerAId]);

  useEffect(() => {
    void loadSelectedMeasurement(conductedJammerBId, setConductedJammerB);
  }, [conductedJammerBId]);

  useEffect(() => {
    setAiExplanation(null);
    setAiExplanationError(null);
  }, [baselineId, comparisonId]);

  useEffect(() => {
    setConductedResult(null);
    setConductedError(null);
  }, [conductedBaselineId, conductedJammerAId, conductedJammerBId]);

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
      setError(t("form.invalidRange"));
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
      setError(requestError instanceof Error ? requestError.message : t("errors.dataFetchFailed"));
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
        requestError instanceof Error ? requestError.message : t("errors.readDbFailed"),
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
        requestError instanceof Error ? requestError.message : t("errors.readSnapshotFailed"),
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
      setStorageNotice(t("notices.savedSnapshot"));
    } catch (requestError) {
      setStorageNotice(
        requestError instanceof Error ? requestError.message : t("errors.saveSnapshotFailed"),
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
      if (conductedBaselineId === id) {
        setConductedBaselineId("");
      }
      if (conductedJammerAId === id) {
        setConductedJammerAId("");
      }
      if (conductedJammerBId === id) {
        setConductedJammerBId("");
      }
    } catch (requestError) {
      setStorageNotice(
        requestError instanceof Error ? requestError.message : t("errors.deleteSnapshotFailed"),
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
      setStorageNotice(t("notices.importedSnapshot"));
    } catch (importError) {
      setStorageNotice(
        importError instanceof Error ? importError.message : t("errors.importFailed"),
      );
    } finally {
      event.target.value = "";
    }
  }

  async function handleAnalyzeConductedComparison() {
    if (!conductedBaseline || !conductedJammerA || !conductedJammerB) {
      setConductedError(t("conducted.selectThree"));
      return;
    }

    let targetFrequencyFromHz: number | null;
    let targetFrequencyToHz: number | null;
    try {
      targetFrequencyFromHz = parseOptionalNumber(conductedForm.targetFrequencyFromHz);
      targetFrequencyToHz = parseOptionalNumber(conductedForm.targetFrequencyToHz);
    } catch {
      setConductedError(t("conducted.invalidNumber"));
      return;
    }

    if (
      targetFrequencyFromHz !== null &&
      targetFrequencyToHz !== null &&
      targetFrequencyToHz <= targetFrequencyFromHz
    ) {
      setConductedError(t("conducted.invalidTargetRange"));
      return;
    }

    setConductedLoading(true);
    setConductedError(null);
    setConductedResult(null);
    try {
      const data = await compareConductedJammers({
        baseline_name: conductedBaseline.name,
        jammer_a_name: conductedJammerA.name,
        jammer_b_name: conductedJammerB.name,
        response_language: i18n.resolvedLanguage === "uk" ? "uk" : "en",
        threshold_db: conductedForm.thresholdDb,
        attenuation_db: conductedForm.attenuationDb,
        target_frequency_from_hz: targetFrequencyFromHz,
        target_frequency_to_hz: targetFrequencyToHz,
        top_bins_limit: Math.trunc(conductedForm.topBinsLimit),
        baseline: conductedBaseline.result,
        jammer_a: conductedJammerA.result,
        jammer_b: conductedJammerB.result,
      });
      setConductedResult(data);
    } catch (requestError) {
      setConductedError(
        requestError instanceof Error ? requestError.message : t("conducted.analysisFailed"),
      );
    } finally {
      setConductedLoading(false);
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
        response_language: i18n.resolvedLanguage === "uk" ? "uk" : "en",
        baseline: baseline.result,
        comparison: comparison.result,
      });
      setAiExplanation(explanation);
    } catch (requestError) {
      setAiExplanationError(
        requestError instanceof Error ? requestError.message : t("errors.aiUnavailable"),
      );
    } finally {
      setAiExplanationLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="topline">
        <div>
          <p className="eyebrow">{t("app.eyebrow")}</p>
          <h1>{t("app.title")}</h1>
        </div>
        <div className="top-actions">
          <LanguageSwitcher />
          <button
            aria-controls="project-help"
            aria-expanded={helpOpen}
            aria-label={t("app.helpOpenLabel")}
            className="help-trigger"
            type="button"
            onClick={() => setHelpOpen(true)}
          >
            ?
          </button>
          <div className="mode-pill">
            <span>{t("app.source")}</span>
            <strong>{settings ? t(`sourceMode.${settings.source_mode}`) : "..."}</strong>
          </div>
        </div>
      </section>

      {helpOpen ? <HelpDialog onClose={() => setHelpOpen(false)} /> : null}

      <section className="workspace">
        <form className="control-surface" onSubmit={handleSubmit}>
          <label>
            {t("form.frequencyFrom")}
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
            {t("form.frequencyTo")}
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
            {t("form.bins")}
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
            {t("form.captureSeconds")}
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
            {t("form.referenceLevel")}
            <input
              type="number"
              step="1"
              placeholder={t("form.optional")}
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
            {t("form.occupancyThreshold")}
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
            {t("form.window")}
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

          <label>
            {t("form.aaroniaSpan")}
            <select
              value={form.aaronia_span_mode}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  aaronia_span_mode: event.target.value as AaroniaSpanMode,
                }))
              }
            >
              {aaroniaSpanModes.map((mode) => (
                <option key={mode} value={mode}>
                  {t(`aaroniaSpan.${mode.replace("/", "_")}`)}
                </option>
              ))}
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
            {t("form.applyToDevice")}
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
            {t("form.includeBins")}
          </label>

          <button disabled={loading || !rangeIsValid} type="submit">
            {loading ? t("form.loading") : t("form.submit")}
          </button>
        </form>

        <section className="results" aria-live="polite">
          {error ? <div className="error-box">{error}</div> : null}

          <DeviceStatusPanel status={deviceStatus} />

          <ConductedComparisonPanel
            measurements={measurements}
            baselineId={conductedBaselineId}
            jammerAId={conductedJammerAId}
            jammerBId={conductedJammerBId}
            form={conductedForm}
            result={conductedResult}
            error={conductedError}
            loading={conductedLoading}
            onBaselineChange={setConductedBaselineId}
            onJammerAChange={setConductedJammerAId}
            onJammerBChange={setConductedJammerBId}
            onFormChange={setConductedForm}
            onAnalyze={handleAnalyzeConductedComparison}
          />

          {!result ? (
            <div className="empty-state">
              <strong>{t("status.readyTitle")}</strong>
              <span>{t("status.readyText")}</span>
            </div>
          ) : (
            <>
              <div className="status-row">
                <span>
                  {t("status.deviceConfigured")}:{" "}
                  {result.configured_device ? t("status.yes") : t("status.no")}
                </span>
                <span>
                  {t("status.packets")}: {result.metadata.packet_count ?? 0}
                </span>
              </div>

              <div className="metrics-grid">
                <Metric
                  label={t("metrics.rangeDensity")}
                  value={`${formatCompactNumber(result.range_assessment.occupancy_percent)}%`}
                />
                <Metric
                  label={t("metrics.assessment")}
                  value={assessmentLabel(result.range_assessment.label, t)}
                />
                <Metric
                  label={t("metrics.meanDensity")}
                  value={formatDb(result.summary.mean_density_db_per_hz)}
                />
                <Metric
                  label={t("metrics.peakDensity")}
                  value={formatDb(result.summary.peak_density_db_per_hz)}
                />
                <Metric
                  label={t("metrics.peakFrequency")}
                  value={`${formatHz(result.summary.peak_frequency_hz)} Hz`}
                />
                <Metric
                  label={t("metrics.integratedPower")}
                  value={formatDb(result.summary.integrated_power_db)}
                />
                <Metric
                  label={t("metrics.binWidth")}
                  value={`${formatHz(result.summary.bin_width_hz)} Hz`}
                />
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
                {t("status.density")}: {result.summary.density_unit}; {t("status.power")}:{" "}
                {result.summary.power_unit}; {t("status.samples")}: {result.summary.sample_count}
              </div>

              {result.bins.length > 0 ? (
                <div className="table-shell">
                  <table>
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>{t("table.frequencyHz")}</th>
                        <th>{t("table.density")}</th>
                        <th>{t("table.densityDbHz")}</th>
                        <th>{t("table.power")}</th>
                        <th>{t("table.powerDb")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.bins.map((bin) => (
                        <tr key={bin.index}>
                          <td>{bin.index}</td>
                          <td>{formatHz(bin.frequency_hz)}</td>
                          <td>{formatScientific(bin.density_linear)}</td>
                          <td>{formatCompactNumber(bin.density_db_per_hz)}</td>
                          <td>{formatScientific(bin.power_linear)}</td>
                          <td>{formatCompactNumber(bin.power_db)}</td>
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

function LanguageSwitcher() {
  const { i18n, t } = useTranslation();
  const language = i18n.resolvedLanguage ?? i18n.language;

  async function handleLanguageChange(event: ChangeEvent<HTMLSelectElement>) {
    const nextLanguage = event.target.value;
    await i18n.changeLanguage(nextLanguage);
    persistLanguage(nextLanguage);
  }

  return (
    <label className="language-select">
      <span>{t("app.language")}</span>
      <select value={language} onChange={handleLanguageChange}>
        <option value="en">{t("language.english")}</option>
        <option value="uk">{t("language.ukrainian")}</option>
      </select>
    </label>
  );
}

function HelpDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const intro = t("help.intro", { returnObjects: true }) as string[];
  const helpSections = t("help.sections", { returnObjects: true }) as HelpSection[];

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
            <p className="eyebrow">{t("help.eyebrow")}</p>
            <h2 id="project-help-title">{t("help.title")}</h2>
          </div>
          <button className="help-close" type="button" onClick={onClose}>
            {t("help.close")}
          </button>
        </div>

        <div className="help-body">
          <div className="help-intro">
            {intro.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
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
  const { t } = useTranslation();

  return (
    <section className="settings-panel compact">
      <h2>{t("exportPanel.title")}</h2>
      <label>
        {t("exportPanel.snapshotName")}
        <input
          placeholder={t("exportPanel.placeholder")}
          value={measurementName}
          onChange={(event) => onNameChange(event.target.value)}
        />
      </label>
      <div className="action-row">
        <button type="button" onClick={onSaveSnapshot}>
          {t("exportPanel.save")}
        </button>
        <button type="button" onClick={onExportJson}>
          {t("exportPanel.exportJson")}
        </button>
        <button type="button" onClick={onExportCsv}>
          {t("exportPanel.exportCsv")}
        </button>
        <label className="file-button">
          {t("exportPanel.importJson")}
          <input accept="application/json,.json" type="file" onChange={onImportJson} />
        </label>
      </div>
      <p className="helper-text">{t("exportPanel.helper")}</p>
      {result.bins.length === 0 ? (
        <p className="helper-text">{t("exportPanel.noBins")}</p>
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
  const { t } = useTranslation();

  return (
    <section className="settings-panel compact">
      <h2>{t("comparison.title")}</h2>
      {measurements.length === 0 ? (
        <p className="helper-text">{t("comparison.empty")}</p>
      ) : (
        <>
          <div className="compare-controls">
            <label>
              {t("comparison.baseline")}
              <select value={baselineId} onChange={(event) => onBaselineChange(event.target.value)}>
                <option value="">{t("comparison.chooseSnapshot")}</option>
                {measurements.map((measurement) => (
                  <option key={measurement.id} value={measurement.id}>
                    {measurement.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              {t("comparison.compareWith")}
              <select
                value={comparisonId}
                onChange={(event) => onComparisonChange(event.target.value)}
              >
                <option value="">{t("comparison.chooseSnapshot")}</option>
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
            <p className="helper-text">{t("comparison.selectTwo")}</p>
          )}

          <div className="snapshot-list">
            {measurements.map((measurement) => (
              <div className="snapshot-item" key={measurement.id}>
                <div>
                  <strong>{measurement.name}</strong>
                  <span>
                    {formatDateTime(measurement.created_at)} · {formatHz(measurement.frequency_from_hz)}-
                    {formatHz(measurement.frequency_to_hz)} Hz · {t("comparison.density")}{" "}
                    {formatCompactNumber(measurement.occupancy_percent)}% · {t("comparison.bins")}:{" "}
                    {measurement.bins_count}
                  </span>
                </div>
                <button type="button" onClick={() => onDeleteSnapshot(measurement.id)}>
                  {t("comparison.delete")}
                </button>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function ConductedComparisonPanel({
  measurements,
  baselineId,
  jammerAId,
  jammerBId,
  form,
  result,
  error,
  loading,
  onBaselineChange,
  onJammerAChange,
  onJammerBChange,
  onFormChange,
  onAnalyze,
}: {
  measurements: MeasurementSummary[];
  baselineId: string;
  jammerAId: string;
  jammerBId: string;
  form: ConductedForm;
  result: ConductedJammerComparisonResponse | null;
  error: string | null;
  loading: boolean;
  onBaselineChange: (id: string) => void;
  onJammerAChange: (id: string) => void;
  onJammerBChange: (id: string) => void;
  onFormChange: (form: ConductedForm) => void;
  onAnalyze: () => void;
}) {
  const { t } = useTranslation();
  const canAnalyze = Boolean(baselineId && jammerAId && jammerBId) && !loading;

  return (
    <section className="settings-panel compact">
      <h2>{t("conducted.title")}</h2>
      <div className="warning-box">
        <strong>{t("conducted.safetyTitle")}</strong>
        <span>{t("conducted.safetyLine1")}</span>
        <span>{t("conducted.safetyLine2")}</span>
        <span>{t("conducted.safetyLine3")}</span>
      </div>

      {measurements.length === 0 ? (
        <p className="helper-text">{t("comparison.empty")}</p>
      ) : (
        <>
          <div className="conducted-controls">
            <label>
              {t("conducted.baseline")}
              <select value={baselineId} onChange={(event) => onBaselineChange(event.target.value)}>
                <option value="">{t("comparison.chooseSnapshot")}</option>
                {measurements.map((measurement) => (
                  <option key={measurement.id} value={measurement.id}>
                    {measurement.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              {t("conducted.jammerA")}
              <select value={jammerAId} onChange={(event) => onJammerAChange(event.target.value)}>
                <option value="">{t("comparison.chooseSnapshot")}</option>
                {measurements.map((measurement) => (
                  <option key={measurement.id} value={measurement.id}>
                    {measurement.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              {t("conducted.jammerB")}
              <select value={jammerBId} onChange={(event) => onJammerBChange(event.target.value)}>
                <option value="">{t("comparison.chooseSnapshot")}</option>
                {measurements.map((measurement) => (
                  <option key={measurement.id} value={measurement.id}>
                    {measurement.name}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="conducted-fields">
            <label>
              {t("conducted.thresholdDb")}
              <input
                min="0"
                step="0.5"
                type="number"
                value={form.thresholdDb}
                onChange={(event) =>
                  onFormChange({ ...form, thresholdDb: Number(event.target.value) })
                }
              />
            </label>
            <label>
              {t("conducted.attenuationDb")}
              <input
                min="0"
                step="1"
                type="number"
                value={form.attenuationDb}
                onChange={(event) =>
                  onFormChange({ ...form, attenuationDb: Number(event.target.value) })
                }
              />
            </label>
            <label>
              {t("conducted.targetFrom")}
              <input
                min="1"
                placeholder={t("conducted.overlapPlaceholder")}
                step="1"
                type="number"
                value={form.targetFrequencyFromHz}
                onChange={(event) =>
                  onFormChange({ ...form, targetFrequencyFromHz: event.target.value })
                }
              />
            </label>
            <label>
              {t("conducted.targetTo")}
              <input
                min="1"
                placeholder={t("conducted.overlapPlaceholder")}
                step="1"
                type="number"
                value={form.targetFrequencyToHz}
                onChange={(event) =>
                  onFormChange({ ...form, targetFrequencyToHz: event.target.value })
                }
              />
            </label>
            <label>
              {t("conducted.topBins")}
              <input
                min="0"
                max="100"
                step="1"
                type="number"
                value={form.topBinsLimit}
                onChange={(event) =>
                  onFormChange({ ...form, topBinsLimit: Number(event.target.value) })
                }
              />
            </label>
          </div>

          <div className="action-row">
            <button disabled={!canAnalyze} type="button" onClick={onAnalyze}>
              {loading ? t("conducted.analyzing") : t("conducted.analyze")}
            </button>
          </div>
          {!canAnalyze ? <p className="helper-text">{t("conducted.selectThree")}</p> : null}
          {error ? <p className="ai-error">{error}</p> : null}
          {result ? <ConductedResultPanel result={result} /> : null}
        </>
      )}
    </section>
  );
}

function ConductedResultPanel({ result }: { result: ConductedJammerComparisonResponse }) {
  const { t } = useTranslation();
  const rows = conductedMetricRows(result, t);

  return (
    <div className="conducted-result">
      <div className="conducted-summary">
        <p>
          <strong>{t("conducted.winner")}</strong>{" "}
          {conductedWinnerLabel(result.winner, result.winner_name, t)}
        </p>
        <p>
          <strong>{t("conducted.analysisQuality")}</strong>{" "}
          {t(`conducted.quality.${result.analysis_quality}`)}
        </p>
        {result.compared_frequency_from_hz !== null &&
        result.compared_frequency_to_hz !== null &&
        result.bin_width_hz !== null ? (
          <p>
            <strong>{t("conducted.comparedRange")}</strong>{" "}
            {formatFrequencySmart(result.compared_frequency_from_hz)}-
            {formatFrequencySmart(result.compared_frequency_to_hz)}; {t("metrics.binWidth")}:{" "}
            {formatFrequencySmart(result.bin_width_hz)}
          </p>
        ) : null}
        <p>{result.summary}</p>
        <p className="helper-text">{result.numeric_basis}</p>
      </div>

      {result.warnings.length > 0 ? (
        <div className="warning-box compact-warning">
          <strong>{t("conducted.warnings")}</strong>
          <ul>
            {result.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="compare-table-shell">
        <table>
          <thead>
            <tr>
              <th>{t("comparison.metric")}</th>
              <th>{result.jammer_a_name}</th>
              <th>{result.jammer_b_name}</th>
              <th>{t("conducted.metricWinner")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label}>
                <td>{row.label}</td>
                <td>{row.jammerA}</td>
                <td>{row.jammerB}</td>
                <td>{row.winner}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="conducted-top-bins">
        <ConductedTopBins
          bins={result.jammer_a.top_raised_bins}
          title={t("conducted.topRaisedFor", { name: result.jammer_a_name })}
        />
        <ConductedTopBins
          bins={result.jammer_b.top_raised_bins}
          title={t("conducted.topRaisedFor", { name: result.jammer_b_name })}
        />
      </div>
    </div>
  );
}

function ConductedTopBins({
  title,
  bins,
}: {
  title: string;
  bins: ConductedJammerComparisonResponse["jammer_a"]["top_raised_bins"];
}) {
  const { t } = useTranslation();

  return (
    <div className="top-bin-table">
      <h3>{title}</h3>
      {bins.length === 0 ? (
        <p className="helper-text">{t("conducted.noRaisedBins")}</p>
      ) : (
        <div className="compare-table-shell">
          <table>
            <thead>
              <tr>
                <th>{t("table.frequencyHz")}</th>
                <th>{t("conducted.baselineDensity")}</th>
                <th>{t("conducted.jammerDensity")}</th>
                <th>{t("conducted.deltaDb")}</th>
              </tr>
            </thead>
            <tbody>
              {bins.map((bin) => (
                <tr key={`${title}-${bin.frequency_hz}`}>
                  <td>{formatFrequencySmart(bin.frequency_hz)}</td>
                  <td>{formatDbPerHz(bin.baseline_density_db_per_hz)}</td>
                  <td>{formatDbPerHz(bin.jammer_density_db_per_hz)}</td>
                  <td>{formatDb(bin.delta_db)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
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
  const { t } = useTranslation();

  return (
    <div className="ai-explanation">
      <div className="ai-explanation-header">
        <h3>{t("ai.title")}</h3>
        <button disabled={loading} type="button" onClick={onExplain}>
          {loading ? t("ai.loading") : t("ai.button")}
        </button>
      </div>
      <p className="helper-text">{t("ai.helper")}</p>
      {error ? <p className="ai-error">{error}</p> : null}
      {explanation ? (
        <div className="ai-result">
          <p>
            <strong>{t("ai.conclusion")}</strong> {comparisonWinnerLabel(explanation, t)}
          </p>
          <p>
            <strong>{t("ai.numericBasis")}</strong> {explanation.numeric_basis}
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
  const { t } = useTranslation();
  const base = baseline.result;
  const next = comparison.result;
  const rows = [
    {
      label: t("metrics.rangeDensity"),
      base: `${formatCompactNumber(base.range_assessment.occupancy_percent)}%`,
      next: `${formatCompactNumber(next.range_assessment.occupancy_percent)}%`,
      delta: `${signed(next.range_assessment.occupancy_percent - base.range_assessment.occupancy_percent)} pp`,
    },
    {
      label: t("comparison.occupiedBandwidth"),
      base: `${formatHz(base.range_assessment.occupied_bandwidth_hz)} Hz`,
      next: `${formatHz(next.range_assessment.occupied_bandwidth_hz)} Hz`,
      delta: `${signed(next.range_assessment.occupied_bandwidth_hz - base.range_assessment.occupied_bandwidth_hz)} Hz`,
    },
    {
      label: t("metrics.meanDensity"),
      base: formatDb(base.summary.mean_density_db_per_hz),
      next: formatDb(next.summary.mean_density_db_per_hz),
      delta: `${signed(next.summary.mean_density_db_per_hz - base.summary.mean_density_db_per_hz)} dB`,
    },
    {
      label: t("metrics.peakDensity"),
      base: formatDb(base.summary.peak_density_db_per_hz),
      next: formatDb(next.summary.peak_density_db_per_hz),
      delta: `${signed(next.summary.peak_density_db_per_hz - base.summary.peak_density_db_per_hz)} dB`,
    },
    {
      label: t("metrics.integratedPower"),
      base: formatDb(base.summary.integrated_power_db),
      next: formatDb(next.summary.integrated_power_db),
      delta: `${signed(next.summary.integrated_power_db - base.summary.integrated_power_db)} dB`,
    },
    {
      label: t("metrics.peakFrequency"),
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
            <th>{t("comparison.metric")}</th>
            <th>{t("comparison.base")}</th>
            <th>{t("comparison.comparison")}</th>
            <th>{t("comparison.delta")}</th>
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
  const { t } = useTranslation();
  const assessment = result.range_assessment;
  return (
    <section className="settings-panel compact">
      <h2>{t("range.title")}</h2>
      <div className="assessment-line">
        <strong>{assessmentLabel(assessment.label, t)}</strong>
        <span>
          {t("range.line", {
            percent: formatCompactNumber(assessment.occupancy_percent),
            threshold: formatCompactNumber(assessment.threshold_offset_db),
          })}
        </span>
      </div>
      <div className="settings-grid">
        <InfoItem
          label={t("range.noiseFloor")}
          value={formatDbPerHz(assessment.noise_floor_db_per_hz)}
        />
        <InfoItem label={t("range.threshold")} value={formatDbPerHz(assessment.threshold_db_per_hz)} />
        <InfoItem
          label={t("range.occupiedBins")}
          value={`${assessment.occupied_bins} / ${result.summary.bin_count}`}
        />
        <InfoItem
          label={t("range.occupiedBandwidth")}
          value={`${formatHz(assessment.occupied_bandwidth_hz)} Hz`}
        />
        <InfoItem
          label={t("range.peakOverFloor")}
          value={`${formatCompactNumber(assessment.peak_to_floor_db)} dB`}
        />
        <InfoItem
          label={t("range.meanExcess")}
          value={`${formatCompactNumber(assessment.mean_excess_db)} dB`}
        />
      </div>
    </section>
  );
}

function DeviceStatusPanel({ status }: { status: DeviceStatusResponse | null }) {
  const { t } = useTranslation();

  if (!status) {
    return (
      <section className="settings-panel">
        <h2>{t("device.title")}</h2>
        <div className="settings-grid">
          <InfoItem label={t("device.status")} value={t("device.waitingBackend")} />
        </div>
      </section>
    );
  }

  const stream = status.stream;
  const currentValues = [
    [t("device.start"), stream?.frequency_from_hz, "Hz"],
    [t("device.end"), stream?.frequency_to_hz, "Hz"],
    [t("device.center"), stream?.center_frequency_hz, "Hz"],
    [t("device.span"), stream?.span_hz, "Hz"],
    [t("device.rbwFromFft"), stream?.rbw_from_fft_size_hz, "Hz"],
    [t("device.sampleFrequency"), stream?.sample_frequency_hz, "Hz"],
    [t("device.samplesPerPacket"), stream?.samples_per_packet, null],
    [t("device.unit"), stream?.unit, null],
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
        <h2>{t("device.title")}</h2>
        <span className={status.reachable ? "ok-chip" : "bad-chip"}>
          {status.reachable
            ? localizeDeviceValue(status.health_state ?? t("device.online"), t)
            : t("device.offline")}
        </span>
      </div>

      <div className="settings-grid">
        <InfoItem
          label={t("device.mission")}
          value={
            typeof status.info.mission === "string"
              ? localizeDeviceValue(status.info.mission, t)
              : status.info.mission ?? t("device.unknown")
          }
        />
        <InfoItem
          label={t("device.input")}
          value={
            status.inputs.length > 0
              ? status.inputs.map((input) => localizeDeviceValue(input, t)).join(", ")
              : t("device.mainInput")
          }
        />
        <InfoItem
          label={t("device.payload")}
          value={stream?.payload ? localizeDeviceValue(stream.payload, t) : t("device.unknown")}
        />
        <InfoItem
          label={t("device.control")}
          value={
            status.endpoints.control
              ? localizeDeviceValue(status.endpoints.control, t)
              : localizeDeviceValue("mock", t)
          }
        />
      </div>

      <h3>{t("device.currentStreamHeader")}</h3>
      <div className="settings-grid">
        {currentValues.map(([label, value, unit]) => (
          <InfoItem key={label} label={label} value={formatMaybeNumber(value, unit, t)} />
        ))}
      </div>

      <h3>{t("device.remoteConfig")}</h3>
      <div className="settings-grid">
        {remoteSettings.map((key) => {
          const setting = status.settings[key];
          return (
            <InfoItem
              key={key}
              label={localizeDeviceLabel(key, setting?.label, t)}
              value={formatSettingValue(setting?.value, setting?.unit, t)}
            />
          );
        })}
      </div>
    </section>
  );
}

function CaptureSettingsPanel({ settings }: { settings: CaptureSettings }) {
  const { t } = useTranslation();

  return (
    <section className="settings-panel compact">
      <h2>{t("capture.title")}</h2>
      <div className="settings-grid">
        <InfoItem label={t("device.start")} value={`${formatHz(settings.frequency_from_hz)} Hz`} />
        <InfoItem label={t("device.end")} value={`${formatHz(settings.frequency_to_hz)} Hz`} />
        <InfoItem label={t("device.center")} value={`${formatHz(settings.center_frequency_hz)} Hz`} />
        <InfoItem label={t("device.span")} value={`${formatHz(settings.span_hz)} Hz`} />
        <InfoItem label={t("capture.rbwBin")} value={`${formatHz(settings.rbw_estimate_hz)} Hz`} />
        <InfoItem label={t("capture.sampleRate")} value={`${formatHz(settings.sample_rate_hz)} Hz`} />
        <InfoItem label={t("form.bins")} value={settings.bins} />
        <InfoItem
          label={t("capture.occupancyThreshold")}
          value={`${settings.occupancy_threshold_db} dB`}
        />
        <InfoItem
          label={t("capture.reference")}
          value={
            settings.reference_level_dbm === null
              ? t("device.notSet")
              : `${settings.reference_level_dbm} dBm`
          }
        />
        <InfoItem
          label={t("form.aaroniaSpan")}
          value={aaroniaSpanLabel(settings.aaronia_span_mode, t)}
        />
      </div>
    </section>
  );
}

function InfoItem({ label, value }: { label: string; value: string | number | boolean | null }) {
  const { t } = useTranslation();
  const displayValue =
    typeof value === "boolean" ? (value ? t("status.yes") : t("status.no")) : String(value ?? t("device.noData"));

  return (
    <div className="info-item">
      <span>{label}</span>
      <strong>{displayValue}</strong>
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

function currentLocale() {
  return i18nInstance.resolvedLanguage === "uk" ? "uk-UA" : "en-US";
}

function formatCompactNumber(value: number) {
  return new Intl.NumberFormat(currentLocale(), {
    maximumFractionDigits: 3,
  }).format(value);
}

function formatScientific(value: number) {
  return new Intl.NumberFormat(currentLocale(), {
    maximumSignificantDigits: 6,
    notation: "scientific",
  }).format(value);
}

function formatHz(value: number) {
  return new Intl.NumberFormat(currentLocale(), {
    maximumFractionDigits: 2,
  }).format(value);
}

function formatFrequencySmart(value: number) {
  const absolute = Math.abs(value);
  if (absolute >= 1_000_000_000) {
    return `${formatCompactNumber(value / 1_000_000_000)} GHz`;
  }
  if (absolute >= 1_000_000) {
    return `${formatCompactNumber(value / 1_000_000)} MHz`;
  }
  if (absolute >= 1_000) {
    return `${formatCompactNumber(value / 1_000)} kHz`;
  }
  return `${formatHz(value)} Hz`;
}

function formatDb(value: number) {
  return `${formatCompactNumber(value)} dB`;
}

function formatDbPerHz(value: number) {
  return `${formatCompactNumber(value)} dB/Hz`;
}

function formatMaybeNumber(
  value: string | number | boolean | null | undefined,
  unit: string | null,
  t: TFunction,
) {
  if (typeof value === "number") {
    return unit === "Hz" ? `${formatHz(value)} Hz` : formatCompactNumber(value);
  }
  if (typeof value === "string") {
    return localizeDeviceValue(value, t);
  }
  return value ?? t("device.noData");
}

function formatSettingValue(
  value: string | number | boolean | null | undefined,
  unit: string | null | undefined,
  t: TFunction,
) {
  if (typeof value === "number" && unit === "Frequency") {
    return `${formatHz(value)} Hz`;
  }
  if (typeof value === "number" && unit) {
    return `${formatCompactNumber(value)} ${unit}`;
  }
  if (typeof value === "string") {
    return localizeDeviceValue(value, t);
  }
  return value ?? t("device.noData");
}

function localizeDeviceLabel(key: string, label: string | undefined, t: TFunction) {
  const directKey = `deviceLabels.${key}`;
  const direct = t(directKey, { defaultValue: "" });
  if (direct) {
    return direct;
  }

  if (!label) {
    return key;
  }

  const normalizedLabel = normalizeDeviceToken(label);
  const labelKey = `deviceLabels.${normalizedLabel}`;
  const translated = t(labelKey, { defaultValue: "" });
  return translated || label;
}

function localizeDeviceValue(value: string, t: TFunction) {
  const normalized = normalizeDeviceToken(value);
  const translated = t(`deviceValues.${normalized}`, { defaultValue: "" });
  if (translated) {
    return translated;
  }

  if (/^\d+\s*ghz$/i.test(value)) {
    return value.replace(/\s*ghz$/i, " GHz");
  }
  if (/^\d+\s*mhz$/i.test(value)) {
    return value.replace(/\s*mhz$/i, " MHz");
  }

  return value;
}

function normalizeDeviceToken(value: string) {
  return value
    .trim()
    .replace(/([a-z])([A-Z])/g, "$1_$2")
    .replace(/[^a-zA-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .toLowerCase();
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
    throw new Error(i18nInstance.t("errors.invalidExport"));
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
  return `${formatDateTime(createdAt)} · ${formatCompactNumber(startMhz)}-${formatCompactNumber(endMhz)} MHz · ${formatCompactNumber(density)}%`;
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
  const formatted = formatCompactNumber(value);
  return value > 0 ? `+${formatted}` : formatted;
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(currentLocale(), {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(value));
}

function parseOptionalNumber(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error("Invalid number");
  }
  return parsed;
}

function assessmentLabel(label: DensityResponse["range_assessment"]["label"], t: TFunction) {
  return t(`assessment.${label}`);
}

function comparisonWinnerLabel(explanation: AIComparisonResponse, t: TFunction) {
  if (explanation.winner === "tie") {
    return t("ai.tie");
  }
  if (explanation.winner === "unclear") {
    return t("ai.unclear");
  }
  return t("ai.denser", { name: explanation.winner_name });
}

function aaroniaSpanLabel(mode: AaroniaSpanMode | undefined, t: TFunction) {
  const safeMode = mode ?? "auto";
  return t(`aaroniaSpan.${safeMode.replace("/", "_")}`);
}

function conductedWinnerLabel(
  winner: ConductedJammerWinner,
  winnerName: string,
  t: TFunction,
) {
  if (winner === "tie") {
    return t("conducted.winnerTie");
  }
  if (winner === "unclear") {
    return t("conducted.winnerUnclear");
  }
  return t("conducted.winnerNamed", { name: winnerName });
}

function conductedMetricRows(result: ConductedJammerComparisonResponse, t: TFunction) {
  const jammerA = result.jammer_a;
  const jammerB = result.jammer_b;
  const valueWinner = (valueA: number, valueB: number, tolerance = 1e-9) =>
    conductedMetricWinner(valueA, valueB, tolerance, t);

  return [
    {
      label: t("conducted.metrics.raisedRange"),
      jammerA: `${formatCompactNumber(jammerA.raised_percent)}%`,
      jammerB: `${formatCompactNumber(jammerB.raised_percent)}%`,
      winner: valueWinner(jammerA.raised_percent, jammerB.raised_percent),
    },
    {
      label: t("conducted.metrics.raisedBandwidth"),
      jammerA: formatFrequencySmart(jammerA.raised_bandwidth_hz),
      jammerB: formatFrequencySmart(jammerB.raised_bandwidth_hz),
      winner: valueWinner(jammerA.raised_bandwidth_hz, jammerB.raised_bandwidth_hz),
    },
    {
      label: t("conducted.metrics.meanDelta"),
      jammerA: formatSignedDb(jammerA.mean_delta_db),
      jammerB: formatSignedDb(jammerB.mean_delta_db),
      winner: valueWinner(jammerA.mean_delta_db, jammerB.mean_delta_db),
    },
    {
      label: t("conducted.metrics.medianDelta"),
      jammerA: formatSignedDb(jammerA.median_delta_db),
      jammerB: formatSignedDb(jammerB.median_delta_db),
      winner: valueWinner(jammerA.median_delta_db, jammerB.median_delta_db),
    },
    {
      label: t("conducted.metrics.p90Delta"),
      jammerA: formatSignedDb(jammerA.p90_delta_db),
      jammerB: formatSignedDb(jammerB.p90_delta_db),
      winner: valueWinner(jammerA.p90_delta_db, jammerB.p90_delta_db),
    },
    {
      label: t("conducted.metrics.maxDelta"),
      jammerA: formatSignedDb(jammerA.max_delta_db),
      jammerB: formatSignedDb(jammerB.max_delta_db),
      winner: valueWinner(jammerA.max_delta_db, jammerB.max_delta_db),
    },
    {
      label: t("conducted.metrics.noiseFloorDelta"),
      jammerA: formatSignedDb(jammerA.noise_floor_delta_db),
      jammerB: formatSignedDb(jammerB.noise_floor_delta_db),
      winner: valueWinner(jammerA.noise_floor_delta_db, jammerB.noise_floor_delta_db),
    },
    {
      label: t("conducted.metrics.integratedPowerDelta"),
      jammerA: formatSignedDb(jammerA.integrated_power_delta_db),
      jammerB: formatSignedDb(jammerB.integrated_power_delta_db),
      winner: valueWinner(jammerA.integrated_power_delta_db, jammerB.integrated_power_delta_db),
    },
    {
      label: t("conducted.metrics.correctedIntegratedPower"),
      jammerA: formatDb(jammerA.corrected_integrated_power_db),
      jammerB: formatDb(jammerB.corrected_integrated_power_db),
      winner: valueWinner(
        jammerA.corrected_integrated_power_db,
        jammerB.corrected_integrated_power_db,
      ),
    },
    {
      label: t("conducted.metrics.peakDeltaFrequency"),
      jammerA:
        jammerA.peak_delta_frequency_hz === null
          ? "-"
          : formatFrequencySmart(jammerA.peak_delta_frequency_hz),
      jammerB:
        jammerB.peak_delta_frequency_hz === null
          ? "-"
          : formatFrequencySmart(jammerB.peak_delta_frequency_hz),
      winner: "-",
    },
  ];
}

function formatSignedDb(value: number) {
  return `${signed(value)} dB`;
}

function conductedMetricWinner(
  valueA: number,
  valueB: number,
  tolerance: number,
  t: TFunction,
) {
  if (Math.abs(valueA - valueB) <= tolerance) {
    return t("conducted.tieShort");
  }
  return valueA > valueB ? t("conducted.shortA") : t("conducted.shortB");
}
