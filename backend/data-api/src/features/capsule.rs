use super::helpers::*;
use axum::extract::{Path, State};
use axum::http::StatusCode;
use chrono::{DateTime, Utc};
use serde_json::{json, Value};
use sqlx::PgPool;
use uuid::Uuid;

pub const BODY_MAX: usize = 5000;

/// Render only the explicitly published snapshot. A prior openedAt marker
/// never overrides the release timestamp of the current publication.
fn public_payload(
    now: DateTime<Utc>,
    label: &str,
    at: &str,
    body: &str,
    opened_at: Option<&str>,
) -> (Value, bool) {
    let release = DateTime::parse_from_rfc3339(at).ok().map(|time| time.with_timezone(&Utc));
    let Some(release) = release else {
        return (json!({ "state": "sealed", "label": label, "at": at, "body": null, "raised": false }), false);
    };
    if now < release {
        return (json!({ "state": "sealed", "label": label, "at": at, "body": null, "raised": false }), false);
    }
    let prior_open = opened_at
        .and_then(|value| DateTime::parse_from_rfc3339(value).ok())
        .map(|time| time.with_timezone(&Utc))
        .filter(|time| time >= &release && time <= &now);
    let already_open = prior_open.is_some();
    let opened = prior_open.unwrap_or(now);
    (json!({
        "state": "open",
        "label": label,
        "opened_at": opened.to_rfc3339(),
        "body": body,
        "raised": already_open,
    }), !already_open)
}

pub async fn public_view(State(pool): State<PgPool>, Path(user_id): Path<Uuid>) -> ApiResult {
    if !super::policy::is_effective(&pool, user_id, "time_capsule").await.unwrap_or(false) {
        return Err(err(StatusCode::NOT_FOUND, "feature_off"));
    }
    let published = get_aux(&pool, &user_id, "capsule_publication").await;
    if published.get("published").and_then(Value::as_bool) != Some(true) {
        return Err(err(StatusCode::NOT_FOUND, "feature_off"));
    }
    let label = published.get("label").and_then(Value::as_str).unwrap_or("");
    let at = published.get("at").and_then(Value::as_str).unwrap_or("");
    let body = published.get("text").and_then(Value::as_str).unwrap_or("");
    let opened = get_aux(&pool, &user_id, "capsule_open").await;
    let (payload, newly_opened) = public_payload(
        Utc::now(), label, at, body, opened.get("openedAt").and_then(Value::as_str),
    );
    if newly_opened {
        if let Some(opened_at) = payload.get("opened_at") {
            set_aux(&pool, &user_id, "capsule_open", &json!({"openedAt": opened_at})).await;
        }
    }
    ok(payload)
}

pub async fn publish(State(pool): State<PgPool>, Path(user_id): Path<Uuid>) -> ApiResult {
    let Some(config) = read_config(&pool, &user_id).await else {
        return Err(err(StatusCode::NOT_FOUND, "profile_not_found"));
    };
    let settings = settings_of(Some(&config));
    let capsule = settings.get("capsule").cloned().unwrap_or_else(|| json!({}));
    let body = capsule.get("text").and_then(Value::as_str).unwrap_or("");
    let at = capsule.get("at").and_then(Value::as_str).unwrap_or("");
    let label = capsule.get("label").and_then(Value::as_str).unwrap_or("");
    if body.trim().is_empty() || body.chars().count() > BODY_MAX || DateTime::parse_from_rfc3339(at).is_err() {
        return Err(err(StatusCode::UNPROCESSABLE_ENTITY, "invalid_capsule"));
    }
    let snapshot = json!({ "published": true, "text": body, "at": at, "label": label });
    let mut tx = pool.begin().await.map_err(|_| err(StatusCode::INTERNAL_SERVER_ERROR, "store_error"))?;
    sqlx::query(
        "INSERT INTO feature_aux (user_id, feature, state, updated_at)
         VALUES ($1,'capsule_publication',$2,NOW())
         ON CONFLICT (user_id,feature) DO UPDATE
         SET state=EXCLUDED.state, updated_at=NOW()",
    ).bind(user_id).bind(sqlx::types::Json(snapshot))
        .execute(&mut *tx).await.map_err(|_| err(StatusCode::INTERNAL_SERVER_ERROR, "store_error"))?;
    // Reset the opened marker in the same transaction. A previous capsule
    // cannot grant early access to a newly scheduled body.
    sqlx::query(
        "INSERT INTO feature_aux (user_id, feature, state, updated_at)
         VALUES ($1,'capsule_open','{}'::jsonb,NOW())
         ON CONFLICT (user_id,feature) DO UPDATE
         SET state='{}'::jsonb, updated_at=NOW()",
    ).bind(user_id).execute(&mut *tx).await
        .map_err(|_| err(StatusCode::INTERNAL_SERVER_ERROR, "store_error"))?;
    tx.commit().await.map_err(|_| err(StatusCode::INTERNAL_SERVER_ERROR, "store_error"))?;
    ok(json!({ "ok": true, "state": "published" }))
}

pub async fn unpublish(State(pool): State<PgPool>, Path(user_id): Path<Uuid>) -> ApiResult {
    sqlx::query(
        "UPDATE feature_aux SET state=jsonb_set(state,'{published}','false'::jsonb,true), updated_at=NOW()
         WHERE user_id=$1 AND feature='capsule_publication'",
    ).bind(user_id).execute(&pool).await
        .map_err(|_| err(StatusCode::INTERNAL_SERVER_ERROR, "store_error"))?;
    ok(json!({ "ok": true, "state": "unpublished" }))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stale_open_marker_cannot_unseal_a_future_publication() {
        let now = DateTime::parse_from_rfc3339("2026-09-26T12:00:00Z").unwrap().with_timezone(&Utc);
        let (payload, opened) = public_payload(
            now, "new label", "2026-10-01T00:00:00Z", "new private body",
            Some("2026-09-01T00:00:00Z"),
        );
        assert_eq!(payload.get("state"), Some(&json!("sealed")));
        assert_eq!(payload.get("body"), Some(&Value::Null));
        assert!(!opened);
    }

    #[test]
    fn current_release_opens_without_reusing_an_old_marker() {
        let now = DateTime::parse_from_rfc3339("2026-10-01T00:00:00Z").unwrap().with_timezone(&Utc);
        let (payload, opened) = public_payload(
            now, "label", "2026-10-01T00:00:00Z", "new body",
            Some("2026-09-01T00:00:00Z"),
        );
        assert_eq!(payload.get("body"), Some(&json!("new body")));
        assert_eq!(payload.get("raised"), Some(&json!(false)));
        assert!(opened);
    }
}
