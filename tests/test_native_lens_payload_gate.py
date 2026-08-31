import pytest

from run_darkpipe_kids_native_lens_v016 import (
    PUBLISHED_TARGET_COUNT,
    require_authoritative_native_selection,
)


def test_native_pair_payload_gate_accepts_only_complete_exact_selection() -> None:
    require_authoritative_native_selection(
        valid_native_rows=1_239_422,
        bright_rows=1_239_422,
        selected_rows=PUBLISHED_TARGET_COUNT,
    )


@pytest.mark.parametrize(
    ("valid_rows", "bright_rows", "selected_rows", "message"),
    [
        (1_239_150, 1_239_422, PUBLISHED_TARGET_COUNT, "coverage is incomplete"),
        (1_239_422, 1_239_422, 106_876, "selection diverges"),
    ],
)
def test_native_pair_payload_gate_rejects_non_authoritative_inputs(
    valid_rows: int, bright_rows: int, selected_rows: int, message: str
) -> None:
    with pytest.raises(RuntimeError, match=message):
        require_authoritative_native_selection(
            valid_native_rows=valid_rows,
            bright_rows=bright_rows,
            selected_rows=selected_rows,
        )
