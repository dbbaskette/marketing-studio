"""Provider-neutral image contract, with no networking or provider implementation."""
from typing import Protocol


class ImageAdapter(Protocol):
    """Results satisfy runner.validation.validate_image_result.

    File references are owned staged assets, not arbitrary model-selected paths.
    A cancel response can remain unknown when remote cancellation is unavailable.
    """

    def readiness(self) -> dict: ...

    def generate(self, *, attempt_id: str, brief: dict) -> dict: ...

    def edit(self, *, attempt_id: str, brief: dict, reference_assets: list[dict]) -> dict: ...

    def status(self, *, attempt_id: str) -> dict: ...

    def cancel(self, *, attempt_id: str) -> dict: ...
