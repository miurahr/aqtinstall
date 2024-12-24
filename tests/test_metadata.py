import pytest

from aqt.metadata import Version, get_semantic_version


@pytest.mark.parametrize(
    "input_version, is_preview, expected",
    [
        # Test cases for non-preview versions
        ("51212", False, Version("5.12.12")),
        ("600", False, Version("6.0.0")),
        ("6_7_3", False, Version("6.7.3")),
        ("6_7", False, Version("6.7.0")),
        # Test cases for preview versions
        ("51212", True, Version("5.1212-preview")),
        ("600", True, Version("6.0-preview")),
        ("6_7_3", True, Version("6.73-preview")),
        ("6_7", True, Version("6.7-preview")),
    ],
)
def test_get_semantic_version_valid(input_version, is_preview, expected):
    """
    Test the get_semantic_version function with valid inputs.

    Args:
        input_version (str): Input version string to be converted
        is_preview (bool): Flag indicating whether this is a preview version
        expected (Version): Expected semantic version output
    """
    result = get_semantic_version(input_version, is_preview)
    assert (
        result == expected
    ), f"Failed for input '{input_version}' with is_preview={is_preview}. Expected '{expected}', but got '{result}'"


@pytest.mark.parametrize(
    "invalid_input, is_preview",
    [
        ("", False),  # Empty string
        ("abc", False),  # Non-numeric input
        ("1_2_3_4", False),  # Too many underscores
        ("1_a_2", False),  # Non-numeric parts
        (None, False),  # None input
    ],
)
def test_get_semantic_version_returns_none(invalid_input, is_preview):
    """
    Test cases where the function should return None.
    """
    result = get_semantic_version(invalid_input, is_preview)
    assert result is None, f"Expected None for invalid input '{invalid_input}', but got '{result}'"


def test_get_semantic_version_raises_value_error():
    """
    Test the specific case that raises ValueError - single digit version.
    """
    with pytest.raises(ValueError, match="Invalid version string '1'"):
        get_semantic_version("1", False)
