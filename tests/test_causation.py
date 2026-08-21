"""Tests for tf_peek.causation."""

from typing import Any

import pytest

from tf_peek.causation import (
    escape_in_code_span,
    escape_in_html,
    escape_in_markdown,
    phrase_reason,
    render_forcing_path,
    render_forcing_paths,
    resolve_causation,
)
from tf_peek.diff import Marker

_NO_SENSITIVITY: tuple[Marker, Marker] = (False, False)

# ---------------------------------------------------------------------------
# Path rendering notation (task 2.2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        pytest.param(["tier"], "tier", id="single-identifier-has-no-leading-dot"),
        pytest.param(["settings", 0, "tier"], "settings[0].tier", id="mixed-name-index-name"),
        pytest.param(["labels", "kubernetes.io/role"], 'labels["kubernetes.io/role"]', id="non-identifier-key"),
        pytest.param(["m", "0"], 'm["0"]', id="numeric-string-key-stays-a-string"),
        pytest.param(["a", -1], "a[-1]", id="negative-index"),
        pytest.param(["a", 1.5], "a[1.5]", id="float-step-falls-back-to-json"),
        pytest.param([True], "[true]", id="bool-step-is-not-an-index"),
        pytest.param(["a", None], "a[null]", id="null-step-falls-back-to-json"),
    ],
)
def test_render_forcing_path(path: list[Any], expected: str) -> None:
    """A forcing path renders in HCL attribute-path notation with no leading separator."""
    assert render_forcing_path(path) == expected


# ---------------------------------------------------------------------------
# Sorting, de-duplication and empty paths (task 2.3)
# ---------------------------------------------------------------------------


def test_render_forcing_paths_sorts_by_rendered_form() -> None:
    """Paths render in ascending lexical order of their rendered text, not plan order."""
    assert render_forcing_paths([["zebra"], ["apple"], ["mango"]]) == ["apple", "mango", "zebra"]


def test_render_forcing_paths_deduplicates_by_rendered_form() -> None:
    """A path stated more than once renders exactly once."""
    assert render_forcing_paths([["settings", 0, "tier"], ["settings", 0, "tier"]]) == ["settings[0].tier"]


def test_render_forcing_paths_drops_paths_that_render_to_nothing() -> None:
    """An empty step array is dropped, so it can never emit an empty code span."""
    assert render_forcing_paths([[], ["ami"]]) == ["ami"]


# ---------------------------------------------------------------------------
# Sensitivity truncation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "markers", "expected"),
    [
        pytest.param(
            ["password"],
            ({"password": True}, {"password": True}),
            ["password"],
            id="named-attribute-is-still-shown",
        ),
        pytest.param(
            ["environment", "STRIPE_LIVE_KEY"],
            ({"environment": True}, {"environment": True}),
            ["environment"],
            id="descent-into-masked-value-is-truncated",
        ),
        pytest.param(
            ["tags", "secret"],
            (False, {"tags": {"secret": True}}),
            ["tags"],
            id="union-of-both-sides-and-nested-marker",
        ),
        pytest.param(
            ["items", 1, "key"],
            (False, {"items": [False, True]}),
            ["items"],
            id="marker-nested-under-a-list-still-masks-the-attribute",
        ),
        pytest.param(
            [0, "key"],
            (True, False),
            ["[0].key"],
            id="non-name-first-step-is-left-alone",
        ),
        pytest.param(
            ["settings", 0, "tier"],
            ({"other": True}, False),
            ["settings[0].tier"],
            id="unrelated-marker-leaves-the-path-intact",
        ),
        pytest.param(
            ["settings", 0, "tier"],
            (True, False),
            ["settings"],
            id="whole-object-marker-truncates-to-the-attribute",
        ),
    ],
)
def test_render_forcing_paths_truncates_at_masked_values(
    path: list[Any],
    markers: tuple[Marker, Marker],
    expected: list[str],
) -> None:
    """A path is cut to its attribute name whenever that attribute's value is masked."""
    assert render_forcing_paths([path], sensitivity=markers) == expected


def test_render_forcing_paths_keeps_full_path_when_sensitivity_is_waived() -> None:
    """Under `--show-sensitive` there is nothing to hide, so the path renders in full."""
    paths = [["environment", "STRIPE_LIVE_KEY"]]
    assert render_forcing_paths(paths, sensitivity=None) == ["environment.STRIPE_LIVE_KEY"]


# ---------------------------------------------------------------------------
# Escaping, one function per rendering context (task 2.4)
# ---------------------------------------------------------------------------


def test_escape_in_code_span_neutralizes_only_the_backtick() -> None:
    """Inside a code span only the delimiter can break out, and entities are not decoded there."""
    assert escape_in_code_span("a`b") == r"a\u0060b"


def test_escape_in_code_span_leaves_a_pipe_untouched() -> None:
    """A pipe is ordinary text in a paragraph, so escaping it would only mutate the report."""
    assert escape_in_code_span("a|b") == "a|b"


def test_escape_in_code_span_collapses_line_breaks() -> None:
    """CR, LF and CRLF all collapse so the fragment stays on one physical line."""
    assert escape_in_code_span("a\nb") == "a\\nb"
    assert escape_in_code_span("a\r\nb") == "a\\nb"
    assert escape_in_code_span("a\rb") == "a\\nb"


def test_escape_in_markdown_neutralizes_html_and_code_delimiters_as_entities() -> None:
    """Markdown prose is HTML-capable, and an entity is inert yet still displays the character."""
    assert escape_in_markdown("</details> & `x`") == "&lt;/details> &amp; &#96;x&#96;"


def test_escape_in_markdown_collapses_line_breaks() -> None:
    """A raw line break cannot split the paragraph out of its detail block."""
    assert "\n" not in escape_in_markdown("a\nb")


def test_escape_in_html_escapes_the_full_markup_set() -> None:
    """`<summary>` is raw HTML, so every markup character is entity-encoded."""
    assert escape_in_html('<b>&"</b>') == "&lt;b&gt;&amp;&quot;&lt;/b&gt;"


def test_escape_in_html_collapses_line_breaks() -> None:
    """A raw line break cannot break the collapsed `<summary>` line across physical lines."""
    assert "\n" not in escape_in_html("a\nb")


# ---------------------------------------------------------------------------
# Reason phrasing (task 2.5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected_fragment"),
    [
        pytest.param("replace_because_tainted", "the resource is tainted", id="tainted"),
        pytest.param("replace_by_request", "explicitly requested when the plan was created", id="by-request"),
        pytest.param("replace_by_triggers", "configured replacement triggers", id="by-triggers"),
        pytest.param(
            "delete_because_no_resource_config",
            "Terraform found no corresponding resource configuration",
            id="no-resource-config",
        ),
        pytest.param("delete_because_wrong_repetition", "addressing mode", id="wrong-repetition"),
        pytest.param("delete_because_count_index", "count index is out of range", id="count-index"),
        pytest.param("delete_because_each_key", "for_each key no longer matches", id="each-key"),
        pytest.param("delete_because_no_module", "containing module instance is no longer declared", id="no-module"),
        pytest.param("delete_because_no_move_target", "moved block", id="no-move-target"),
    ],
)
def test_phrase_reason_known_codes_are_neutral_prose(code: str, expected_fragment: str) -> None:
    """Every phrasable non-read reason code renders as neutral prose, not the raw code."""
    phrase = phrase_reason(code)
    assert expected_fragment in phrase
    assert code not in phrase
    for judgment in ("expected", "unexpected", "intentional", "accidental", "dangerous"):
        assert judgment not in phrase


def test_phrase_reason_unknown_code_passes_through_marked_as_such() -> None:
    """An unrecognized code is echoed verbatim behind a preamble marking it as passed through."""
    phrase = phrase_reason("delete_because_a_future_terraform_release")
    assert "delete_because_a_future_terraform_release" in phrase
    assert "reported by Terraform" in phrase


def test_phrase_reason_cannot_update_falls_through_to_the_passthrough() -> None:
    """The provider-cannot-update code carries no phrasing: Terraform only states it beside paths."""
    assert "reported by Terraform" in phrase_reason("replace_because_cannot_update")


# ---------------------------------------------------------------------------
# Replacement mechanism
# ---------------------------------------------------------------------------


def test_resolve_causation_states_destroy_first_mechanism_without_a_consequence() -> None:
    """Destroy-then-create states the mechanism and asserts no consequence."""
    causation = resolve_causation([], None, mechanism="destroy_first", sensitivity=_NO_SENSITIVITY)
    assert causation is not None
    assert causation.mechanism == "the existing object is destroyed before its replacement is created"
    for consequence in ("downtime", "data loss", "outage", "unsafe"):
        assert consequence not in causation.mechanism


def test_resolve_causation_states_create_first_mechanism() -> None:
    """Create-before-destroy states the opposite mechanism."""
    causation = resolve_causation([], None, mechanism="create_first", sensitivity=_NO_SENSITIVITY)
    assert causation is not None
    assert causation.mechanism == "the replacement is created before the existing object is destroyed"


def test_resolve_causation_omits_the_mechanism_from_the_summary_line() -> None:
    """The mechanism is body-only: the collapsed line carries paths and reason, nothing else."""
    causation = resolve_causation([["ami"]], None, mechanism="destroy_first", sensitivity=_NO_SENSITIVITY)
    assert causation is not None
    assert causation.summary_paths == ["ami"]
    assert causation.reason is None


# ---------------------------------------------------------------------------
# Precedence resolver (task 2.6)
# ---------------------------------------------------------------------------


def test_resolve_causation_neither_paths_nor_reason_nor_mechanism_returns_none() -> None:
    """A change with no stated cause and no mechanism receives no explanation."""
    assert resolve_causation([], None, mechanism=None, sensitivity=_NO_SENSITIVITY) is None


def test_resolve_causation_paths_only() -> None:
    """Paths without a reason render only the paths."""
    causation = resolve_causation(
        [["settings", 0, "tier"]], None, mechanism="destroy_first", sensitivity=_NO_SENSITIVITY
    )
    assert causation is not None
    assert causation.paths == ["settings[0].tier"]
    assert causation.reason is None


def test_resolve_causation_reason_only() -> None:
    """A reason without paths renders only the reason."""
    causation = resolve_causation(
        [], "replace_because_tainted", mechanism="destroy_first", sensitivity=_NO_SENSITIVITY
    )
    assert causation is not None
    assert not causation.paths
    assert causation.reason is not None
    assert "tainted" in causation.reason


def test_resolve_causation_paths_and_cannot_update_reason_suppresses_the_reason() -> None:
    """Paths plus `replace_because_cannot_update` render paths only: the reason is redundant."""
    causation = resolve_causation(
        [["engine_version"]], "replace_because_cannot_update", mechanism="destroy_first", sensitivity=_NO_SENSITIVITY
    )
    assert causation is not None
    assert causation.paths == ["engine_version"]
    assert causation.reason is None


def test_resolve_causation_paths_and_other_reason_renders_both() -> None:
    """Paths plus any other reason render both, since the paths do not prove it redundant."""
    causation = resolve_causation(
        [["ami"]], "replace_by_triggers", mechanism="destroy_first", sensitivity=_NO_SENSITIVITY
    )
    assert causation is not None
    assert causation.paths == ["ami"]
    assert causation.reason is not None
    assert "triggers" in causation.reason


def test_resolve_causation_paths_and_unknown_reason_renders_both() -> None:
    """An unrecognized reason alongside paths is preserved, not dropped as redundant."""
    causation = resolve_causation(
        [["ami"]], "replace_because_some_future_code", mechanism="destroy_first", sensitivity=_NO_SENSITIVITY
    )
    assert causation is not None
    assert causation.paths == ["ami"]
    assert causation.reason is not None
    assert "replace_because_some_future_code" in causation.reason


def test_resolve_causation_ignores_forcing_paths_when_the_change_is_not_a_replacement() -> None:
    """A forcing path explains a replacement; labelling one elsewhere would assert a false one."""
    causation = resolve_causation([["ami"]], "delete_because_each_key", mechanism=None, sensitivity=_NO_SENSITIVITY)
    assert causation is not None
    assert not causation.paths
    assert causation.reason is not None
    assert "for_each" in causation.reason


def test_resolve_causation_treats_an_empty_reason_as_absent() -> None:
    """An empty reason string states nothing, so it gets no sentence rather than an empty quote."""
    assert resolve_causation([], "", mechanism=None, sensitivity=_NO_SENSITIVITY) is None


# ---------------------------------------------------------------------------
# Collapsed summary-line bounds
# ---------------------------------------------------------------------------


def test_resolve_causation_caps_the_summary_paths_by_count() -> None:
    """The summary line shows a bounded number of paths and counts the remainder."""
    paths = [["alpha"], ["bravo"], ["delta"], ["mango"], ["zeta"]]
    causation = resolve_causation(paths, None, mechanism="destroy_first", sensitivity=_NO_SENSITIVITY)
    assert causation is not None
    assert causation.summary_paths == ["alpha", "bravo", "delta"]
    assert causation.summary_remainder == len(paths) - len(causation.summary_paths)
    assert len(causation.paths) == len(paths)


def test_resolve_causation_caps_the_summary_paths_by_rendered_length() -> None:
    """A long map key cannot push the resource address off the collapsed line."""
    long_key = "k" * 200
    causation = resolve_causation(
        [["labels", long_key], ["zeta"]], None, mechanism="destroy_first", sensitivity=_NO_SENSITIVITY
    )
    assert causation is not None
    assert len(causation.summary_paths) == 1
    assert causation.summary_paths[0].endswith("…")
    assert len(causation.summary_paths[0]) < len(long_key)
    assert causation.summary_remainder == 1
    assert causation.paths[1] == "zeta"
