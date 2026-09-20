from app.core.public_profile_html import render_public_profile
from app.core.profiles import default_public_profile
from app.models import User


def make_user() -> User:
    return User(id="u1", username="odt", display_name="Otter", created_at="2025-01-01")


def base_config():
    return default_public_profile(make_user())


def render(config, *, asks=None, signatures=None, request=None):
    return render_public_profile(config, request=request, widgets=[], default_fonts=[], asks=asks, signatures=signatures)


def test_guestbook_disabled_hidden():
    config = base_config()
    config["settings"]["guestbook"] = False
    html = render(config, signatures=[])
    assert "data-misa-guest" not in html


def test_guestbook_enabled_shows_form_and_rows():
    config = base_config()
    config["settings"]["guestbook"] = True
    signatures = [
        {"id": "s1", "line": "first line", "name": "Sam", "at": "2025-01-01T00:00:00Z"},
        {"id": "s2", "line": "second <b>line</b>", "name": "", "at": "2025-02-01T00:00:00Z"},
    ]
    html = render(config, signatures=signatures)
    assert 'data-misa-guest="1"' in html
    assert 'action="/api/v1/profile/odt/guestbook"' in html
    assert "first line" in html
    assert "Sam" in html
    assert "second &lt;b&gt;line&lt;/b&gt;" in html
    assert "anonym" in html


def test_guestbook_empty_state():
    config = base_config()
    config["settings"]["guestbook"] = True
    html = render(config, signatures=[])
    assert "No signatures yet" in html


def test_guestbook_signed_notice():
    from starlette.requests import Request
    config = base_config()
    config["settings"]["guestbook"] = True
    request = Request({"type": "http", "method": "GET", "path": "/odt", "headers": [], "query_string": b"signed=1", "url": "https://misa.lol/odt?signed=1", "client": ("1.2.3.4", 1234), "server": ("misa.lol", 443)})
    html = render(config, signatures=[], request=request)
    assert "Signed! Thanks." in html