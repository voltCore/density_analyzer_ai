from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from spectrana_density.schemas import DensityRequest
from spectrana_density.signal.density import DensityComputation


@dataclass(frozen=True)
class IQCapture:
    samples: NDArray[np.complexfloating]
    sample_rate_hz: float
    frequency_from_hz: float
    frequency_to_hz: float
    unit: str = "normalized"
    packet_count: int = 1
    configured_device: bool = False
    sample_count: int | None = None
    density: DensityComputation | None = None
    metadata: dict[str, str | int | float | bool | None] = field(default_factory=dict)


class IQSource(Protocol):
    async def capture(self, request: DensityRequest) -> IQCapture:
        """Capture IQ samples for the requested frequency range."""
