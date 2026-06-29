from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from typing import Any


def load_module() -> Any:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "llm_verify_submission_articles.py"
    spec = importlib.util.spec_from_file_location("llm_verify_submission_articles_script", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def article(law_id: str, title: str = "Luật A", article_no: str = "Điều 1") -> str:
    return f"{law_id}|{title}|{article_no}"


def record(articles: list[str], record_id: int = 1, question: str = "Nộp thuế thế nào?", answer: str = "Theo Điều 1.") -> dict[str, Any]:
    module = load_module()
    return {"id": record_id, "question": question, "answer": answer, "relevant_docs": module.rebuild_docs_from_articles(articles), "relevant_articles": articles}


def options(mode: str = "balanced") -> dict[str, Any]:
    return {"mode": mode, "max_candidates": 12, "max_article_chars": 1200, "limit": None, "start_id": None, "end_id": None, "resume_from_changes": None, "write_incremental": False, "checkpoint_every": 0, "progress_every": 10, "max_retries": 2, "retry_sleep_seconds": 0, "health_check_before_call": False, "merge_changes": False, "only_possible_overpruned": False, "priority_domains": "", "sleep_seconds": 0, "changes": "changes.jsonl", "output": "output.json", "report": "report.json", "zip_output": None, "disable_thinking": False}


def test_parse_article_ref() -> None:
    module = load_module()
    ref = module.parse_article_ref("38/2019/QH14|Luật Quản lý thuế|Điều 3")
    assert ref.law_id == "38/2019/QH14"
    assert ref.law_title == "Luật Quản lý thuế"
    assert ref.article_no == "Điều 3"
    assert ref.doc_ref == "38/2019/QH14|Luật Quản lý thuế"
    assert module.parse_article_ref("bad") is None


def test_article_text_lookup_exact_key() -> None:
    module = load_module()
    lookup = module.build_article_text_lookup([{"law_id": "01/2020/QH14", "law_title": "Luật A", "article_no": "Điều 1", "article_text": "text exact"}])
    ref = module.parse_article_ref(article("01/2020/QH14", "Luật A", "Điều 1"))
    assert module.lookup_article_text(lookup, ref) == ("text exact", None, False)


def test_article_text_lookup_fallback_law_id_article_no() -> None:
    module = load_module()
    lookup = module.build_article_text_lookup([{"law_id": "01/2020/QH14", "law_title": "Luật khác", "article_no": "Điều 1", "article_text": "fallback text"}])
    ref = module.parse_article_ref(article("01/2020/QH14", "Luật A", "Điều 1"))
    text, warning, missing = module.lookup_article_text(lookup, ref)
    assert text == "fallback text"
    assert warning is None
    assert missing is False


def test_candidate_ordering_with_fallback_and_audit_risky_fields() -> None:
    module = load_module()
    articles = [article(f"0{i}/2020/QH14", f"Luật {i}", f"Điều {i}") for i in range(1, 6)]
    audit = {"answer_mentioned_removed_articles": articles[3], "legal_basis_removed_articles": articles[4], "domain_primary_removed_articles": articles[2]}
    ordered = module.order_candidate_refs(articles, [articles[1]], audit, max_candidates=4)
    assert [ref.raw for ref in ordered] == [articles[1], articles[3], articles[4], articles[2]]


def test_prompt_candidate_formatting() -> None:
    module = load_module()
    ref = module.parse_article_ref(article("01/2020/QH14", "Luật A", "Điều 1"))
    candidate = module.Candidate(1, ref, "Nội dung điều luật", 0)
    prompt = module.format_user_prompt("Câu hỏi?", [candidate])
    assert "[1]" in prompt
    assert "article_ref: 01/2020/QH14|Luật A|Điều 1" in prompt
    assert "article_text:" in prompt


def test_json_parsing_direct_and_fenced_noisy_output() -> None:
    module = load_module()
    direct = '{"selected": [], "rejected": []}'
    fenced = 'noise```json\n{"selected": [], "rejected": []}\n```tail'
    assert module.parse_llm_json(direct)["selected"] == []
    assert module.parse_llm_json(fenced)["rejected"] == []


def test_label_normalization_and_confidence_clamping() -> None:
    module = load_module()
    assert module.normalize_label("direct") == "direct_relevant"
    assert module.normalize_label("supporting") == "strong_supporting"
    assert module.normalize_label("old_law") == "superseded_old_law"
    assert module.clamp_confidence(2) == 1.0
    assert module.clamp_confidence(-1) == 0.0


def test_mode_thresholds() -> None:
    module = load_module()
    assert module.passes_mode_threshold("direct_relevant", 0.75, mode="strict", question_type="default")
    assert not module.passes_mode_threshold("strong_supporting", 0.90, mode="strict", question_type="default")
    assert module.passes_mode_threshold("strong_supporting", 0.60, mode="balanced", question_type="default")
    assert module.passes_mode_threshold("weak_supporting", 0.70, mode="balanced", question_type="list_policy")
    assert module.passes_mode_threshold("direct_relevant", 0.50, mode="recall", question_type="default")


def test_question_type_detection() -> None:
    module = load_module()
    assert module.detect_question_type("Thời hạn bao lâu?") == "single_fact"
    assert module.detect_question_type("Câu hỏi chung?") == "default"
    assert module.detect_question_type("Hồ sơ bao gồm những gì?") == "list_policy"
    assert module.detect_question_type("Vừa nộp thuế vừa bị phạt thì sao?") == "multi_part"


def test_fallback_on_invalid_json_and_empty_selection() -> None:
    module = load_module()
    articles = [article("01/2020/QH14", "Luật A", "Điều 1"), article("02/2020/QH14", "Luật B", "Điều 2")]
    original = record(articles)
    fallback = record([articles[0]])
    lookup = module.build_article_text_lookup([])
    patched, change = module.verify_record(record=original, fallback=fallback, audit={}, article_lookup=lookup, prompt_template="prompt", options=options(), llm_client=lambda _messages: "not json", domain="tax", question_type="default")
    assert patched["relevant_articles"] == [articles[0]]
    assert change["fallback_used"] is True
    patched2, change2 = module.verify_record(record=original, fallback=fallback, audit={}, article_lookup=lookup, prompt_template="prompt", options=options(), llm_client=lambda _messages: '{"selected": [], "rejected": [{"candidate_id": 1, "label": "irrelevant", "confidence": 1}]}', domain="tax", question_type="default")
    assert patched2["relevant_articles"] == [articles[0]]
    assert change2["fallback_used"] is True


def test_never_empty_articles_and_rebuild_docs() -> None:
    module = load_module()
    original = record([article("01/2020/QH14", "Luật A", "Điều 1")])
    empty_fallback = {**original, "relevant_docs": [], "relevant_articles": []}
    patched = module.fallback_or_top_original(original, empty_fallback)
    assert patched["relevant_articles"]
    assert patched["relevant_docs"] == ["01/2020/QH14|Luật A"]
    assert module.rebuild_docs_from_articles([article("01/2020/QH14", "Luật A", "Điều 1"), article("01/2020/QH14", "Luật A", "Điều 2")]) == ["01/2020/QH14|Luật A"]


def test_flat_zip_output(tmp_path: Path) -> None:
    module = load_module()
    output = tmp_path / "submission.zip"
    module.write_flat_zip(output, [record([article("01/2020/QH14", "Luật A", "Điều 1")])])
    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == ["results.json"]


def test_report_field_creation() -> None:
    module = load_module()
    original = record([article("01/2020/QH14", "Luật A", "Điều 1")])
    change = module.build_change(original, original, mode="balanced", domain="tax", question_type="default", possible_overpruned=True, llm_success=True, fallback_used=False, warnings=[])
    report = module.build_report([original], [original], [change], module.Counter({"llm_success_count": 1}), module.Counter({"direct_relevant": 1}), module.Counter({"irrelevant": 1}), module.Counter({"tax": 1}), module.Counter(), {}, options())
    assert report["total_records"] == 1
    assert report["mode"] == "balanced"
    assert "domain_summary" in report


def test_disable_thinking_adds_chat_template_kwargs(monkeypatch: Any) -> None:
    module = load_module()
    captured: dict[str, Any] = {}

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def read(self) -> bytes:
            return b'{"choices":[{"message":{"content":"{\\"ok\\": true}"}}]}'

    def fake_urlopen(request: Any, timeout: float) -> FakeResponse:
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    content = module.call_openai_compatible("http://localhost:8000/v1", "qwen3-14b", [{"role": "user", "content": "hi"}], 0, 120, disable_thinking=True)

    assert json.loads(content) == {"ok": True}
    assert captured["body"]["chat_template_kwargs"] == {"enable_thinking": False}
    assert captured["timeout"] == 120


def test_disable_thinking_not_set_by_default(monkeypatch: Any) -> None:
    module = load_module()
    captured: dict[str, Any] = {}

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def read(self) -> bytes:
            return b'{"choices":[{"message":{"content":"{\\"ok\\": true}"}}]}'

    def fake_urlopen(request: Any, timeout: float) -> FakeResponse:
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    module.call_openai_compatible("http://localhost:8000/v1", "qwen3-14b", [{"role": "user", "content": "hi"}], 0, 120)

    assert "chat_template_kwargs" not in captured["body"]


def test_parse_json_after_think_block() -> None:
    module = load_module()
    parsed = module.parse_llm_json('<think>reasoning that must be ignored</think>{"selected": [], "rejected": []}')

    assert parsed == {"selected": [], "rejected": []}



def verify_sample(module: Any, records: list[dict[str, Any]], fallback_records: list[dict[str, Any]], opts: dict[str, Any], llm_client: Any, resume: dict[int, dict[str, Any]] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    lookup = module.build_article_text_lookup([
        {"law_id": "01/2020/QH14", "law_title": "Luật A", "article_no": "Điều 1", "article_text": "A"},
        {"law_id": "02/2020/QH14", "law_title": "Luật B", "article_no": "Điều 2", "article_text": "B"},
        {"law_id": "03/2020/QH14", "law_title": "Luật C", "article_no": "Điều 3", "article_text": "C"},
    ])
    return module.verify_submission(
        input_records=records,
        fallback_by_id={row["id"]: row for row in fallback_records},
        audit_by_id={},
        article_lookup=lookup,
        prompt_template="prompt",
        options=opts,
        resume_success_by_id=resume or {},
        llm_client=llm_client,
        health_check=None,
    )


def test_start_end_id_processes_only_chunk_but_outputs_all_records() -> None:
    module = load_module()
    articles = [article("01/2020/QH14", "Luật A", "Điều 1"), article("02/2020/QH14", "Luật B", "Điều 2")]
    records = [record(articles, record_id=i) for i in range(1, 4)]
    fallbacks = [record([articles[0]], record_id=i) for i in range(1, 4)]
    opts = options(); opts.update({"start_id": 2, "end_id": 2})
    calls = {"count": 0}

    def llm(_messages: Any) -> str:
        calls["count"] += 1
        return '{"selected": [{"candidate_id": 2, "label": "direct_relevant", "confidence": 0.9}], "rejected": []}'

    output, report, changes = verify_sample(module, records, fallbacks, opts, llm)

    assert len(output) == 3
    assert calls["count"] == 1
    assert output[1]["relevant_articles"] == [articles[1]]
    assert output[0]["relevant_articles"] == [articles[0]]
    assert report["processed_in_chunk_count"] == 1
    assert len(changes) == 1


def test_write_incremental_writes_one_line_per_processed_record(tmp_path: Path) -> None:
    module = load_module()
    articles = [article("01/2020/QH14", "Luật A", "Điều 1")]
    records = [record(articles, record_id=1), record(articles, record_id=2)]
    opts = options(); opts.update({"write_incremental": True, "changes": str(tmp_path / "changes.jsonl")})
    verify_sample(module, records, records, opts, lambda _messages: '{"selected": [{"candidate_id": 1, "label": "direct_relevant", "confidence": 0.9}], "rejected": []}')

    lines = (tmp_path / "changes.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert all(json.loads(line)["after_docs"] for line in lines)


def test_resume_from_changes_skips_successful_records() -> None:
    module = load_module()
    a1 = article("01/2020/QH14", "Luật A", "Điều 1")
    a2 = article("02/2020/QH14", "Luật B", "Điều 2")
    records = [record([a1, a2], record_id=1)]
    resume = {1: {"id": 1, "llm_success": True, "fallback_used": False, "after_articles": [a2], "after_docs": ["02/2020/QH14|Luật B"]}}
    calls = {"count": 0}
    output, report, changes = verify_sample(module, records, [record([a1], record_id=1)], options(), lambda _messages: calls.__setitem__("count", calls["count"] + 1) or "{}", resume)

    assert calls["count"] == 0
    assert output[0]["relevant_articles"] == [a2]
    assert report["resumed_success_count"] == 1
    assert changes == []


def test_merge_changes_uses_latest_successful_entry(tmp_path: Path) -> None:
    module = load_module()
    a1 = article("01/2020/QH14", "Luật A", "Điều 1")
    a2 = article("02/2020/QH14", "Luật B", "Điều 2")
    path = tmp_path / "changes.jsonl"
    path.write_text("\n".join([
        json.dumps({"id": 1, "llm_success": True, "fallback_used": False, "after_articles": [a1], "after_docs": ["01/2020/QH14|Luật A"]}),
        json.dumps({"id": 1, "llm_success": True, "fallback_used": False, "after_articles": [a2], "after_docs": ["02/2020/QH14|Luật B"]}),
    ]), encoding="utf-8")

    loaded = module.load_resume_success_changes(path)

    assert loaded[1]["after_articles"] == [a2]


def test_merge_changes_outputs_all_records() -> None:
    module = load_module()
    a1 = article("01/2020/QH14", "Luật A", "Điều 1")
    a2 = article("02/2020/QH14", "Luật B", "Điều 2")
    records = [record([a1, a2], record_id=1), record([a1, a2], record_id=2)]
    fallback = [record([a1], record_id=1), record([a1], record_id=2)]
    resume = {2: {"id": 2, "llm_success": True, "fallback_used": False, "after_articles": [a2], "after_docs": ["02/2020/QH14|Luật B"]}}

    output, report, _changes = module.merge_changes_output(input_records=records, fallback_by_id={row["id"]: row for row in fallback}, resume_success_by_id=resume, options=options())

    assert len(output) == 2
    assert output[0]["relevant_articles"] == [a1]
    assert output[1]["relevant_articles"] == [a2]
    assert report["merge_only"] is True


def test_retry_on_connection_refused() -> None:
    module = load_module()
    opts = options(); opts.update({"max_retries": 2, "retry_sleep_seconds": 0})
    attempts = {"count": 0}
    counters = module.Counter()
    state = {"retries": 0}

    def flaky(_messages: Any) -> str:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("Connection refused")
        return "ok"

    client = module.build_retrying_client(1, flaky, None, opts, counters, state)

    assert client([]) == "ok"
    assert attempts["count"] == 2
    assert state["retries"] == 1


def test_no_retry_on_404_model_not_found() -> None:
    module = load_module()
    opts = options(); opts.update({"max_retries": 2, "retry_sleep_seconds": 0})
    attempts = {"count": 0}

    def fail(_messages: Any) -> str:
        attempts["count"] += 1
        raise RuntimeError("HTTP Error 404 model not found")

    client = module.build_retrying_client(1, fail, None, opts, module.Counter(), {"retries": 0})

    try:
        client([])
    except module.RequestFailure:
        pass
    assert attempts["count"] == 1


def test_progress_logging_prints_current_id(capsys: Any) -> None:
    module = load_module()
    articles = [article("01/2020/QH14", "Luật A", "Điều 1")]
    opts = options(); opts.update({"progress_every": 1})
    verify_sample(module, [record(articles, record_id=7)], [record(articles, record_id=7)], opts, lambda _messages: '{"selected": [{"candidate_id": 1, "label": "direct_relevant", "confidence": 0.9}], "rejected": []}')

    captured = capsys.readouterr().out
    assert "[START]" in captured
    assert "[RECORD] id=7" in captured
    assert "[PROGRESS]" in captured
    assert "[DONE]" in captured


def test_report_contains_progress_resume_retry_fields() -> None:
    module = load_module()
    base = record([article("01/2020/QH14", "Luật A", "Điều 1")])
    opts = options(); opts.update({"progress_every": 1, "write_incremental": True, "checkpoint_every": 5})
    report = module.build_report([base], [base], [], module.Counter({"retry_count": 2, "request_failure_count": 1, "resumed_success_count": 1}), module.Counter(), module.Counter(), module.Counter(), module.Counter(), {}, opts, start_time=0.0, attempted_llm_count=3)

    for field in ("chunk_start_id", "chunk_end_id", "processed_in_chunk_count", "resumed_success_count", "attempted_llm_count", "request_failure_count", "retry_count", "merge_only", "progress_every", "write_incremental", "checkpoint_every", "incremental_changes_path", "partial_output_path", "partial_report_path", "elapsed_sec", "avg_sec_per_record"):
        assert field in report



def test_ids_file_processes_only_listed_ids_but_outputs_all_records(tmp_path: Path) -> None:
    module = load_module()
    articles = [article("01/2020/QH14", "Luật A", "Điều 1"), article("02/2020/QH14", "Luật B", "Điều 2")]
    records = [record(articles, record_id=i) for i in range(1, 5)]
    fallbacks = [record([articles[0]], record_id=i) for i in range(1, 5)]
    ids_file = tmp_path / "ids.txt"
    ids_file.write_text("2\n4\n", encoding="utf-8")
    opts = options(); opts.update({"ids_file": str(ids_file)})
    calls = {"count": 0}

    def llm(_messages: Any) -> str:
        calls["count"] += 1
        return '{"selected": [{"candidate_id": 2, "label": "direct_relevant", "confidence": 0.9}], "rejected": []}'

    output, report, changes = verify_sample(module, records, fallbacks, opts, llm)

    assert len(output) == 4
    assert calls["count"] == 2
    assert [change["id"] for change in changes] == [2, 4]
    assert output[0]["relevant_articles"] == [articles[0]]
    assert output[1]["relevant_articles"] == [articles[1]]
    assert output[3]["relevant_articles"] == [articles[1]]
    assert report["ids_file"] == str(ids_file)
    assert report["ids_file_count"] == 2


def test_ids_file_intersects_with_start_end_range(tmp_path: Path) -> None:
    module = load_module()
    articles = [article("01/2020/QH14", "Luật A", "Điều 1"), article("02/2020/QH14", "Luật B", "Điều 2")]
    records = [record(articles, record_id=i) for i in range(1, 5)]
    fallbacks = [record([articles[0]], record_id=i) for i in range(1, 5)]
    ids_file = tmp_path / "ids.txt"
    ids_file.write_text("2\n4\n", encoding="utf-8")
    opts = options(); opts.update({"ids_file": str(ids_file), "start_id": 3, "end_id": 4})
    calls = {"count": 0}

    def llm(_messages: Any) -> str:
        calls["count"] += 1
        return '{"selected": [{"candidate_id": 2, "label": "direct_relevant", "confidence": 0.9}], "rejected": []}'

    output, report, changes = verify_sample(module, records, fallbacks, opts, llm)

    assert len(output) == 4
    assert calls["count"] == 1
    assert [change["id"] for change in changes] == [4]
    assert output[1]["relevant_articles"] == [articles[0]]
    assert output[3]["relevant_articles"] == [articles[1]]
    assert report["ids_file_count"] == 2
