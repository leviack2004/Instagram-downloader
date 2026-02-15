import pytest

from instagram_adapter import InstagramAdapterError, normalize_instagram_url


def test_normalize_standard_url():
    assert (
        normalize_instagram_url("https://m.instagram.com/p/ABC123/?utm_source=ig_web_copy_link")
        == "https://www.instagram.com/p/ABC123/"
    )


def test_rejects_non_instagram_host():
    with pytest.raises(InstagramAdapterError) as exc:
        normalize_instagram_url("https://example.com/p/ABC123/")
    assert exc.value.code == "invalid_url"


def test_rejects_unsupported_path():
    with pytest.raises(InstagramAdapterError) as exc:
        normalize_instagram_url("https://www.instagram.com/stories/foo/")
    assert exc.value.code == "unsupported_content"
