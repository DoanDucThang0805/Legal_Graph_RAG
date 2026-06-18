import json
from dataclasses import dataclass
from zipfile import ZipFile

from backend.submission.build_results import build_results, build_submission_item
from backend.submission.make_zip import make_submission_zip
from backend.submission.validate_results import validate_results_file, validate_results_items


ARTICLE_ID = "04/2017/QH14|Luật hỗ trợ doanh nghiệp nhỏ và vừa|Điều 4"


def test_build_submission_item_derives_citations_from_dict_articles() -> None:
    item = build_submission_item(
        question_item={"id": 1, "question": "Doanh nghiệp nhỏ và vừa là gì?"},
        answer="Theo Điều 4, doanh nghiệp nhỏ và vừa gồm doanh nghiệp siêu nhỏ, nhỏ và vừa.",
        selected_articles=[
            {
                "article_id": ARTICLE_ID,
                "law_id": "04/2017/QH14",
                "law_title": "Luật hỗ trợ doanh nghiệp nhỏ và vừa",
                "article_no": "Điều 4",
            },
            ARTICLE_ID,
        ],
    )

    assert item["relevant_articles"] == [ARTICLE_ID]
    assert item["relevant_docs"] == ["04/2017/QH14|Luật hỗ trợ doanh nghiệp nhỏ và vừa"]


@dataclass
class ArticleObject:
    law_id: str
    law_title: str
    article_no: str


def test_build_results_supports_object_articles() -> None:
    items = [
        {
            "id": 1,
            "question": "Câu hỏi",
            "answer": "Theo Điều 5, nội dung trả lời.",
            "selected_articles": [
                ArticleObject(
                    law_id="01/2020/QH14",
                    law_title="Luật Doanh nghiệp",
                    article_no="Điều 5",
                )
            ],
        }
    ]

    results = build_results(items)

    assert results[0]["relevant_articles"] == ["01/2020/QH14|Luật Doanh nghiệp|Điều 5"]
    assert results[0]["relevant_docs"] == ["01/2020/QH14|Luật Doanh nghiệp"]


def test_validate_results_items_accepts_valid_item() -> None:
    report = validate_results_items(
        [
            {
                "id": 1,
                "question": "Câu hỏi",
                "answer": "Theo Điều 4, nội dung trả lời.",
                "relevant_docs": ["04/2017/QH14|Luật hỗ trợ doanh nghiệp nhỏ và vừa"],
                "relevant_articles": [ARTICLE_ID],
            }
        ],
        expected_ids={1},
    )

    assert report.is_valid
    assert report.errors == []
    assert report.num_items == 1


def test_validate_detects_missing_required_fields() -> None:
    report = validate_results_items([{"id": 1}])

    assert not report.is_valid
    assert any("missing required field: question" in error for error in report.errors)
    assert any("missing required field: answer" in error for error in report.errors)


def test_validate_detects_duplicate_id() -> None:
    item = {
        "id": 1,
        "question": "Câu hỏi",
        "answer": "Theo Điều 4, nội dung trả lời.",
        "relevant_docs": ["04/2017/QH14|Luật hỗ trợ doanh nghiệp nhỏ và vừa"],
        "relevant_articles": [ARTICLE_ID],
    }

    report = validate_results_items([item, item])

    assert not report.is_valid
    assert any("duplicate id: 1" in error for error in report.errors)


def test_validate_detects_invalid_article_format() -> None:
    report = validate_results_items(
        [
            {
                "id": 1,
                "question": "Câu hỏi",
                "answer": "Theo Điều 4, nội dung trả lời.",
                "relevant_docs": ["04/2017/QH14|Luật hỗ trợ doanh nghiệp nhỏ và vừa"],
                "relevant_articles": ["Điều 4"],
            }
        ]
    )

    assert not report.is_valid
    assert any("invalid canonical format" in error for error in report.errors)


def test_validate_detects_docs_not_derived_from_articles() -> None:
    report = validate_results_items(
        [
            {
                "id": 1,
                "question": "Câu hỏi",
                "answer": "Theo Điều 4, nội dung trả lời.",
                "relevant_docs": ["99/2020/QH14|Luật khác"],
                "relevant_articles": [ARTICLE_ID],
            }
        ]
    )

    assert not report.is_valid
    assert any("not derived from relevant_articles" in error for error in report.errors)


def test_validate_detects_answer_missing_selected_article_no() -> None:
    report = validate_results_items(
        [
            {
                "id": 1,
                "question": "Câu hỏi",
                "answer": "Nội dung trả lời chưa nhắc điều luật.",
                "relevant_docs": ["04/2017/QH14|Luật hỗ trợ doanh nghiệp nhỏ và vừa"],
                "relevant_articles": [ARTICLE_ID],
            }
        ]
    )

    assert not report.is_valid
    assert any("answer does not mention" in error for error in report.errors)


def test_validate_results_file_and_expected_ids(tmp_path) -> None:
    results_path = tmp_path / "results.json"
    results_path.write_text(
        json.dumps(
            [
                {
                    "id": 1,
                    "question": "Câu hỏi",
                    "answer": "Theo Điều 4, nội dung trả lời.",
                    "relevant_docs": ["04/2017/QH14|Luật hỗ trợ doanh nghiệp nhỏ và vừa"],
                    "relevant_articles": [ARTICLE_ID],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = validate_results_file(results_path, expected_ids={1, 2})

    assert not report.is_valid
    assert any("missing expected id: 2" in error for error in report.errors)


def test_make_submission_zip_contains_only_results_json(tmp_path) -> None:
    results_path = tmp_path / "results.json"
    zip_path = tmp_path / "submission.zip"
    results_path.write_text("[]", encoding="utf-8")

    output_path = make_submission_zip(results_path, zip_path)

    assert output_path == zip_path
    with ZipFile(zip_path) as archive:
        assert archive.namelist() == ["results.json"]
