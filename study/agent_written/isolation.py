"""References and pure command construction; deliberately no execution API."""
from pathlib import Path

from study.budget import validate_run_budget
from study.run_study import container_command

ISOLATION_SOURCE = "study.run_study.container_command"
RESOURCE_MONITOR_SOURCE = "study.resources.install_guard"
PROCESS_RUNNER_SOURCE = "study.process.run"


def scoring_envelope(image_id, inputs, wheels, seconds=900):
    """Describe existing isolation for one future scoring job, never start it.

    This is the existing worker command, NOT an agent-written executor: an
    approved adapter for baseline repetition/app startup is still required.
    """
    validate_run_budget([{"budget_seconds": seconds}])
    return container_command(image_id, "agent-written-plan", Path(inputs), Path(wheels), seconds)
