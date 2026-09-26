import logging

from src.config.logging import RedactionFilter, _mask_card_like


def test_masks_card_like_number() -> None:
    assert _mask_card_like("Card 4111111111111111 was used") == "Card ************1111 was used"


def test_masks_card_like_number_with_dashes() -> None:
    assert _mask_card_like("4111-1111-1111-1111") == "************1111"


def test_leaves_normal_text_and_short_numbers_alone() -> None:
    assert _mask_card_like("case CASE-SYN-0008, amount 850") == "case CASE-SYN-0008, amount 850"


def test_filter_redacts_log_record_message() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="card 4111111111111111 charged",
        args=(),
        exc_info=None,
    )
    RedactionFilter().filter(record)
    assert "4111111111111111" not in record.msg
    assert record.msg.endswith("1111 charged")
