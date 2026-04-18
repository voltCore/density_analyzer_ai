# ruff: noqa: RUF001

from __future__ import annotations

import json
from heapq import nlargest
from typing import Any

import httpx

from spectrana_density.config import Settings
from spectrana_density.schemas import AIComparisonRequest, AIComparisonResponse, DensityResponse

LanguageCode = str


class AIComparisonUnavailableError(RuntimeError):
    """Raised when the remote AI explanation cannot be generated."""


async def explain_signal_comparison(
    payload: AIComparisonRequest,
    settings: Settings,
) -> AIComparisonResponse:
    api_key = (settings.ai_api_key or "").strip()
    if not api_key:
        raise AIComparisonUnavailableError(
            _localized_message(payload.response_language, "missing_api_key")
        )

    context = build_comparison_context(payload)
    language = payload.response_language
    request_body = {
        "model": settings.ai_model,
        "messages": [
            {
                "role": "system",
                "content": _system_prompt(language),
            },
            {
                "role": "user",
                "content": _user_prompt(language, context),
            },
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
            response = await client.post(
                f"{settings.ai_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=request_body,
            )
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise AIComparisonUnavailableError(
            _localized_message(language, "timeout")
        ) from exc
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        api_detail = _extract_error_message(exc.response)
        if api_detail:
            detail = api_detail
        elif status_code in {401, 403}:
            detail = _localized_message(language, "auth_detail")
        elif status_code == 404:
            detail = _localized_message(language, "not_found_detail")
        elif status_code == 429:
            detail = _localized_message(language, "rate_limit_detail")
        else:
            detail = _localized_message(language, "generic_http_detail")
        raise AIComparisonUnavailableError(
            _localized_message(language, "http_error", status_code=status_code, detail=detail)
        ) from exc
    except httpx.TransportError as exc:
        raise AIComparisonUnavailableError(
            _localized_message(language, "transport")
        ) from exc

    content = _extract_chat_message(response.json())
    if not content:
        raise AIComparisonUnavailableError(_localized_message(language, "empty_response"))

    return AIComparisonResponse(
        provider="openai-compatible-chat",
        model=settings.ai_model,
        winner=context["local_assessment"]["winner"],
        winner_name=context["local_assessment"]["winner_name"],
        comparison_quality=context["comparison_quality"],
        numeric_basis=context["local_assessment"]["numeric_basis"],
        caveats=context["caveats"],
        explanation=content,
    )


def build_comparison_context(payload: AIComparisonRequest) -> dict[str, Any]:
    language = payload.response_language
    baseline_name = payload.baseline_name or _localized_message(language, "baseline_name")
    comparison_name = payload.comparison_name or _localized_message(language, "comparison_name")
    deltas = _comparison_deltas(payload.baseline, payload.comparison)
    local_assessment = _local_winner(
        baseline_name=baseline_name,
        comparison_name=comparison_name,
        deltas=deltas,
        language=language,
    )
    caveats = _comparison_caveats(payload.baseline, payload.comparison, language)

    return {
        "response_language": language,
        "density_definition": _localized_message(language, "density_definition"),
        "comparison_quality": "direct" if not caveats else "caution",
        "baseline": _signal_snapshot_context(baseline_name, payload.baseline),
        "comparison": _signal_snapshot_context(comparison_name, payload.comparison),
        "deltas_comparison_minus_baseline": deltas,
        "local_assessment": local_assessment,
        "caveats": caveats,
    }


def _signal_snapshot_context(name: str, result: DensityResponse) -> dict[str, Any]:
    summary = result.summary
    assessment = result.range_assessment
    settings = result.capture_settings
    return {
        "name": name,
        "frequency_from_hz": _rounded(settings.frequency_from_hz),
        "frequency_to_hz": _rounded(settings.frequency_to_hz),
        "span_hz": _rounded(settings.span_hz),
        "bins": settings.bins,
        "bin_width_hz": _rounded(summary.bin_width_hz),
        "capture_seconds": _rounded(settings.capture_seconds),
        "window": settings.window,
        "occupancy_threshold_db": _rounded(settings.occupancy_threshold_db),
        "occupancy_percent": _rounded(assessment.occupancy_percent),
        "occupied_bins": assessment.occupied_bins,
        "occupied_bandwidth_hz": _rounded(assessment.occupied_bandwidth_hz),
        "noise_floor_db_per_hz": _rounded(assessment.noise_floor_db_per_hz),
        "threshold_db_per_hz": _rounded(assessment.threshold_db_per_hz),
        "mean_excess_db": _rounded(assessment.mean_excess_db),
        "peak_to_floor_db": _rounded(assessment.peak_to_floor_db),
        "assessment_label": assessment.label,
        "mean_density_db_per_hz": _rounded(summary.mean_density_db_per_hz),
        "peak_density_db_per_hz": _rounded(summary.peak_density_db_per_hz),
        "peak_frequency_hz": _rounded(summary.peak_frequency_hz),
        "integrated_power_db": _rounded(summary.integrated_power_db),
        "sample_count": summary.sample_count,
        "top_density_bins": _top_density_bins(result),
    }


def _comparison_deltas(
    baseline: DensityResponse,
    comparison: DensityResponse,
) -> dict[str, float]:
    return {
        "occupancy_percent_points": _rounded(
            comparison.range_assessment.occupancy_percent
            - baseline.range_assessment.occupancy_percent
        ),
        "occupied_bins": _rounded(
            comparison.range_assessment.occupied_bins - baseline.range_assessment.occupied_bins
        ),
        "occupied_bandwidth_hz": _rounded(
            comparison.range_assessment.occupied_bandwidth_hz
            - baseline.range_assessment.occupied_bandwidth_hz
        ),
        "mean_density_db": _rounded(
            comparison.summary.mean_density_db_per_hz - baseline.summary.mean_density_db_per_hz
        ),
        "peak_density_db": _rounded(
            comparison.summary.peak_density_db_per_hz - baseline.summary.peak_density_db_per_hz
        ),
        "integrated_power_db": _rounded(
            comparison.summary.integrated_power_db - baseline.summary.integrated_power_db
        ),
        "peak_to_floor_db": _rounded(
            comparison.range_assessment.peak_to_floor_db
            - baseline.range_assessment.peak_to_floor_db
        ),
        "mean_excess_db": _rounded(
            comparison.range_assessment.mean_excess_db - baseline.range_assessment.mean_excess_db
        ),
        "peak_frequency_hz": _rounded(
            comparison.summary.peak_frequency_hz - baseline.summary.peak_frequency_hz
        ),
    }


def _local_winner(
    baseline_name: str,
    comparison_name: str,
    deltas: dict[str, float],
    language: LanguageCode,
) -> dict[str, str]:
    labels = _metric_labels(language)
    checks = [
        (
            deltas["occupancy_percent_points"],
            0.5,
            "occupancy_percent",
            labels["occupancy_percent"],
            "percentage points",
        ),
        (
            deltas["occupied_bandwidth_hz"],
            1.0,
            "occupied_bandwidth_hz",
            labels["occupied_bandwidth"],
            "Hz",
        ),
        (
            deltas["mean_density_db"],
            0.5,
            "mean_density_db_per_hz",
            labels["mean_density"],
            "dB",
        ),
        (
            deltas["integrated_power_db"],
            0.5,
            "integrated_power_db",
            labels["integrated_power"],
            "dB",
        ),
    ]

    for delta, threshold, metric, label, unit in checks:
        if abs(delta) >= threshold:
            winner = "comparison" if delta > 0 else "baseline"
            winner_name = comparison_name if delta > 0 else baseline_name
            direction = _localized_message(
                language,
                "direction_higher" if delta > 0 else "direction_lower",
            )
            return {
                "winner": winner,
                "winner_name": winner_name,
                "numeric_basis": _localized_message(
                    language,
                    "numeric_basis",
                    winner_name=winner_name,
                    label=label,
                    delta=f"{delta:g}",
                    unit=unit,
                    direction=direction,
                ),
                "primary_metric": metric,
            }

    return {
        "winner": "tie",
        "winner_name": _localized_message(language, "tie_winner_name"),
        "numeric_basis": _localized_message(language, "tie_numeric_basis"),
        "primary_metric": "no_clear_delta",
    }


def _comparison_caveats(
    baseline: DensityResponse,
    comparison: DensityResponse,
    language: LanguageCode,
) -> list[str]:
    caveats: list[str] = []
    if not _same_number(
        baseline.capture_settings.frequency_from_hz,
        comparison.capture_settings.frequency_from_hz,
    ) or not _same_number(
        baseline.capture_settings.frequency_to_hz,
        comparison.capture_settings.frequency_to_hz,
    ):
        caveats.append(_localized_message(language, "caveat_frequency_range"))
    if baseline.capture_settings.bins != comparison.capture_settings.bins:
        caveats.append(_localized_message(language, "caveat_bins"))
    if not _same_number(
        baseline.capture_settings.occupancy_threshold_db,
        comparison.capture_settings.occupancy_threshold_db,
    ):
        caveats.append(_localized_message(language, "caveat_threshold"))
    if baseline.capture_settings.window != comparison.capture_settings.window:
        caveats.append(_localized_message(language, "caveat_window"))
    if not baseline.bins or not comparison.bins:
        caveats.append(_localized_message(language, "caveat_missing_bins"))
    return caveats


def _top_density_bins(result: DensityResponse) -> list[dict[str, float | int]]:
    bins = nlargest(5, result.bins, key=lambda item: item.density_db_per_hz)
    return [
        {
            "index": item.index,
            "frequency_hz": _rounded(item.frequency_hz),
            "density_db_per_hz": _rounded(item.density_db_per_hz),
            "power_db": _rounded(item.power_db),
        }
        for item in bins
    ]


def _system_prompt(language: LanguageCode) -> str:
    if language == "uk":
        return (
            "Ти RF-аналітик для спектральних вимірів. Відповідай українською. "
            "Порівнюй тільки за наданими числовими даними: зайнятість діапазону, "
            "occupied bandwidth, mean/peak density, integrated power, noise floor "
            "і пікові bins. Якщо точного пояснення з даних немає, прямо скажи це "
            "і запропонуй найбільш імовірну технічну гіпотезу без вигаданих фактів."
        )

    return (
        "You are an RF analyst for spectral measurements. Respond in English. "
        "Compare only using the provided numeric data: range occupancy, occupied bandwidth, "
        "mean/peak density, integrated power, noise floor, and peak bins. If the data does "
        "not support a precise explanation, say that directly and provide the most likely "
        "technical hypothesis without inventing facts."
    )


def _user_prompt(language: LanguageCode, context: dict[str, Any]) -> str:
    serialized_context = json.dumps(context, ensure_ascii=False, indent=2)
    if language == "uk":
        return (
            "Порівняй два snapshots радіосигналів. Дай детальне пояснення: "
            "1) який сигнал щільніший; 2) точні числові причини; "
            "3) що може пояснювати різницю; 4) які обмеження має такий висновок.\n\n"
            f"Дані:\n{serialized_context}"
        )

    return (
        "Compare two radio-signal snapshots. Give a detailed explanation: "
        "1) which signal is denser; 2) the exact numeric reasons; "
        "3) what may explain the difference; 4) what limitations this conclusion has.\n\n"
        f"Data:\n{serialized_context}"
    )


def _metric_labels(language: LanguageCode) -> dict[str, str]:
    if language == "uk":
        return {
            "occupancy_percent": "частка зайнятих bins",
            "occupied_bandwidth": "зайнята смуга",
            "mean_density": "середня спектральна щільність",
            "integrated_power": "інтегральна потужність",
        }

    return {
        "occupancy_percent": "occupied bins share",
        "occupied_bandwidth": "occupied bandwidth",
        "mean_density": "mean spectral density",
        "integrated_power": "integrated power",
    }


def _localized_message(language: LanguageCode, key: str, **values: object) -> str:
    messages = _UK_MESSAGES if language == "uk" else _EN_MESSAGES
    return messages[key].format(**values)


_EN_MESSAGES = {
    "missing_api_key": (
        "AI analysis is unavailable: add OPENAI_API_KEY or AI_API_KEY to backend/.env."
    ),
    "timeout": (
        "AI analysis is unavailable: the AI API request timed out. A stable internet "
        "connection is required."
    ),
    "auth_detail": "check OPENAI_API_KEY or AI_API_KEY.",
    "not_found_detail": "check AI_BASE_URL and AI_MODEL.",
    "rate_limit_detail": "the AI API temporarily limited requests or quota is exhausted.",
    "generic_http_detail": "check internet access, AI_BASE_URL, and AI_MODEL.",
    "http_error": "AI API returned HTTP {status_code}: {detail}",
    "transport": "AI analysis is unavailable: cannot connect to the AI API. Internet is required.",
    "empty_response": "AI API returned no explanation text.",
    "baseline_name": "Baseline",
    "comparison_name": "Comparison",
    "density_definition": (
        "Treat the denser signal as the one with the larger share of FFT bins above "
        "noise floor + occupancy threshold. If occupancy difference is small, also "
        "consider occupied bandwidth, mean density, and integrated power."
    ),
    "direction_higher": "higher",
    "direction_lower": "lower",
    "numeric_basis": (
        "{winner_name} is denser by the '{label}' metric: delta comparison-baseline = "
        "{delta} {unit}; in the comparison snapshot this metric is {direction}."
    ),
    "tie_winner_name": "approximately equal",
    "tie_numeric_basis": (
        "The difference in occupancy, occupied bandwidth, mean density, and integrated "
        "power is below practical thresholds for a confident conclusion."
    ),
    "caveat_frequency_range": (
        "Frequency ranges differ, so density is compared within each range."
    ),
    "caveat_bins": "FFT bin counts differ; bin-level comparison is not direct.",
    "caveat_threshold": "Occupancy thresholds differ; occupancy_percent may shift.",
    "caveat_window": "FFT windows differ; peak values and leakage may differ.",
    "caveat_missing_bins": (
        "One of the snapshots has no bin-level rows; AI can only use summary data."
    ),
}


_UK_MESSAGES = {
    "missing_api_key": (
        "AI аналіз недоступний: додайте OPENAI_API_KEY або AI_API_KEY у backend/.env."
    ),
    "timeout": (
        "AI аналіз недоступний: запит до AI API перевищив час очікування. "
        "Потрібен стабільний інтернет."
    ),
    "auth_detail": "перевірте OPENAI_API_KEY або AI_API_KEY.",
    "not_found_detail": "перевірте AI_BASE_URL та AI_MODEL.",
    "rate_limit_detail": "AI API тимчасово обмежив запити або вичерпано квоту.",
    "generic_http_detail": "перевірте інтернет, AI_BASE_URL і AI_MODEL.",
    "http_error": "AI API повернув HTTP {status_code}: {detail}",
    "transport": "AI аналіз недоступний: немає з'єднання з AI API. Потрібен інтернет.",
    "empty_response": "AI API відповів без тексту пояснення.",
    "baseline_name": "База",
    "comparison_name": "Порівняння",
    "density_definition": (
        "Щільнішим вважай сигнал із більшою часткою FFT bins вище "
        "noise floor + occupancy threshold. Якщо різниця зайнятості мала, "
        "додатково враховуй occupied bandwidth, mean density та integrated power."
    ),
    "direction_higher": "вища",
    "direction_lower": "нижча",
    "numeric_basis": (
        "{winner_name} щільніший за метрикою '{label}': delta comparison-baseline = "
        "{delta} {unit}, тобто у snapshot 'Порівняння' ця метрика {direction}."
    ),
    "tie_winner_name": "приблизно однаково",
    "tie_numeric_basis": (
        "Різниця у зайнятості, occupied bandwidth, mean density та integrated power "
        "менша за практичні пороги для впевненого висновку."
    ),
    "caveat_frequency_range": (
        "Діапазони частот різні, тому щільність порівнюється всередині кожного діапазону."
    ),
    "caveat_bins": "Кількість FFT bins різна; bin-level порівняння не є прямим.",
    "caveat_threshold": "Поріг зайнятості різний; occupancy_percent може зміщуватися.",
    "caveat_window": "FFT window різний; peak та leakage можуть відрізнятися.",
    "caveat_missing_bins": (
        "Для одного зі snapshot-ів немає bin-level rows; AI бачить тільки summary."
    ),
}


def _extract_chat_message(response_payload: dict[str, Any]) -> str:
    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""

    message = choices[0].get("message")
    if not isinstance(message, dict):
        return ""

    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                chunks.append(item["text"])
        return "\n".join(chunks).strip()
    return ""


def _extract_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ""

    error = payload.get("error")
    if not isinstance(error, dict):
        return ""

    message = error.get("message")
    if not isinstance(message, str):
        return ""

    return message.strip()[:500]


def _same_number(left: float, right: float, tolerance: float = 1e-9) -> bool:
    return abs(left - right) <= tolerance


def _rounded(value: float | int, digits: int = 6) -> float:
    return round(float(value), digits)
