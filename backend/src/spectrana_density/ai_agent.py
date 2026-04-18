# ruff: noqa: RUF001

from __future__ import annotations

import json
from heapq import nlargest
from typing import Any

import httpx

from spectrana_density.config import Settings
from spectrana_density.schemas import AIComparisonRequest, AIComparisonResponse, DensityResponse


class AIComparisonUnavailableError(RuntimeError):
    """Raised when the remote AI explanation cannot be generated."""


async def explain_signal_comparison(
    payload: AIComparisonRequest,
    settings: Settings,
) -> AIComparisonResponse:
    api_key = (settings.ai_api_key or "").strip()
    if not api_key:
        raise AIComparisonUnavailableError(
            "AI аналіз недоступний: додайте OPENAI_API_KEY або AI_API_KEY у backend/.env."
        )

    context = build_comparison_context(payload)
    request_body = {
        "model": settings.ai_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Ти RF-аналітик для спектральних вимірів. Пиши українською. "
                    "Порівнюй тільки за наданими числовими даними: зайнятість діапазону, "
                    "occupied bandwidth, mean/peak density, integrated power, noise floor "
                    "і пікові bins. Якщо точного пояснення з даних немає, прямо скажи це "
                    "і запропонуй найбільш імовірну технічну гіпотезу без вигаданих фактів."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Порівняй два snapshots радіосигналів. Дай детальне пояснення: "
                    "1) який сигнал щільніший; 2) точні числові причини; "
                    "3) що може пояснювати різницю; 4) які обмеження має такий висновок.\n\n"
                    f"Дані:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
                ),
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
            "AI аналіз недоступний: запит до AI API перевищив час очікування. "
            "Потрібен стабільний інтернет."
        ) from exc
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        api_detail = _extract_error_message(exc.response)
        if api_detail:
            detail = api_detail
        elif status_code in {401, 403}:
            detail = "перевірте OPENAI_API_KEY або AI_API_KEY."
        elif status_code == 404:
            detail = "перевірте AI_BASE_URL та AI_MODEL."
        elif status_code == 429:
            detail = "AI API тимчасово обмежив запити або вичерпано квоту."
        else:
            detail = "перевірте інтернет, AI_BASE_URL і AI_MODEL."
        raise AIComparisonUnavailableError(f"AI API повернув HTTP {status_code}: {detail}") from exc
    except httpx.TransportError as exc:
        raise AIComparisonUnavailableError(
            "AI аналіз недоступний: немає з'єднання з AI API. Потрібен інтернет."
        ) from exc

    content = _extract_chat_message(response.json())
    if not content:
        raise AIComparisonUnavailableError("AI API відповів без тексту пояснення.")

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
    baseline_name = payload.baseline_name or "База"
    comparison_name = payload.comparison_name or "Порівняння"
    deltas = _comparison_deltas(payload.baseline, payload.comparison)
    local_assessment = _local_winner(
        baseline_name=baseline_name,
        comparison_name=comparison_name,
        deltas=deltas,
    )
    caveats = _comparison_caveats(payload.baseline, payload.comparison)

    return {
        "density_definition": (
            "Щільнішим вважай сигнал із більшою часткою FFT bins вище "
            "noise floor + occupancy threshold. Якщо різниця зайнятості мала, "
            "додатково враховуй occupied bandwidth, mean density та integrated power."
        ),
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
) -> dict[str, str]:
    checks = [
        (
            deltas["occupancy_percent_points"],
            0.5,
            "occupancy_percent",
            "частка зайнятих bins",
            "percentage points",
        ),
        (
            deltas["occupied_bandwidth_hz"],
            1.0,
            "occupied_bandwidth_hz",
            "зайнята смуга",
            "Hz",
        ),
        (
            deltas["mean_density_db"],
            0.5,
            "mean_density_db_per_hz",
            "середня спектральна щільність",
            "dB",
        ),
        (
            deltas["integrated_power_db"],
            0.5,
            "integrated_power_db",
            "інтегральна потужність",
            "dB",
        ),
    ]

    for delta, threshold, metric, label, unit in checks:
        if abs(delta) >= threshold:
            winner = "comparison" if delta > 0 else "baseline"
            winner_name = comparison_name if delta > 0 else baseline_name
            direction = "вища" if delta > 0 else "нижча"
            return {
                "winner": winner,
                "winner_name": winner_name,
                "numeric_basis": (
                    f"{winner_name} щільніший за метрикою '{label}': "
                    f"delta comparison-baseline = {delta:g} {unit}, тобто у snapshot "
                    f"'Порівняння' ця метрика {direction}."
                ),
                "primary_metric": metric,
            }

    return {
        "winner": "tie",
        "winner_name": "приблизно однаково",
        "numeric_basis": (
            "Різниця у зайнятості, occupied bandwidth, mean density та integrated power "
            "менша за практичні пороги для впевненого висновку."
        ),
        "primary_metric": "no_clear_delta",
    }


def _comparison_caveats(baseline: DensityResponse, comparison: DensityResponse) -> list[str]:
    caveats: list[str] = []
    if not _same_number(
        baseline.capture_settings.frequency_from_hz,
        comparison.capture_settings.frequency_from_hz,
    ) or not _same_number(
        baseline.capture_settings.frequency_to_hz,
        comparison.capture_settings.frequency_to_hz,
    ):
        caveats.append(
            "Діапазони частот різні, тому щільність порівнюється всередині кожного діапазону."
        )
    if baseline.capture_settings.bins != comparison.capture_settings.bins:
        caveats.append("Кількість FFT bins різна; bin-level порівняння не є прямим.")
    if not _same_number(
        baseline.capture_settings.occupancy_threshold_db,
        comparison.capture_settings.occupancy_threshold_db,
    ):
        caveats.append("Поріг зайнятості різний; occupancy_percent може зміщуватися.")
    if baseline.capture_settings.window != comparison.capture_settings.window:
        caveats.append("FFT window різний; peak та leakage можуть відрізнятися.")
    if not baseline.bins or not comparison.bins:
        caveats.append("Для одного зі snapshot-ів немає bin-level rows; AI бачить тільки summary.")
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
