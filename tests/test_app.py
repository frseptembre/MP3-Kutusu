"""Offline tests: network/YouTube access is intentionally mocked."""
from __future__ import annotations

import sys
import types
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# The web server's converter is stubbed, so tests require no YouTube connection.
if 'yt_dlp' not in sys.modules:
    try:
        import yt_dlp  # noqa: F401
    except ModuleNotFoundError:
        fake = types.ModuleType('yt_dlp')
        fake.YoutubeDL = object
        fake.utils = types.SimpleNamespace(DownloadError=RuntimeError, ExtractorError=ValueError)
        sys.modules['yt_dlp'] = fake

import app as module

client = TestClient(module.app)


@pytest.mark.parametrize('input_url,expected', [
    ('https://www.youtube.com/watch?v=ABCDEFGHI01&t=123', 'https://www.youtube.com/watch?v=ABCDEFGHI01'),
    ('https://youtu.be/ABCDEFGHI01?si=test', 'https://www.youtube.com/watch?v=ABCDEFGHI01'),
    ('https://youtube.com/shorts/ABCDEFGHI01', 'https://www.youtube.com/watch?v=ABCDEFGHI01'),
    ('https://m.youtube.com/live/ABCDEFGHI01', 'https://www.youtube.com/watch?v=ABCDEFGHI01'),
])
def test_allowed_links(input_url, expected):
    assert module.canonical_video_url(input_url) == expected


@pytest.mark.parametrize('bad', [
    'https://youtube.com.evil.example/watch?v=ABCDEFGHI01',
    'https://www.youtube.com/playlist?list=PLfoo',
    'https://www.youtube.com/watch?v=ABCDEFGHI01&list=PLfoo&index=1#nope/??',
    'https://www.youtube.com/watch?v=x',
    'ftp://youtu.be/ABCDEFGHI01',
    'https://www.youtube.com:invalid/watch?v=ABCDEFGHI01',
    'https://evil.example/',
    'file:///etc/passwd',
    'https://www.youtube.com@evil.example/watch?v=ABCDEFGHI01',
])
def test_invalid_links(bad):
    if bad.startswith('https://www.youtube.com/watch?v=ABCDEFGHI01&list='):
        # A watch link with a playlist parameter still targets a SINGLE video.
        assert module.canonical_video_url(bad) == 'https://www.youtube.com/watch?v=ABCDEFGHI01'
        return
    with pytest.raises(ValueError):
        module.canonical_video_url(bad)


def test_filename():
    assert module.friendly_filename('Türkçe | Şarkı: A/B?') == 'Türkçe Şarkı AB.mp3'
    assert module.friendly_filename('CON') == 'YouTube ses.mp3'


def test_home_and_assets():
    assert client.get('/').status_code == 200
    assert 'Videonun sesini' in client.get('/').text
    assert client.get('/app.js').status_code == 200
    assert client.get('/styles.css').status_code == 200
    assert client.get('/health').json() == {'ok': True}


def test_bad_link_rejected_without_downloading():
    response = client.post('/api/convert', json={'url': 'https://example.com/'})
    assert response.status_code == 400


def test_password_security(monkeypatch):
    monkeypatch.setattr(module, 'APP_KEY', 'a-test-key')
    response = client.post('/api/convert', json={'url': 'https://youtu.be/ABCDEFGHI01'})
    assert response.status_code == 403


def test_download_cleans_temporary_directory(monkeypatch):
    monkeypatch.setattr(module, 'APP_KEY', 'secret')
    with TemporaryDirectory() as temp:
        directory = Path(temp) / 'job'
        directory.mkdir()
        path = directory / 'ABCDEFGHI01.mp3'
        path.write_bytes(b'ID3' + b'A' * 1024)
        with patch.object(module, 'convert_video', return_value=(directory, path, 'Güzel şarkı.mp3')):
            response = client.post('/api/convert', json={'url': 'https://youtu.be/ABCDEFGHI01'}, headers={'X-App-Key': 'secret'})
        assert response.status_code == 200
        assert response.content.startswith(b'ID3')
        assert 'attachment' in response.headers['Content-Disposition']
        assert not directory.exists()


def test_converter_creates_mp3_with_mocked_ytdlp(monkeypatch):
    class DummyYoutubeDL:
        def __init__(self, options):
            self.options = options
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def extract_info(self, url, download):
            assert download is False
            return {'duration': 120, 'title': 'Örnek şarkı'}
        def download(self, urls):
            assert len(urls) == 1
            path = Path(self.options['outtmpl'].replace('%(id)s', 'ABCDEFGHI01').replace('%(ext)s', 'mp3'))
            path.write_bytes(b'ID3' + b'A' * 200)

    monkeypatch.setattr(module.yt_dlp, 'YoutubeDL', DummyYoutubeDL)
    temp_dir, mp3, filename = module.convert_video('https://www.youtube.com/watch?v=ABCDEFGHI01')
    try:
        assert mp3.exists()
        assert filename == 'Örnek şarkı.mp3'
    finally:
        import shutil
        shutil.rmtree(temp_dir)


def test_too_long_rejected(monkeypatch):
    class DummyYoutubeDL:
        def __init__(self, options): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def extract_info(self, url, download):
            return {'duration': module.MAX_DURATION_SECONDS + 1, 'title': 'too long'}
        def download(self, urls):
            raise AssertionError('Should not download overlong videos')
    monkeypatch.setattr(module.yt_dlp, 'YoutubeDL', DummyYoutubeDL)
    with pytest.raises(module.FriendlyError, match='60 dakikalık'):
        module.convert_video('https://www.youtube.com/watch?v=ABCDEFGHI01')
