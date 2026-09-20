import pytest

from app.core.public_profile_html import render_public_profile
from app.core.profiles import default_public_profile
from app.models import User
from starlette.requests import Request


def make_user() -> User:
    return User(id="u1", username="odt", display_name="Otter", created_at="2025-01-01")


def base_config():
    return default_public_profile(make_user())


def render(config, *, asks=None, request=None):
    return render_public_profile(config, request=request, widgets=[], default_fonts=[], asks=asks)


def test_asks_disabled_no_askbox():
    config = base_config()
    config["settings"]["asks"] = False
    html = render(config, asks=[])
    assert 'data-misa-ask' not in html


def test_asks_enabled_shows_form():
    config = base_config()
    config["settings"]["asks"] = True
    html = render(config, asks=[])
    assert 'action="/api/v1/profile/odt/asks"' in html
    assert "Ask me anything" in html
    assert "No questions answered yet" in html


def test_published_asks_rendered_and_escaped():
    config = base_config()
    config["settings"]["asks"] = True
    asks = [{"id": "a1", "q": "where's the <b>otter</b>?", "a": "in the pond\nnext door"}]
    html = render(config, asks=asks)
    assert "&lt;b&gt;otter&lt;/b&gt;" in html
    assert "in the pond" in html
    assert "next door" in html


def test_sent_notice():
    config = base_config()
    config["settings"]["asks"] = True
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/odt",
        "raw_path": b"/odt",
        "query_string": b"sent=1",
        "headers": [],
        "client": ("1.2.3.4", 1),
        "server": ("misa.lol", 80),
        "scheme": "http",
    }
    request = Request(scope)
    html = render(config, asks=[], request=request)
    assert "Sent! Thanks." in html


def test_asks_none_still_renders_when_enabled_without_data():
    config = base_config()
    config["settings"]["asks"] = True
    html = render(config, asks=None)
    assert 'class="section askbox"' not in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])