from spectrana_density.config import Settings
from spectrana_density.sources.aaronia import AaroniaIQSource
from spectrana_density.sources.base import IQSource
from spectrana_density.sources.mock import MockIQSource


def create_source(settings: Settings) -> IQSource:
    match settings.source_mode:
        case "aaronia":
            return AaroniaIQSource(settings)
        case "mock":
            return MockIQSource(settings)
