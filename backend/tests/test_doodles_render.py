from app.core.public_profile_html import render_public_profile
from app.core.profiles import default_public_profile
from app.models import User


def make_user() -> User:
    return User(id="u1", username="odt", display_name="Otter", created_at="2025-01-01")


def base_config():
    return default_public_profile(make_user())


def render(config, *, doodles=None, request=None):
    return render_public_profile(config, request=request, widgets=[], default_fonts=[], asks=None, signatures=None, tally=None, doodles=doodles)


def test_doodles_disabled_hidden():
    config = base_config()
    config["settings"]["doodles"] = False
    html = render(config, doodles=[])
    assert "data-misa-doodles" not in html


def test_doodles_wall_and_canvas():
    config = base_config()
    config["settings"]["doodles"] = True
    doodles = [{"id": "d1", "svg": "data:image/png;base64,QQ==", "at": "2025-01-01T00:00:00Z"}]
    html = render(config, doodles=doodles)
    assert 'data-misa-doodles="1"' in html
    assert "data:image/png;base64,QQ==" in html
    assert 'id="doodle-canvas"' in html
    assert "/api/v1/profile/odt/doodles" in html


def test_doodles_empty_wall():
    config = base_config()
    config["settings"]["doodles"] = True
    html = render(config, doodles=[])
    assert "The wall is blank" in html