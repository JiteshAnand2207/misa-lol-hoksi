

# CONTINUE-HERE (session 2026-09)

Dovrseno i POSVECENO (green, `backend` stablo cisto):
  - asks, guestbook, tally, presence/render sloj (misa_* tablice), doodles
    (f4a1d81), secret stripped_secret leak fix (8aa7417),
    secret JAVNI reveal endpoint mounted u api router + leak-proof testovi
    (040bd20, semantics: resolve_public_profile -> data_api.get_profile ->
    unwrap_profile_config -> sha256(word) vs RAW wordHash, rate-limit po IP;
    odgovor uvijek samo {ok, revealed, url, label}). 68 testa pass.

NEDOVRSENO (NE oznacavaj kao gotovo):
  1. Task 12 - Admin moderation FRONTEND (v2/me admin panel).
  2. regresica: `npm install` u frontend + eslint (. --max-warnings=0) + tsc --noEmit.
