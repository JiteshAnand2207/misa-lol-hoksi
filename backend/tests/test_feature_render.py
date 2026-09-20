from datetime import datetime, timedelta, timezone

import pytest

from app.core.public_profile_html import render_public_profile
from app.core.profiles import default_public_profile
from app.features.render import feature_blocks_html, moon_phase_name, stripped_secret
from app.models import User


def make_user() -> User:
    return User(id="u1", username="odt", display_name="Otter", created_at="2025-01-01")


def base_config():
    return default_public_profile(make_user())


def render(config, *, asks=None, request=None):
    return render_public_profile(config, request=request, widgets=[], default_fonts=[], asks=asks)


def test_reverse_block_rendered_and_escaped():
    config = base_config()
    config["settings"]["reverse"] = {"title": "The Otter & Side", "text": "line one\nline two"}
    html = render(config)
    assert 'data-misa-feature="reverse"' in html
    assert "The Otter &amp; Side" in html
    assert "line one<br>line two" in html
    assert "<i>" not in html


def test_reverse_hidden_when_empty():
    config = base_config()
    config["settings"]["reverse"] = {"title": "", "text": ""}
    html = render(config)
    assert "data-misa-feature=\"reverse\"" not in html


def test_night_block_when_tz_set():
    config = base_config()
    config["settings"]["night"] = {"tz": "Europe/Sarajevo", "from": "22", "to": 6}
    html = render(config)
    assert 'data-misa-feature="night"' in html
    assert "22:00 to 06:00" in html
    assert "Europe/Sarajevo" in html


def test_draw_block():
    config = base_config()
    config["settings"]["draw"] = "A couple of notes"
    html = render(config)
    assert 'data-misa-feature="draw"' in html
    assert "A couple of notes" in html


def test_capsule_sealed_until_future():
    config = base_config()
    config["settings"]["capsule"] = {"text": "hello 2030", "at": "2030-01-01T00:00:00Z"}
    html = render(config)
    assert 'data-misa-feature="capsule"' in html
    assert "sealed" in html
    assert "hello 2030" not in html


def test_capsule_opened_shows_text():
    config = base_config()
    config["settings"]["capsule"] = {"text": "back from the past", "at": "2020-01-01T00:00:00Z"}
    html = render(config)
    assert "sealed" not in html
    assert "back from the past" in html


def test_archive_block_toggle():
    config = base_config()
    config["settings"]["archive"] = True
    assert 'data-misa-feature="archive"' in render(config)
    config["settings"]["archive"] = False
    assert 'data-misa-feature="archive"' not in render(config)


def test_neighbours_rendered_with_links():
    config = base_config()
    config["settings"]["neighbours"] = ["odt", "friend", "z<z>"]
    html = render(config)
    assert 'data-misa-feature="neighbours"' in html
    assert 'href="/odt"' in html
    assert "z&lt;z&gt;" not in html


def test_presence_block_when_enabled():
    config = base_config()
    config["settings"]["presence"] = True
    html = render(config)
    assert 'data-misa-feature="presence"' in html
    assert " UTC" in html


def test_moon_block_renders_phase():
    config = base_config()
    config["settings"]["moon"] = True
    html = render(config)
    assert 'data-misa-feature="moon"' in html
    phase = moon_phase_name(datetime.now(timezone.utc))
    assert phase in html


def test_moon_phase_known_boundaries():
    ref = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    cycle = timedelta(days=29.530588853)
    assert moon_phase_name(ref) == "New moon"
    assert moon_phase_name(ref + cycle * 0.25) == "First quarter"
    assert moon_phase_name(ref + cycle * 0.5) == "Full moon"
    assert moon_phase_name(ref + cycle * 0.75) == "Last quarter"
    assert moon_phase_name(ref + cycle * 0.4) == "Waxing gibbous"
    assert moon_phase_name(ref + cycle * 0.6) == "Waning gibbous"


def test_secret_never_leaked_in_render():
    config = base_config()
    config["settings"]["secret"] = {"word": "otterwordsz", "wordHash": "q" * 64, "url": "https://s.secret/x", "label": "here"}
    config["settings"]["moon"] = True
    html = render(config)
    assert "otterwordsz" not in html
    assert "q" * 64 not in html


def test_stripped_secret_removes_word_and_hash():
    cleaned = stripped_secret({"secret": {"word": "otto", "wordHash": "z" * 64, "url": "https://e", "label": "l"}})
    assert cleaned["secret"] == {"word": "", "wordHash": "", "url": "", "label": "", "hasSecret": True}