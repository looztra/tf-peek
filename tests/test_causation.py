"""Tests for tf_peek.causation."""

import pytest

from tf_peek.causation import (
    Causation,
    escape_for_markdown,
    escape_for_summary_html,
    mechanism_statement,
    phrase_reason,
    render_forcing_path,
    render_forcing_paths,
    resolve_causation,
)

# ---------------------------------------------------------------------------
# Path rendering notation (task 2.2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        pytest.param(["settings", 0, "tier"], "settings[0].tier", id="mixed-identifier-index-identifier"),
        pytest.param(["labels", "kubernetes.io/role"], 'labels["kubernetes.io/role"]', id="non-identifier-subscript"),
        pytest.param([0, "tier"], "[0].tier", id="leading-index-no-separator"),
        pytest.param(["a-b", "c_d"], "a-b.c_d", id="dash-and-underscore-are-identifier-safe"),
        pytest.param(["a"], "a", id="single-identifier-step-no-separator"),
        pytest.param(["tags", "0"], 'tags["0"]', id="string-digit-key-is-not-a-numeric-index"),
    ],
)
def test_render_forcing_path(path: list[str | int], expected: str) -> None:
    """A forcing path renders in HCL attribute-path notation with no leading separator."""
    assert render_forcing_path(path) == expected


# ---------------------------------------------------------------------------
# Sorting and de-duplication (task 2.3)
# ---------------------------------------------------------------------------


def test_render_forcing_paths_sorts_by_rendered_form() -> None:
    """Paths render in ascending lexical order of their rendered text, not plan order."""
    paths: list[list[str | int]] = [["zebra"], ["apple"], ["mango"]]
    assert render_forcing_paths(paths) == ["apple", "mango", "zebra"]


def test_render_forcing_paths_deduplicates_by_rendered_form() -> None:
    """A path stated more than once renders exactly once."""
    paths = [["settings", 0, "tier"], ["settings", 0, "tier"]]
    assert render_forcing_paths(paths) == ["settings[0].tier"]


# ---------------------------------------------------------------------------
# Escaping (task 2.4)
# ---------------------------------------------------------------------------


def test_escape_for_markdown_neutralizes_pipe_and_backtick_as_literal_text() -> None:
    """Pipe and backtick become escape *text*, not the original character, so they stay inert."""
    escaped = escape_for_markdown("a|b`c")
    assert "|" not in escaped
    assert "`" not in escaped
    assert escaped == r"a\u007cb\u0060c"


def test_escape_for_markdown_collapses_line_breaks() -> None:
    """CR, LF and CRLF all collapse to a visible escape so the fragment stays one physical line."""
    assert escape_for_markdown("a\nb") == "a\\nb"
    assert escape_for_markdown("a\r\nb") == "a\\nb"
    assert escape_for_markdown("a\rb") == "a\\nb"


def test_escape_for_summary_html_neutralizes_markup_characters() -> None:
    """`<`, `&`, `>` and `"` become HTML entities so hostile text cannot inject markup."""
    escaped = escape_for_summary_html('<b>&"</b>')
    assert "<" not in escaped
    assert ">" not in escaped
    assert '"' not in escaped
    assert escaped == "&lt;b&gt;&amp;&quot;&lt;/b&gt;"


def test_escape_for_summary_html_collapses_line_breaks() -> None:
    """A raw line break cannot break the collapsed `<summary>` line out of one physical line."""
    assert "\n" not in escape_for_summary_html("a\nb")


# ---------------------------------------------------------------------------
# Reason phrasing (task 2.5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected_fragment"),
    [
        pytest.param("replace_because_tainted", "tainted", id="tainted"),
        pytest.param("replace_by_request", "explicitly requested when the plan was created", id="by-request"),
        pytest.param("replace_by_triggers", "configured replacement triggers selected the replacement", id="triggers"),
        pytest.param(
            "delete_because_no_resource_config",
            "Terraform found no corresponding resource configuration",
            id="no-resource-config",
        ),
        pytest.param("delete_because_each_key", "for_each key no longer matches", id="each-key"),
        pytest.param("delete_because_no_move_target", "moved block", id="no-move-target"),
        pytest.param("delete_because_count_index", "count index is out of range", id="count-index"),
        pytest.param("delete_because_wrong_repetition", "addressing mode", id="wrong-repetition"),
        pytest.param("delete_because_no_module", "containing module instance", id="no-module"),
        pytest.param(
            "replace_because_cannot_update",
            "cannot be made without replacing the object",
            id="cannot-update",
        ),
    ],
)
def test_phrase_reason_known_codes_are_neutral_prose(code: str, expected_fragment: str) -> None:
    """Every known non-read reason code phrases as neutral prose, not the raw code."""
    phrase = phrase_reason(code)
    assert expected_fragment in phrase
    assert code not in phrase


def test_phrase_reason_unknown_code_passes_through_marked_as_such() -> None:
    """An unrecognized code is echoed verbatim behind a preamble marking it as passed through."""
    phrase = phrase_reason("a_future_reason_code")
    assert "a_future_reason_code" in phrase
    assert "reported by Terraform" in phrase


# ---------------------------------------------------------------------------
# Replacement mechanism statement
# ---------------------------------------------------------------------------


def test_mechanism_statement_destroy_first() -> None:
    """Destroy-then-create states the mechanism without asserting a consequence."""
    statement = mechanism_statement(destroy_before_create=True)
    assert "destroyed before its replacement is created" in statement
    assert "downtime" not in statement
    assert "data loss" not in statement


def test_mechanism_statement_create_first() -> None:
    """Create-before-destroy states the opposite mechanism."""
    statement = mechanism_statement(destroy_before_create=False)
    assert "created before the existing object is destroyed" in statement


# ---------------------------------------------------------------------------
# Precedence resolver (task 2.6)
# ---------------------------------------------------------------------------


def test_resolve_causation_neither_paths_nor_reason_returns_none() -> None:
    """A change with no stated cause receives no explanation."""
    assert resolve_causation([], None) is None


def test_resolve_causation_paths_only() -> None:
    """Paths without a reason render only the paths."""
    causation = resolve_causation([["settings", 0, "tier"]], None)
    assert causation is not None
    assert causation.body_paths == ["settings[0].tier"]
    assert causation.body_reason is None


def test_resolve_causation_reason_only() -> None:
    """A reason without paths renders only the reason."""
    causation = resolve_causation([], "replace_because_tainted")
    assert causation is not None
    assert not causation.body_paths
    assert causation.body_reason is not None
    assert "tainted" in causation.body_reason


def test_resolve_causation_paths_and_cannot_update_reason_suppresses_the_reason() -> None:
    """Paths plus `replace_because_cannot_update` render paths only: the reason is redundant."""
    causation = resolve_causation([["settings", 0, "tier"]], "replace_because_cannot_update")
    assert causation is not None
    assert causation.body_paths == ["settings[0].tier"]
    assert causation.body_reason is None
    assert "cannot" not in causation.summary_html


def test_resolve_causation_paths_and_other_reason_renders_both() -> None:
    """Paths plus any other reason render both, since the paths do not prove it redundant."""
    causation = resolve_causation([["settings", 0, "tier"]], "replace_by_triggers")
    assert causation is not None
    assert causation.body_paths == ["settings[0].tier"]
    assert causation.body_reason is not None
    assert "triggers" in causation.body_reason


def test_resolve_causation_paths_and_unknown_reason_renders_both() -> None:
    """An unrecognized reason alongside paths is preserved, not dropped as redundant."""
    causation = resolve_causation([["settings", 0, "tier"]], "some_future_code")
    assert causation is not None
    assert causation.body_paths == ["settings[0].tier"]
    assert causation.body_reason is not None
    assert "some_future_code" in causation.body_reason


# ---------------------------------------------------------------------------
# End-to-end hostile-path safety through resolve_causation (task 2.7 map-key case)
# ---------------------------------------------------------------------------


def test_resolve_causation_hostile_map_key_stays_structurally_safe() -> None:
    """A map key carrying a pipe, a backtick, a line feed and HTML-like text renders safely."""
    hostile_key = "a|b`c<script>\nd"
    causation = resolve_causation([["labels", hostile_key]], None)
    assert causation is not None

    body_path = causation.body_paths[0]
    assert "|" not in body_path
    assert "`" not in body_path
    assert "\n" not in body_path

    assert "<" not in causation.summary_html or "<code>" in causation.summary_html
    assert "<script>" not in causation.summary_html
    assert "\n" not in causation.summary_html


def test_resolve_causation_returns_frozen_dataclass() -> None:
    """`resolve_causation` returns the `Causation` type the report/template rely on."""
    causation = resolve_causation([["a"]], None)
    assert isinstance(causation, Causation)
