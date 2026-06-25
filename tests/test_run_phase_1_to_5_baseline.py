from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any


def load_runner_module() -> Any:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_phase_1_to_5_baseline.py"
    spec = importlib.util.spec_from_file_location("baseline_runner_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SubprocessRecorder:
    def __init__(self, return_codes: list[int] | None = None) -> None:
        self.return_codes = return_codes or []
        self.calls: list[dict[str, Any]] = []

    def run(self, command: list[str] | tuple[str, ...], **kwargs: Any) -> subprocess.CompletedProcess:
        self.calls.append({"command": tuple(command), "kwargs": kwargs})
        index = len(self.calls) - 1
        return_code = self.return_codes[index] if index < len(self.return_codes) else 0
        return subprocess.CompletedProcess(args=command, returncode=return_code)


def command_names(calls: list[dict[str, Any]]) -> list[str]:
    return [call["command"][1] for call in calls]


def test_import_script_does_not_run_subprocess(monkeypatch) -> None:
    recorder = SubprocessRecorder()
    monkeypatch.setattr(subprocess, "run", recorder.run)

    load_runner_module()

    assert recorder.calls == []


def test_dry_run_does_not_call_subprocess(monkeypatch) -> None:
    module = load_runner_module()
    recorder = SubprocessRecorder()
    monkeypatch.setattr(module.subprocess, "run", recorder.run)

    exit_code = module.main(["--dry-run", "--python-bin", "python-test"])

    assert exit_code == 0
    assert recorder.calls == []


def test_execute_calls_subprocess_in_step_order(monkeypatch, tmp_path) -> None:
    module = load_runner_module()
    recorder = SubprocessRecorder()
    monkeypatch.setattr(module.subprocess, "run", recorder.run)

    exit_code = module.main(["--execute", "--python-bin", "python-test", "--cwd", str(tmp_path)])

    assert exit_code == 0
    assert command_names(recorder.calls) == [
        "scripts/01_build_corpus.py",
        "scripts/02_build_indexes.py",
        "scripts/03_analyze_questions.py",
        "scripts/04_run_retrieval.py",
        "scripts/05_generate_answers.py",
        "scripts/06_build_submission.py",
        "scripts/07_validate_submission.py",
    ]
    assert recorder.calls[1]["command"] == (
        "python-test",
        "scripts/02_build_indexes.py",
        "--only",
        "all-no-dense",
    )
    assert recorder.calls[-1]["command"] == (
        "python-test",
        "scripts/07_validate_submission.py",
        "--zip-path",
        "data/outputs/submission.zip",
    )


def test_execute_uses_shell_false(monkeypatch, tmp_path) -> None:
    module = load_runner_module()
    recorder = SubprocessRecorder()
    monkeypatch.setattr(module.subprocess, "run", recorder.run)

    module.main(["--execute", "--cwd", str(tmp_path)])

    assert recorder.calls
    assert all(call["kwargs"]["shell"] is False for call in recorder.calls)


def test_execute_stops_on_first_failure(monkeypatch, tmp_path) -> None:
    module = load_runner_module()
    recorder = SubprocessRecorder(return_codes=[0, 3, 0])
    monkeypatch.setattr(module.subprocess, "run", recorder.run)

    exit_code = module.main(["--execute", "--cwd", str(tmp_path)])

    assert exit_code == 3
    assert command_names(recorder.calls) == [
        "scripts/01_build_corpus.py",
        "scripts/02_build_indexes.py",
    ]


def test_continue_on_error_runs_remaining_steps(monkeypatch, tmp_path) -> None:
    module = load_runner_module()
    recorder = SubprocessRecorder(return_codes=[0, 3, 0, 0, 0, 0, 0])
    monkeypatch.setattr(module.subprocess, "run", recorder.run)

    exit_code = module.main(["--execute", "--continue-on-error", "--cwd", str(tmp_path)])

    assert exit_code == 3
    assert len(recorder.calls) == 7


def test_start_end_phase_filters_steps(monkeypatch, tmp_path) -> None:
    module = load_runner_module()
    recorder = SubprocessRecorder()
    monkeypatch.setattr(module.subprocess, "run", recorder.run)

    exit_code = module.main(["--execute", "--start-phase", "3", "--end-phase", "4", "--cwd", str(tmp_path)])

    assert exit_code == 0
    assert command_names(recorder.calls) == [
        "scripts/03_analyze_questions.py",
        "scripts/04_run_retrieval.py",
    ]


def test_only_filters_phase_group(monkeypatch, tmp_path) -> None:
    module = load_runner_module()
    recorder = SubprocessRecorder()
    monkeypatch.setattr(module.subprocess, "run", recorder.run)

    exit_code = module.main(["--execute", "--only", "5", "--cwd", str(tmp_path)])

    assert exit_code == 0
    assert command_names(recorder.calls) == [
        "scripts/05_generate_answers.py",
        "scripts/06_build_submission.py",
        "scripts/07_validate_submission.py",
    ]


def test_skip_index_omits_phase_2_subprocess(monkeypatch, tmp_path) -> None:
    module = load_runner_module()
    recorder = SubprocessRecorder()
    monkeypatch.setattr(module.subprocess, "run", recorder.run)

    exit_code = module.main(["--execute", "--skip-index", "--cwd", str(tmp_path)])

    assert exit_code == 0
    assert "scripts/02_build_indexes.py" not in command_names(recorder.calls)


def test_limit_is_forwarded_only_to_supported_steps(monkeypatch, tmp_path) -> None:
    module = load_runner_module()
    recorder = SubprocessRecorder()
    monkeypatch.setattr(module.subprocess, "run", recorder.run)

    exit_code = module.main(["--execute", "--limit", "2", "--cwd", str(tmp_path)])

    assert exit_code == 0
    assert recorder.calls[3]["command"] == (
        sys.executable,
        "scripts/04_run_retrieval.py",
        "--limit",
        "2",
    )
    assert recorder.calls[4]["command"] == (
        sys.executable,
        "scripts/05_generate_answers.py",
        "--limit",
        "2",
    )
    assert "--limit" not in recorder.calls[5]["command"]


def test_python_bin_is_used_for_all_commands(monkeypatch, tmp_path) -> None:
    module = load_runner_module()
    recorder = SubprocessRecorder()
    monkeypatch.setattr(module.subprocess, "run", recorder.run)

    exit_code = module.main(["--execute", "--python-bin", "custom-python", "--cwd", str(tmp_path)])

    assert exit_code == 0
    assert all(call["command"][0] == "custom-python" for call in recorder.calls)
