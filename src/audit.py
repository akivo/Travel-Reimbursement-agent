from src.models import AuditStep


class AuditLogger:
    def __init__(self):
        self._steps: list[AuditStep] = []
        self._counter: int = 0

    def log(self, tool_called: str, input_summary: str, output_summary: str) -> None:
        self._counter += 1
        self._steps.append(AuditStep(
            step=self._counter,
            tool_called=tool_called,
            input_summary=input_summary,
            output_summary=output_summary[:300],
        ))

    def steps(self) -> list[AuditStep]:
        return list(self._steps)


def format_audit_trail(steps: list[AuditStep]) -> str:
    lines = ["\n[AUDIT TRAIL]", "-" * 60]
    for s in steps:
        lines.append(f"  Step {s.step}: [{s.tool_called}]")
        lines.append(f"    Input:  {s.input_summary}")
        lines.append(f"    Output: {s.output_summary}")
    lines.append("-" * 60)
    return "\n".join(lines)
