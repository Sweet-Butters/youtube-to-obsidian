from datetime import date

import yaml

from notes_project.format_md import filename, render
from notes_project.summarize import Summary
from notes_project.youtube import VideoMeta


def _meta(**overrides):
    base = dict(
        video_id="abcDEF12345",
        title="Test: 한글 제목 [special]",
        channel="Some Channel",
        channel_url="https://www.youtube.com/channel/UC123",
        upload_date="2024-04-24",
        duration="23m 14s",
        description="...",
        category_id=28,
    )
    base.update(overrides)
    return VideoMeta(**base)


def _summary():
    return Summary(
        short="Two sentence summary.",
        long="- bullet one\n- bullet two",
        key_terms=["term1", "term2"],
        tags=["llm", "agent"],
        quotes=[{"text": "a quote", "ts": "01:23"}],
    )


def test_filename_contains_video_id_and_date():
    fn = filename(_meta(), date(2026, 5, 15))
    assert fn.startswith("2026-05-15_")
    assert "[abcDEF12345].md" in fn


def test_render_frontmatter_has_all_fields():
    body = render(
        _meta(), "ko", "manual", _summary(),
        transcript="hello transcript",
        watched=date(2026, 5, 15),
        display_lang="ko",
    )
    assert body.startswith("---\n")
    fm_text = body.split("---\n", 2)[1]
    fm = yaml.safe_load(fm_text)
    assert fm["video_id"] == "abcDEF12345"
    assert fm["category_id"] == 28
    assert fm["category_en"] == "Science & Technology"
    assert fm["category_ko"] == "과학/기술"
    assert fm["category"] == "과학/기술"  # display_lang=ko
    assert "youtube" in fm["tags"]
    assert "llm" in fm["tags"]


def test_render_display_lang_en():
    body = render(
        _meta(), "en", "auto", _summary(),
        transcript="hi",
        watched=date(2026, 5, 15),
        display_lang="en",
    )
    fm = yaml.safe_load(body.split("---\n", 2)[1])
    assert fm["category"] == "Science & Technology"


def test_render_unknown_category():
    body = render(
        _meta(category_id=None), "en", "auto", _summary(),
        transcript="hi", watched=date(2026, 5, 15), display_lang="ko",
    )
    fm = yaml.safe_load(body.split("---\n", 2)[1])
    assert fm["category"] == "기타"
