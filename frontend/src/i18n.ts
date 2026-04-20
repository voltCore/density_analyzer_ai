import i18n from "i18next";
import { initReactI18next } from "react-i18next";

const languageStorageKey = "spectrana-language";
const supportedLanguages = ["en", "uk"] as const;

function initialLanguage() {
  if (typeof window === "undefined") {
    return "en";
  }

  const storedLanguage = window.localStorage.getItem(languageStorageKey);
  return supportedLanguages.some((language) => language === storedLanguage) ? storedLanguage! : "en";
}

export function persistLanguage(language: string) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(languageStorageKey, language);
  document.documentElement.lang = language;
}

const resources = {
  en: {
    translation: {
      app: {
        eyebrow: "SPECTRAN V6 IQ",
        title: "Signal density by frequency range",
        source: "Source",
        language: "Language",
        helpOpenLabel: "Open help",
      },
      sourceMode: {
        mock: "mock",
        aaronia: "Aaronia",
      },
      language: {
        english: "English",
        ukrainian: "Ukrainian",
      },
      form: {
        frequencyFrom: "Frequency from, Hz",
        frequencyTo: "Frequency to, Hz",
        bins: "Bins",
        captureSeconds: "IQ time, sec",
        referenceLevel: "Reference level, dBm",
        optional: "optional",
        occupancyThreshold: "Occupancy threshold, dB",
        window: "Window",
        aaroniaSpan: "Aaronia span",
        applyToDevice: "Send settings to Aaronia",
        includeBins: "Return numerical data by bins",
        submit: "Calculate",
        loading: "Calculating...",
        invalidRange: "End frequency must be greater than start frequency, bins >= 16.",
      },
      aaroniaSpan: {
        auto: "Auto cover requested range",
        full: "Full",
        "1_2": "1 / 2",
        "1_4": "1 / 4",
        "1_8": "1 / 8",
        "1_16": "1 / 16",
        "1_32": "1 / 32",
        "1_64": "1 / 64",
        "1_128": "1 / 128",
        "1_256": "1 / 256",
        "1_512": "1 / 512",
      },
      errors: {
        backendUnavailable: "Backend is unavailable",
        dataFetchFailed: "Failed to get data",
        readDbFailed: "Failed to read the database.",
        readSnapshotFailed: "Failed to read the snapshot.",
        saveSnapshotFailed: "Failed to save the snapshot.",
        deleteSnapshotFailed: "Failed to delete the snapshot.",
        importFailed: "Failed to import JSON.",
        aiUnavailable: "AI explanation is unavailable.",
        invalidExport: "JSON does not look like a Spectrana Density export.",
      },
      notices: {
        savedSnapshot: "Snapshot saved to the database for comparison.",
        importedSnapshot: "JSON snapshot imported to the database for comparison.",
      },
      status: {
        deviceConfigured: "Device configured",
        yes: "yes",
        no: "no",
        packets: "Packets",
        readyTitle: "Ready to calculate.",
        readyText: "Enter the frequency range and bin count.",
        density: "Density",
        power: "power",
        samples: "samples",
      },
      metrics: {
        rangeDensity: "Range density",
        assessment: "Assessment",
        meanDensity: "Mean density",
        peakDensity: "Peak density",
        peakFrequency: "Peak frequency",
        integratedPower: "Integrated power",
        binWidth: "Bin width",
      },
      exportPanel: {
        title: "Export and storage",
        snapshotName: "Snapshot name",
        placeholder: "for example: antenna A, 745 MHz, before filter",
        save: "Save snapshot",
        exportJson: "Export JSON",
        exportCsv: "Export CSV",
        importJson: "Import JSON",
        helper:
          "JSON stores the full result. CSV contains summary, range assessment, and bins for table comparison.",
        noBins:
          "This result has no bin rows. Enable \"Return numerical data by bins\" before the next calculation if bin-level CSV is needed.",
      },
      comparison: {
        title: "Snapshot comparison",
        empty: "Save the first snapshot to the database after calculation.",
        baseline: "Baseline",
        compareWith: "Compare with",
        chooseSnapshot: "choose snapshot",
        selectTwo: "Choose two snapshots for numerical comparison.",
        delete: "Delete",
        density: "density",
        bins: "bins",
        metric: "Metric",
        base: "Baseline",
        comparison: "Comparison",
        delta: "Delta",
        occupiedBandwidth: "Occupied bandwidth",
      },
      conducted: {
        title: "Conducted Jammer Comparison",
        safetyTitle: "Conducted RF safety",
        safetyLine1: "Use only with conducted setup through sufficient attenuation.",
        safetyLine2: "Do not connect RF output directly to Aaronia.",
        safetyLine3:
          "Check Aaronia max input power and attenuator power rating before measurement.",
        baseline: "Baseline snapshot",
        jammerA: "Jammer A snapshot",
        jammerB: "Jammer B snapshot",
        thresholdDb: "Threshold, dB",
        attenuationDb: "Attenuation, dB",
        targetFrom: "Target frequency from, Hz",
        targetTo: "Target frequency to, Hz",
        topBins: "Top raised bins",
        overlapPlaceholder: "shared overlap",
        analyze: "Analyze conducted comparison",
        analyzing: "Analyzing...",
        selectThree: "Choose baseline, Jammer A, and Jammer B snapshots.",
        invalidNumber: "Target frequency values must be positive numbers or empty.",
        invalidTargetRange: "Target frequency end must be greater than start.",
        analysisFailed: "Failed to analyze conducted comparison.",
        winner: "Winner:",
        winnerNamed: "{{name}}",
        winnerTie: "Tie",
        winnerUnclear: "Unclear",
        analysisQuality: "Analysis quality:",
        comparedRange: "Compared range:",
        warnings: "Warnings",
        metricWinner: "Winner",
        shortA: "A",
        shortB: "B",
        tieShort: "Tie",
        topRaisedFor: "Top raised bins: {{name}}",
        noRaisedBins: "No bins exceeded the configured threshold.",
        baselineDensity: "Baseline density",
        jammerDensity: "Jammer density",
        deltaDb: "Delta",
        quality: {
          direct: "direct",
          caution: "caution",
          incompatible: "incompatible",
        },
        metrics: {
          raisedRange: "Raised range",
          raisedBandwidth: "Raised bandwidth",
          meanDelta: "Mean delta over baseline",
          medianDelta: "Median delta",
          p90Delta: "P90 delta",
          maxDelta: "Max delta",
          noiseFloorDelta: "Noise floor delta",
          integratedPowerDelta: "Integrated power delta",
          correctedIntegratedPower: "Corrected integrated power",
          peakDeltaFrequency: "Peak delta frequency",
        },
      },
      ai: {
        title: "AI explanation",
        button: "Explain with AI",
        loading: "AI is analyzing...",
        helper: "Requires a backend API key and internet connection.",
        conclusion: "Conclusion:",
        numericBasis: "Numeric basis:",
        tie: "signals are approximately equal by density",
        unclear: "not enough data for a precise conclusion",
        denser: "{{name}} is denser",
      },
      range: {
        title: "Range density assessment",
        line:
          "{{percent}}% of the range is above the noise floor by {{threshold}} dB",
        noiseFloor: "PSD noise floor",
        threshold: "PSD threshold",
        occupiedBins: "Occupied bins",
        occupiedBandwidth: "Occupied bandwidth",
        peakOverFloor: "Peak over floor",
        meanExcess: "Mean excess",
      },
      device: {
        title: "Aaronia settings",
        status: "Status",
        waitingBackend: "waiting for backend",
        currentStreamHeader: "Current stream header",
        remoteConfig: "Remote config",
        online: "online",
        offline: "offline",
        unknown: "unknown",
        noData: "no data",
        notSet: "not set",
        mainInput: "main",
        start: "Start",
        end: "End",
        center: "Center",
        span: "Span",
        rbwFromFft: "RBW from FFT size",
        sampleFrequency: "Sample frequency",
        samplesPerPacket: "Samples/packet",
        unit: "Unit",
        mission: "Mission",
        input: "Input",
        payload: "Payload",
        control: "Control",
      },
      deviceLabels: {
        center_frequency: "Center frequency",
        center_frequency_hz: "Center frequency",
        span: "Span",
        reference_level: "Reference level",
        reference_level_dbm: "Reference level",
        ft_size: "FFT size",
        fft_size: "FFT size",
        fft_size_mode: "FFT size mode",
        fft_window: "FFT window",
        receiver_clock: "Receiver clock",
        frequency_range: "Frequency range",
      },
      deviceValues: {
        warning: "warning",
        error: "error",
        ok: "ok",
        main: "main",
        iq: "IQ",
        volt: "volt",
        full: "Full",
        fft: "FFT",
        hamming: "Hamming",
        mock: "mock",
        aaronia: "Aaronia",
      },
      capture: {
        title: "Settings for this calculation",
        rbwBin: "RBW / bin",
        sampleRate: "Sample rate",
        occupancyThreshold: "Occupancy threshold",
        reference: "Reference",
      },
      table: {
        frequencyHz: "Frequency, Hz",
        density: "Density",
        densityDbHz: "Density, dB/Hz",
        power: "Power",
        powerDb: "Power, dB",
      },
      assessment: {
        quiet: "quiet",
        sparse: "sparse",
        moderate: "moderate",
        dense: "dense",
      },
      help: {
        eyebrow: "Help",
        title: "What the project measures",
        close: "Close",
        intro: [
          "Spectrana Density measures how signal energy is distributed inside the selected frequency range. The backend takes IQ data, splits the range into bins, runs FFT, and calculates power spectral density for each frequency cell.",
          "The main practical result is Range density: what part of the range has density above the local noise floor by the configured threshold. Without calibration of the full RF chain, these numbers should be read as stable values for comparing measurements, not as absolute dBm/Hz.",
        ],
        sections: [
          {
            title: "Calculation fields",
            items: [
              {
                term: "Frequency from, Hz",
                description:
                  "Start of the frequency range. The backend begins capture and density calculation from this frequency.",
              },
              {
                term: "Frequency to, Hz",
                description:
                  "End of the range. The difference between end and start frequency forms the measurement span.",
              },
              {
                term: "Bins",
                description:
                  "Number of frequency grid cells. Each bin represents a small part of the range for which density and power are calculated.",
              },
              {
                term: "IQ time, sec",
                description:
                  "How many seconds of IQ data to capture. A longer time gives more samples and a more stable estimate, but calculation takes longer.",
              },
              {
                term: "Reference level, dBm",
                description:
                  "Optional reference level for the Aaronia receiver. It helps the device choose the correct signal chain level, but it does not turn the result into calibrated dBm/Hz without full chain calibration.",
              },
              {
                term: "Occupancy threshold, dB",
                description:
                  "How many dB above the noise floor a bin must be to count as occupied by signal.",
              },
              {
                term: "Window",
                description:
                  "FFT window. Hann reduces spectral leakage between neighboring bins; Rectangular keeps the raw window without smoothing.",
              },
              {
                term: "Send settings to Aaronia",
                description:
                  "When enabled, the backend sends range, center, span, bins, and reference level to the device before calculation.",
              },
              {
                term: "Return numerical data by bins",
                description:
                  "When enabled, the response contains a row for each frequency cell. This is needed for the table, CSV, and detailed analysis.",
              },
            ],
          },
          {
            title: "Main metrics",
            items: [
              {
                term: "Range density",
                description:
                  "Percentage of the range where bins exceeded the occupancy threshold. This is the main indicator of how filled the range is by signal.",
              },
              {
                term: "Assessment",
                description:
                  "Text assessment of Range density: quiet, sparse, moderate, or dense. It shows the range state quickly without reading all numbers.",
              },
              {
                term: "Mean density",
                description:
                  "Average power spectral density across the full range. Useful for comparing overall noise or signal level between measurements.",
              },
              {
                term: "Peak density",
                description:
                  "Highest spectral density among all bins. Shows the strongest part of the selected range.",
              },
              {
                term: "Peak frequency",
                description:
                  "Frequency of the bin where Peak density was found. Helps locate the strongest signal.",
              },
              {
                term: "Integrated power",
                description:
                  "Total power across the range: density is multiplied by bin width and summed. This is total energy in the selected span.",
              },
              {
                term: "Bin width",
                description:
                  "Width of one frequency cell: span divided by bins. Smaller width gives a more detailed grid.",
              },
            ],
          },
          {
            title: "Range density assessment",
            items: [
              {
                term: "PSD noise floor",
                description:
                  "Local baseline noise density in dB/Hz, taken as median PSD across bins. It is not the same unit as the analyzer noise floor in dBm.",
              },
              {
                term: "PSD threshold",
                description:
                  "PSD noise floor plus Occupancy threshold. Bins above this dB/Hz level are treated as occupied.",
              },
              {
                term: "Occupied bins",
                description:
                  "How many bins exceeded Threshold. For example, 300 / 1024 means that 300 frequency cells were occupied.",
              },
              {
                term: "Occupied bandwidth",
                description:
                  "Estimated occupied bandwidth: Occupied bins multiplied by Bin width.",
              },
              {
                term: "Peak over floor",
                description:
                  "How much the strongest bin is above the noise floor. A large value means a clear signal peak.",
              },
              {
                term: "Mean excess",
                description:
                  "Average excess of occupied bins over Threshold. Shows how confidently occupied cells exceed the threshold.",
              },
            ],
          },
          {
            title: "Bin table cells",
            items: [
              {
                term: "#",
                description:
                  "Sequential bin number in the frequency grid. This is a cell index, not a frequency.",
              },
              {
                term: "Frequency, Hz",
                description:
                  "Center frequency of a specific bin. It shows where this value is located in the spectrum.",
              },
              {
                term: "Density",
                description:
                  "Linear power spectral density value for the bin. If IQ uses unit=volt, the unit is V^2/Hz; otherwise it is normalized unit^2/Hz.",
              },
              {
                term: "Density, dB/Hz",
                description:
                  "The same Density value on a logarithmic dB scale. This makes weak and strong signals easier to compare.",
              },
              {
                term: "Power",
                description:
                  "Power in a specific bin: Density multiplied by bin width.",
              },
              {
                term: "Power, dB",
                description:
                  "Power on a dB scale. Useful for comparing individual frequency cells.",
              },
            ],
          },
          {
            title: "Aaronia settings and stream",
            items: [
              {
                term: "Start / End",
                description:
                  "Current range boundaries that the backend sees in the stream header or sends to the device.",
              },
              {
                term: "Center / Span",
                description:
                  "Center frequency and full range width. For the device, this is another way to describe the same Start / End boundaries.",
              },
              {
                term: "RBW from FFT size / RBW / bin",
                description:
                  "Frequency resolution estimate. In this project it corresponds to the width of one FFT cell.",
              },
              {
                term: "Sample frequency / Sample rate",
                description:
                  "IQ stream sampling frequency. It defines how many IQ samples arrive per second.",
              },
              {
                term: "Samples/packet",
                description:
                  "How many IQ samples arrive in one stream packet. This is auxiliary stream diagnostics.",
              },
              {
                term: "Payload / Unit",
                description:
                  "Payload describes the IQ data format; Unit shows the sample unit. Unit is important for the Density label.",
              },
              {
                term: "Remote config",
                description:
                  "Current configuration values read from the RTSA remote API: reference level, FFT size, window, clock, and other parameters.",
              },
            ],
          },
          {
            title: "Export, snapshot, and comparison",
            items: [
              {
                term: "Snapshot",
                description:
                  "Saved measurement with summary, range assessment, bins, and device status. A snapshot is used for later analysis and comparison.",
              },
              {
                term: "Baseline",
                description:
                  "Measurement used as the comparison starting point. Delta values are calculated from it.",
              },
              {
                term: "Compare with",
                description:
                  "Second measurement. Its values are compared against the baseline to see what became denser, weaker, or shifted in frequency.",
              },
              {
                term: "Delta",
                description:
                  "Difference between the second measurement and the baseline. A positive number means the value is higher in the second snapshot.",
              },
              {
                term: "Export JSON",
                description:
                  "Full measurement export. It can be imported back into the app without losing details.",
              },
              {
                term: "Export CSV",
                description:
                  "Table export for Excel, LibreOffice, or Python. It contains summary, range assessment, and bin rows when bins were returned.",
              },
              {
                term: "How to make a CSV file",
                description:
                  "CSV must be UTF-8 plain text with commas as separators. The first row is the header: record_type, name, value, unit, index, frequency_hz, density_linear, density_db_per_hz, power_linear, power_db. For summary rows, use record_type capture, range, or summary and fill name, value, unit. For frequency cells, use record_type bin and fill index, frequency_hz, density_linear, density_db_per_hz, power_linear, power_db.",
              },
              {
                term: "CSV and import",
                description:
                  "In this interface, Import JSON accepts a full JSON snapshot because only JSON preserves all comparison data. Use CSV as a table file for analysis or data sharing; to bring a measurement back into the app, export and import JSON.",
              },
              {
                term: "AI explanation",
                description:
                  "Optional text conclusion for two snapshots. It does not replace the numeric table; it explains it in plain language.",
              },
            ],
          },
        ],
      },
    },
  },
  uk: {
    translation: {
      app: {
        eyebrow: "SPECTRAN V6 IQ",
        title: "Щільність сигналу за діапазоном",
        source: "Джерело",
        language: "Мова",
        helpOpenLabel: "Відкрити довідку",
      },
      sourceMode: {
        mock: "імітація",
        aaronia: "Aaronia",
      },
      language: {
        english: "Англійська",
        ukrainian: "Українська",
      },
      form: {
        frequencyFrom: "Частота з, Hz",
        frequencyTo: "Частота по, Hz",
        bins: "Кількість клітинок",
        captureSeconds: "Час IQ, sec",
        referenceLevel: "Рівень опори, dBm",
        optional: "опційно",
        occupancyThreshold: "Поріг зайнятості, dB",
        window: "Вікно",
        aaroniaSpan: "Aaronia span",
        applyToDevice: "Передавати налаштування на Aaronia",
        includeBins: "Повернути числові дані по клітинках",
        submit: "Розрахувати",
        loading: "Рахую...",
        invalidRange: "Кінцева частота має бути більшою за початкову, клітинок >= 16.",
      },
      aaroniaSpan: {
        auto: "Авто, покрити заданий діапазон",
        full: "Full",
        "1_2": "1 / 2",
        "1_4": "1 / 4",
        "1_8": "1 / 8",
        "1_16": "1 / 16",
        "1_32": "1 / 32",
        "1_64": "1 / 64",
        "1_128": "1 / 128",
        "1_256": "1 / 256",
        "1_512": "1 / 512",
      },
      errors: {
        backendUnavailable: "Бекенд недоступний",
        dataFetchFailed: "Не вдалося отримати дані",
        readDbFailed: "Не вдалося прочитати БД.",
        readSnapshotFailed: "Не вдалося прочитати знімок.",
        saveSnapshotFailed: "Не вдалося зберегти знімок.",
        deleteSnapshotFailed: "Не вдалося видалити знімок.",
        importFailed: "Не вдалося імпортувати JSON.",
        aiUnavailable: "Пояснення ШІ недоступне.",
        invalidExport: "JSON не схожий на експорт Spectrana Density.",
      },
      notices: {
        savedSnapshot: "Знімок збережено в БД для порівняння.",
        importedSnapshot: "JSON-знімок імпортовано в БД для порівняння.",
      },
      status: {
        deviceConfigured: "Пристрій налаштовано",
        yes: "так",
        no: "ні",
        packets: "Пакети",
        readyTitle: "Готово до розрахунку.",
        readyText: "Введіть діапазон частот і кількість клітинок.",
        density: "Щільність",
        power: "потужність",
        samples: "семпли",
      },
      metrics: {
        rangeDensity: "Щільність діапазону",
        assessment: "Оцінка",
        meanDensity: "Середня щільність",
        peakDensity: "Пікова щільність",
        peakFrequency: "Пікова частота",
        integratedPower: "Інтегральна потужність",
        binWidth: "Ширина клітинки",
      },
      exportPanel: {
        title: "Експорт і збереження",
        snapshotName: "Назва знімка",
        placeholder: "наприклад: antenna A, 745 MHz, before filter",
        save: "Зберегти знімок",
        exportJson: "Експорт JSON",
        exportCsv: "Експорт CSV",
        importJson: "Імпорт JSON",
        helper:
          "JSON зберігає повний результат. CSV містить підсумок, оцінку діапазону і клітинки для табличного порівняння.",
        noBins:
          "У цьому результаті немає рядків по клітинках. Увімкніть \"Повернути числові дані по клітинках\" перед наступним розрахунком, якщо потрібен детальний CSV.",
      },
      comparison: {
        title: "Порівняння знімків",
        empty: "Збережіть перший знімок у БД після розрахунку.",
        baseline: "База",
        compareWith: "Порівняти з",
        chooseSnapshot: "оберіть знімок",
        selectTwo: "Оберіть два знімки для числового порівняння.",
        delete: "Видалити",
        density: "щільність",
        bins: "клітинки",
        metric: "Метрика",
        base: "База",
        comparison: "Порівняння",
        delta: "Різниця",
        occupiedBandwidth: "Зайнята смуга",
      },
      conducted: {
        title: "Conducted Jammer Comparison",
        safetyTitle: "Безпека conducted RF",
        safetyLine1: "Використовуйте тільки кабельний тракт із достатнім затуханням.",
        safetyLine2: "Не підключайте RF-вихід напряму до Aaronia.",
        safetyLine3:
          "Перед виміром перевірте максимальну вхідну потужність Aaronia і потужність атенюатора.",
        baseline: "Baseline-знімок",
        jammerA: "Jammer A знімок",
        jammerB: "Jammer B знімок",
        thresholdDb: "Поріг, dB",
        attenuationDb: "Затухання, dB",
        targetFrom: "Цільова частота з, Hz",
        targetTo: "Цільова частота по, Hz",
        topBins: "Top raised bins",
        overlapPlaceholder: "спільний overlap",
        analyze: "Проаналізувати conducted-порівняння",
        analyzing: "Аналізую...",
        selectThree: "Оберіть baseline, Jammer A і Jammer B знімки.",
        invalidNumber: "Цільові частоти мають бути додатними числами або порожніми.",
        invalidTargetRange: "Кінцева цільова частота має бути більшою за початкову.",
        analysisFailed: "Не вдалося виконати conducted-порівняння.",
        winner: "Переможець:",
        winnerNamed: "{{name}}",
        winnerTie: "Нічия",
        winnerUnclear: "Невизначено",
        analysisQuality: "Якість аналізу:",
        comparedRange: "Порівнюваний діапазон:",
        warnings: "Попередження",
        metricWinner: "Переможець",
        shortA: "A",
        shortB: "B",
        tieShort: "Нічия",
        topRaisedFor: "Top raised bins: {{name}}",
        noRaisedBins: "Жодна клітинка не перевищила заданий поріг.",
        baselineDensity: "Baseline щільність",
        jammerDensity: "Jammer щільність",
        deltaDb: "Різниця",
        quality: {
          direct: "прямий",
          caution: "з застереженнями",
          incompatible: "несумісний",
        },
        metrics: {
          raisedRange: "Піднятий діапазон",
          raisedBandwidth: "Піднята смуга",
          meanDelta: "Середня різниця над baseline",
          medianDelta: "Медіанна різниця",
          p90Delta: "P90 різниця",
          maxDelta: "Максимальна різниця",
          noiseFloorDelta: "Різниця рівня шуму",
          integratedPowerDelta: "Різниця інтегральної потужності",
          correctedIntegratedPower: "Інтегральна потужність з поправкою",
          peakDeltaFrequency: "Частота пікової різниці",
        },
      },
      ai: {
        title: "Пояснення ШІ",
        button: "Пояснити через ШІ",
        loading: "ШІ аналізує...",
        helper: "Потрібен ключ API на бекенді та інтернет-з'єднання.",
        conclusion: "Висновок:",
        numericBasis: "Числова база:",
        tie: "сигнали приблизно однакові за щільністю",
        unclear: "недостатньо даних для точного висновку",
        denser: "{{name}} щільніший",
      },
      range: {
        title: "Оцінка щільності діапазону",
        line:
          "{{percent}}% діапазону вище рівня шуму на {{threshold}} dB",
        noiseFloor: "PSD рівень шуму",
        threshold: "PSD поріг",
        occupiedBins: "Зайняті клітинки",
        occupiedBandwidth: "Зайнята смуга",
        peakOverFloor: "Пік над шумом",
        meanExcess: "Середнє перевищення",
      },
      device: {
        title: "Налаштування Aaronia",
        status: "Статус",
        waitingBackend: "чекаю бекенд",
        currentStreamHeader: "Поточний заголовок потоку",
        remoteConfig: "Віддалена конфігурація",
        online: "онлайн",
        offline: "офлайн",
        unknown: "невідомо",
        noData: "немає даних",
        notSet: "не задано",
        mainInput: "основний",
        start: "Початок",
        end: "Кінець",
        center: "Центр",
        span: "Смуга",
        rbwFromFft: "RBW за розміром FFT",
        sampleFrequency: "Частота семплювання",
        samplesPerPacket: "Семплів/пакет",
        unit: "Одиниця",
        mission: "Місія",
        input: "Вхід",
        payload: "Дані",
        control: "Керування",
      },
      deviceLabels: {
        center_frequency: "Центральна частота",
        center_frequency_hz: "Центральна частота",
        span: "Смуга",
        reference_level: "Рівень опори",
        reference_level_dbm: "Рівень опори",
        ft_size: "Розмір FFT",
        fft_size: "Розмір FFT",
        fft_size_mode: "Режим розміру FFT",
        fft_window: "Вікно FFT",
        receiver_clock: "Тактування приймача",
        frequency_range: "Частотний діапазон",
      },
      deviceValues: {
        warning: "попередження",
        error: "помилка",
        ok: "норма",
        main: "основний",
        iq: "IQ",
        volt: "вольт",
        full: "повний",
        fft: "FFT",
        hamming: "Hamming",
        mock: "імітація",
        aaronia: "Aaronia",
      },
      capture: {
        title: "Налаштування цього розрахунку",
        rbwBin: "RBW / клітинка",
        sampleRate: "Частота семплювання",
        occupancyThreshold: "Поріг зайнятості",
        reference: "Рівень опори",
      },
      table: {
        frequencyHz: "Частота, Hz",
        density: "Щільність",
        densityDbHz: "Щільність, dB/Hz",
        power: "Потужність",
        powerDb: "Потужність, dB",
      },
      assessment: {
        quiet: "тихий",
        sparse: "рідкий",
        moderate: "помірний",
        dense: "щільний",
      },
      help: {
        eyebrow: "Довідка",
        title: "Що вимірює проєкт",
        close: "Закрити",
        intro: [
          "Spectrana Density вимірює, як енергія сигналу розподілена всередині обраного частотного діапазону. Бекенд бере IQ-дані, розбиває діапазон на клітинки, рахує FFT і спектральну щільність потужності для кожної частотної клітинки.",
          "Головний практичний результат - щільність діапазону: яка частина діапазону має щільність вище локального рівня шуму на заданий поріг. Без калібрування всього тракту ці числа слід читати як стабільну оцінку для порівняння вимірів, а не як абсолютний dBm/Hz.",
        ],
        sections: [
          {
            title: "Поля розрахунку",
            items: [
              {
                term: "Частота з, Hz",
                description:
                  "Початок частотного діапазону. Звідси бекенд починає збір і розрахунок щільності сигналу.",
              },
              {
                term: "Частота по, Hz",
                description:
                  "Кінець діапазону. Різниця між кінцевою та початковою частотою утворює смугу виміру.",
              },
              {
                term: "Клітинки",
                description:
                  "Кількість клітинок частотної сітки. Кожна клітинка відповідає маленькій частині діапазону, для якої рахується щільність і потужність.",
              },
              {
                term: "Час IQ, sec",
                description:
                  "Скільки секунд збирати IQ-дані. Більший час дає більше семплів і стабільнішу оцінку, але розрахунок триває довше.",
              },
              {
                term: "Рівень опори, dBm",
                description:
                  "Опційний рівень опори для приймача Aaronia. Він допомагає приладу вибрати коректний рівень тракту, але не перетворює результат у калібрований dBm/Hz без калібрування всього тракту.",
              },
              {
                term: "Поріг зайнятості, dB",
                description:
                  "На скільки dB щільність у клітинці має бути вищою за рівень шуму, щоб ця клітинка вважалася зайнятою сигналом.",
              },
              {
                term: "Вікно",
                description:
                  "Вікно FFT. Hann зменшує витік спектра між сусідніми клітинками, Rectangular залишає сире вікно без згладжування.",
              },
              {
                term: "Передавати налаштування на Aaronia",
                description:
                  "Коли увімкнено, бекенд перед розрахунком відправляє діапазон, центр, смугу, кількість клітинок і рівень опори на прилад.",
              },
              {
                term: "Повернути числові дані по клітинках",
                description:
                  "Коли увімкнено, відповідь містить рядок для кожної клітинки частоти. Це потрібно для таблиці, CSV і детального аналізу.",
              },
            ],
          },
          {
            title: "Головні показники",
            items: [
              {
                term: "Щільність діапазону",
                description:
                  "Відсоток діапазону, де клітинки перевищили поріг зайнятості. Це головний індикатор, наскільки діапазон заповнений сигналом.",
              },
              {
                term: "Оцінка",
                description:
                  "Словесна оцінка щільності діапазону: тихий, рідкий, помірний або щільний. Вона швидко показує стан діапазону без читання всіх чисел.",
              },
              {
                term: "Середня щільність",
                description:
                  "Середня спектральна щільність потужності по всьому діапазону. Корисна для порівняння загального рівня шуму або сигналу між вимірами.",
              },
              {
                term: "Пікова щільність",
                description:
                  "Найвища спектральна щільність серед усіх клітинок. Показує найсильнішу ділянку в обраному діапазоні.",
              },
              {
                term: "Пікова частота",
                description:
                  "Частота клітинки, де знайдено пікову щільність. Допомагає швидко знайти, де саме знаходиться найсильніший сигнал.",
              },
              {
                term: "Інтегральна потужність",
                description:
                  "Сумарна потужність по всьому діапазону: щільність множиться на ширину клітинки і підсумовується. Це загальна енергія в обраній смузі.",
              },
              {
                term: "Ширина клітинки",
                description:
                  "Ширина однієї частотної клітинки: смуга поділена на кількість клітинок. Менша ширина дає детальнішу сітку.",
              },
            ],
          },
          {
            title: "Оцінка щільності діапазону",
            items: [
              {
                term: "PSD рівень шуму",
                description:
                  "Локальна базова щільність шуму в dB/Hz, взята як медіана PSD по клітинках. Це не та сама одиниця, що noise floor аналізатора в dBm.",
              },
              {
                term: "PSD поріг",
                description:
                  "PSD рівень шуму плюс поріг зайнятості. Клітинки вище цього рівня dB/Hz вважаються зайнятими.",
              },
              {
                term: "Зайняті клітинки",
                description:
                  "Скільки клітинок перевищили поріг. Наприклад, 300 / 1024 означає, що 300 клітинок частоти були зайняті.",
              },
              {
                term: "Зайнята смуга",
                description:
                  "Оцінена ширина зайнятої смуги: зайняті клітинки множаться на ширину клітинки.",
              },
              {
                term: "Пік над шумом",
                description:
                  "Наскільки найсильніша клітинка вища за рівень шуму. Велике значення означає виразний пік сигналу.",
              },
              {
                term: "Середнє перевищення",
                description:
                  "Середнє перевищення зайнятих клітинок над порогом. Показує, наскільки впевнено зайняті клітинки виходять за поріг.",
              },
            ],
          },
          {
            title: "Клітинки таблиці",
            items: [
              {
                term: "#",
                description:
                  "Порядковий номер клітинки у частотній сітці. Це індекс клітинки, а не частота.",
              },
              {
                term: "Частота, Hz",
                description:
                  "Центральна частота конкретної клітинки. За нею можна знайти, де саме в спектрі лежить значення.",
              },
              {
                term: "Щільність",
                description:
                  "Лінійне значення спектральної щільності потужності для клітинки. Якщо IQ має одиницю volt, одиниця буде V^2/Hz; інакше normalized unit^2/Hz.",
              },
              {
                term: "Щільність, dB/Hz",
                description:
                  "Те саме значення щільності у логарифмічній dB-шкалі. Так легше порівнювати слабкі й сильні сигнали.",
              },
              {
                term: "Потужність",
                description:
                  "Потужність у конкретній клітинці: щільність множиться на ширину клітинки.",
              },
              {
                term: "Потужність, dB",
                description:
                  "Потужність у dB-шкалі. Це зручно для порівняння окремих частотних клітинок.",
              },
            ],
          },
          {
            title: "Налаштування Aaronia і потік",
            items: [
              {
                term: "Початок / Кінець",
                description:
                  "Поточні межі діапазону, які бекенд бачить у заголовку потоку або відправляє на прилад.",
              },
              {
                term: "Центр / Смуга",
                description:
                  "Центральна частота і повна ширина діапазону. Для приладу це альтернативний спосіб задати ті самі межі початку й кінця.",
              },
              {
                term: "RBW за розміром FFT / RBW / клітинка",
                description:
                  "Оцінка частотної роздільної здатності. У цьому проєкті вона відповідає ширині однієї FFT-клітинки.",
              },
              {
                term: "Частота семплювання",
                description:
                  "Частота дискретизації IQ-потоку. Вона визначає, скільки IQ-семплів приходить за секунду.",
              },
              {
                term: "Семплів/пакет",
                description:
                  "Скільки IQ-семплів приходить в одному пакеті потоку. Це допоміжна діагностика потоку.",
              },
              {
                term: "Дані / Одиниця",
                description:
                  "Дані описують формат IQ-потоку, одиниця показує одиницю семплів. Одиниця важлива для правильного підпису щільності.",
              },
              {
                term: "Віддалена конфігурація",
                description:
                  "Поточні значення конфігурації, які бекенд читає з віддаленого API RTSA: рівень опори, розмір FFT, вікно, тактування та інші параметри.",
              },
            ],
          },
          {
            title: "Експорт, знімок і порівняння",
            items: [
              {
                term: "Знімок",
                description:
                  "Збережений вимір із підсумком, оцінкою діапазону, клітинками і статусом приладу. Знімок потрібен для повторного аналізу та порівняння.",
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
                term: "Різниця",
                description:
                  "Різниця між другим виміром і базою. Додатне число означає, що показник у другому знімку більший.",
              },
              {
                term: "Експорт JSON",
                description:
                  "Повний експорт виміру. Його можна імпортувати назад у застосунок без втрати деталей.",
              },
              {
                term: "Експорт CSV",
                description:
                  "Табличний експорт для Excel, LibreOffice або Python. Містить підсумок, оцінку діапазону і рядки по клітинках, якщо клітинки були повернуті.",
              },
              {
                term: "Як зробити CSV файл",
                description:
                  "CSV має бути простим текстом у кодуванні UTF-8 з комою як роздільником. Перший рядок - назви колонок: record_type, name, value, unit, index, frequency_hz, density_linear, density_db_per_hz, power_linear, power_db. Для підсумкових рядків ставте record_type capture, range або summary і заповнюйте name, value, unit. Для частотних клітинок ставте record_type bin і заповнюйте index, frequency_hz, density_linear, density_db_per_hz, power_linear, power_db.",
              },
              {
                term: "CSV і імпорт",
                description:
                  "У цьому інтерфейсі кнопка Імпорт JSON приймає повний JSON-знімок, бо тільки JSON зберігає всі дані для порівняння без втрат. CSV використовуйте як табличний файл для аналізу або передачі чисел; щоб повернути вимір назад у застосунок, експортуйте й імпортуйте JSON.",
              },
              {
                term: "Пояснення ШІ",
                description:
                  "Опційний текстовий висновок по двох знімках. Він не замінює числову таблицю, а пояснює її людською мовою.",
              },
            ],
          },
        ],
      },
    },
  },
};

void i18n.use(initReactI18next).init({
  resources,
  lng: initialLanguage(),
  fallbackLng: "en",
  interpolation: {
    escapeValue: false,
  },
});

persistLanguage(i18n.language);

export default i18n;
