import pytest

from app.features import sanitize as fs
from app.core import profile_sanitize
from app.core.profiles import default_public_profile
from app.models import User


SAMPLE = {
    "asks": True,
    "reverse": {"title": "The Otter Side", "text": "This is the <b>story</b> behind the odt."},
    "night": {"tz": "Europe/Sarajevo", "from": "22", "to": 6},
    "draw": "A couple of notes",
    "capsule": {"text": "Read me in 2030", "at": "2030-01-01T00:00:00Z"},
    "archive": True,
    "moon": True,
    "guestbook": True,
    "neighbours": ["odt", "ODT", "AnOther", "bad name!"],
    "presence": True,
    "secret": {"word": "word", "url": "https://example.com", "label": "my secret"},
    "doodles": True,
    "tally": {"q": "who wins?", "options": ["a", "b", "a", "C"]},
}


def make_user() -> User:
    return User(id="u1", username="odt", display_name="Otter", created_at="2025-01-01")


class TestSanitizeAll:
    def test_valid_input_normalized(self):
        cleaned = fs.sanitize_all(dict(SAMPLE))
        assert cleaned["asks"] is True
        assert cleaned["reverse"]["title"] == "The Otter Side"
        assert "b>" not in cleaned["reverse"]["text"]
        assert cleaned["night"] == {"tz": "Europe/Sarajevo", "from": 22, "to": 6}
        assert cleaned["capsule"]["at"] == "2030-01-01T00:00:00Z"
        assert cleaned["neighbours"] == ["odt", "another"]
        assert cleaned["secret"]["url"] == "https://example.com"
        assert cleaned["tally"]["options"] == ["a", "b", "C"]

    def test_missing_keys_get_defaults(self):
        cleaned = fs.sanitize_all({"asks": "yes"})
        assert cleaned["asks"] is False
        assert cleaned["guestbook"] is False
        assert cleaned["night"] == {"tz": "", "from": 23, "to": 5}
        assert cleaned["neighbours"] == []
        assert cleaned["tally"] == {"q": "", "options": []}
        assert cleaned["secret"] == {"word": "", "url": "", "label": ""}

    def test_non_feature_keys_pass_through(self):
        cleaned = fs.sanitize_all({"vigil": True, "replay": 3, "layout": "Modern"})
        assert cleaned["vigil"] is True
        assert cleaned["replay"] == 3
        assert cleaned["layout"] == "Modern"

    def test_garbage_values_fall_back(self):
        cleaned = fs.sanitize_all(SAMPLE | {"secret": {"word": "x" * 300}, "capsule": {"at": "not a date"}, "neighbours": ["a"], "tally": {"q": "q", "options": ["only one"]}})
        assert len(cleaned["secret"]["word"]) == 64
        assert cleaned["capsule"]["at"] == ""
        assert cleaned["neighbours"] == []
        assert cleaned["tally"] == {"q": "", "options": []}


class TestThroughProfileSanitizer:
    def test_full_pipeline(self):
        config = {
            "profile": {
                "username": "odt",
                "displayName": "Otter",
                "description": "hello",
                "location": "",
                "views": 0,
                "uid": "u1",
                "joinedAt": "2025-01-01",
            },
            "settings": dict(SAMPLE),
            "assets": {},
            "socials": [],
            "badges": [],
            "widgets": [],
            "sections": [],
        }
        cleaned = profile_sanitize.sanitize_profile_config(config)
        assert cleaned["settings"]["asks"] is True
        assert cleaned["settings"]["tally"]["q"] == "who wins?"

    def test_legacy_profile_without_features_still_works(self):
        config = {
            "profile": {"username": "odt", "displayName": "Otter"},
            "settings": {"vigil": True, "layout": "Modern"},
            "assets": {},
            "socials": [],
            "badges": [],
            "widgets": [],
            "sections": [],
        }
        cleaned = profile_sanitize.sanitize_profile_config(config)
        assert cleaned["settings"]["vigil"] is True
        assert cleaned["settings"]["layout"] == "Modern"
        assert cleaned["settings"]["asks"] is False


class TestDefaults:
    def test_default_profile_contains_feature_defaults(self):
        config = default_public_profile(make_user())
        settings = config["settings"]
        assert settings["asks"] is False
        assert settings["tally"] == {"q": "", "options": []}
        assert settings["secret"] == {"word": "", "url": "", "label": ""}

    def test_defaults_match_sanitized_empty(self):
        assert fs.defaults()["night"] == {"tz": "", "from": 23, "to": 5}
        assert fs.defaults()["neighbours"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])