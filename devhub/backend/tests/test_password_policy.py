"""Unicode length boundaries shared with frontend password-policy tests."""

import pytest

from devhub.passwords import validate_password


@pytest.mark.parametrize(
    "value,accepted",
    [
        ("Aa1!😀😀", False),
        ("Aa1!" + "😀" * 3, False),
        ("Aa1!" + "😀" * 4, True),
        ("Aa1!" + "😀" * 124, True),
        ("Aa1!" + "😀" * 125, False),
        ("Aa1!" + "a" * 124, True),
        ("Aa1!" + "a" * 125, False),
        ("Aa1!e\u0301e\u0301", True),
    ],
)
def test_password_length_counts_unicode_code_points(value, accepted):
    if accepted:
        assert validate_password(value) == value
    else:
        with pytest.raises(ValueError):
            validate_password(value)
