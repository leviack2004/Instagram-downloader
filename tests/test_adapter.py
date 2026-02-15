import pytest

from instagram_adapter import InstagramAdapterError, _extract_media_urls, normalize_instagram_url


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


def test_extracts_video_from_og_meta_fallback():
    page = '''
    <html><head>
      <meta property="og:video" content="https://video.cdn.example/reel.mp4" />
      <meta property="og:image" content="https://image.cdn.example/thumb.jpg" />
    </head></html>
    '''

    items = _extract_media_urls(page)

    assert len(items) == 2
    assert items[0].media_type == "video"
    assert items[0].url == "https://video.cdn.example/reel.mp4"


def test_extracts_escaped_video_url():
    page = r'"video_url":"https:\/\/video.cdn.example\/abc.mp4?x=1\u0026y=2"'

    items = _extract_media_urls(page)

    assert len(items) == 1
    assert items[0].media_type == "video"
    assert items[0].url == "https://video.cdn.example/abc.mp4?x=1&y=2"
