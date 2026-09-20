from app.core.public_profile_html import render_public_profile
from app.core.profiles import default_public_profile
from app.models import User


def make_user() -> User:
    return User(id="u1", username="odt", display_name="Otter", created_at="2025-01-01")


def base_config():
    return default_public_profile(make_user())


def render(config, *, tally=None, request=None):
    return render_public_profile(config, request=request, widgets=[], default_fonts=[], asks=None, signatures=None, tally=tally)


def test_tally_hidden_without_data():
    config = base_config()
    config["settings"]["tally"] = {"q": "best?", "options": ["a", "b"]}
    html = render(config, tally=None)
    assert "data-misa-tally" not in html


def test_tally_renders_bars_and_form():
    config = base_config()
    config["settings"]["tally"] = {"q": "best <b>otter</b>?", "options": ["river", "pond"]}
    tally = {
        "question": "best otter?",
        "options": [{"name": "river", "count": 2}, {"name": "pond", "count": 1}],
        "total": 3,
    }
    html = render(config, tally=tally)
    assert 'data-misa-tally="1"' in html
    assert 'action="/api/v1/profile/odt/tally"' in html
    assert "best otter?" in html
    assert "<b>otter</b>" not in html
    assert 'value="river"' in html
    assert "3 votes so far" in html


def test_tally_zero_votes_shows_options():
    config = base_config()
    config["settings"]["tally"] = {"q": "best?", "options": ["a", "b"]}
    tally = {"question": "best?", "options": [{"name": "a", "count": 0}, {"name": "b", "count": 0}], "total": 0}
    html = render(config, tally=tally)
    assert 'value="a"' in html
    assert "0 votes so far" in html