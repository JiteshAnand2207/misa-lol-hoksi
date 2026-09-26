//! Shared availability policy for the thirteen profile feature groups.
//! The data API is private behind `x-data-key`; callers must authenticate the
//! editor or administrator before forwarding management requests here.

use crate::api::AppState;
use axum::extract::{Json, Path, State};
use axum::http::{header, Method, StatusCode};
use axum::middleware::Next;
use axum::response::{IntoResponse, Response};
use axum::routing::{get, put};
use axum::{Router, extract::Request};
use chrono::{DateTime, Utc};
use serde::Deserialize;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use sqlx::{FromRow, PgPool, types::Json as SqlJson};
use uuid::Uuid;

use super::helpers::{err, settings_of, ApiResult};

#[derive(Clone, Copy)]
pub struct Definition {
    pub key: &'static str,
    pub name: &'static str,
    pub reference_tier: &'static str,
}

pub const DEFINITIONS: [Definition; 13] = [
    Definition { key: "ask_anything", name: "Ask me anything", reference_tier: "Free" },
    Definition { key: "other_side", name: "The other side", reference_tier: "Lifetime" },
    Definition { key: "night_shift", name: "The night shift", reference_tier: "Lifetime" },
    Definition { key: "daily_draw", name: "The draw", reference_tier: "Lifetime" },
    Definition { key: "time_capsule", name: "Time capsule", reference_tier: "Lifetime" },
    Definition { key: "archive", name: "The archive", reference_tier: "Free" },
    Definition { key: "moon", name: "The moon", reference_tier: "Free" },
    Definition { key: "guestbook", name: "Guestbook", reference_tier: "Free" },
    Definition { key: "neighbours", name: "Neighbours", reference_tier: "Free" },
    Definition { key: "alive", name: "Alive", reference_tier: "Free + Lifetime" },
    Definition { key: "secret_word", name: "Secret word", reference_tier: "Lifetime" },
    Definition { key: "chalkboard", name: "A chalkboard", reference_tier: "Free" },
    Definition { key: "tally", name: "The tally", reference_tier: "Free" },
];

fn definition(key: &str) -> Option<Definition> {
    DEFINITIONS.iter().copied().find(|item| item.key == key)
}

pub async fn seed_catalogue(pool: &PgPool) -> Result<(), sqlx::Error> {
    for feature in DEFINITIONS {
        let plans: Vec<String> = if feature.reference_tier == "Lifetime" {
            vec!["lifetime".into(), "supporter".into()]
        } else {
            vec!["free".into(), "lifetime".into(), "supporter".into()]
        };
        sqlx::query(
            "INSERT INTO feature_policies (key, eligible_plans) VALUES ($1,$2)
             ON CONFLICT (key) DO NOTHING",
        )
        .bind(feature.key)
        .bind(plans)
        .execute(pool)
        .await?;
    }
    Ok(())
}

#[derive(Clone, FromRow)]
struct PolicyRow {
    key: String,
    globally_enabled: bool,
    eligible_plans: Vec<String>,
    rollout_percent: i32,
    default_enabled: bool,
    version: i32,
    updated_at: DateTime<Utc>,
}

#[derive(FromRow)]
struct PageStateRow {
    requested_enabled: bool,
    version: i32,
    updated_at: DateTime<Utc>,
}

#[derive(FromRow)]
struct ContextRow {
    config: Option<SqlJson<Value>>,
    disabled_at: Option<DateTime<Utc>>,
    suspended_at: Option<DateTime<Utc>>,
    suspended_until: Option<DateTime<Utc>>,
    has_lifetime: bool,
    has_supporter: bool,
}

#[derive(FromRow)]
struct OverrideRow {
    granted: bool,
    restricted: bool,
}

#[derive(FromRow)]
struct OverrideVersionRow {
    granted: bool,
    restricted: bool,
    reason: String,
    expires_at: Option<DateTime<Utc>>,
    version: i32,
}

async fn policy_row(pool: &PgPool, key: &str) -> Result<Option<PolicyRow>, sqlx::Error> {
    sqlx::query_as::<_, PolicyRow>(
        "SELECT key, globally_enabled, eligible_plans, rollout_percent, default_enabled,
                version, updated_at FROM feature_policies WHERE key=$1",
    )
    .bind(key)
    .fetch_optional(pool)
    .await
}

async fn page_state(pool: &PgPool, user_id: Uuid, key: &str) -> Result<Option<PageStateRow>, sqlx::Error> {
    sqlx::query_as::<_, PageStateRow>(
        "SELECT requested_enabled, version, updated_at FROM feature_page_states
         WHERE user_id=$1 AND feature_key=$2",
    )
    .bind(user_id)
    .bind(key)
    .fetch_optional(pool)
    .await
}

async fn context(pool: &PgPool, user_id: Uuid) -> Result<Option<ContextRow>, sqlx::Error> {
    sqlx::query_as::<_, ContextRow>(
        "SELECT p.config, p.disabled_at, u.suspended_at, u.suspended_until,
            EXISTS(SELECT 1 FROM premium_entitlements e WHERE e.user_id=u.id
              AND e.active AND (e.expires_at IS NULL OR e.expires_at>NOW())
              AND lower(e.plan) IN ('lifetime','supporter')) AS has_lifetime,
            EXISTS(SELECT 1 FROM premium_entitlements e WHERE e.user_id=u.id
              AND e.active AND (e.expires_at IS NULL OR e.expires_at>NOW())
              AND lower(e.plan)='supporter') AS has_supporter
         FROM users u LEFT JOIN profiles p ON p.user_id=u.id WHERE u.id=$1",
    )
    .bind(user_id)
    .fetch_optional(pool)
    .await
}

async fn active_override(pool: &PgPool, user_id: Uuid, key: &str) -> Result<Option<OverrideRow>, sqlx::Error> {
    sqlx::query_as::<_, OverrideRow>(
        "SELECT granted, restricted FROM feature_page_overrides
         WHERE user_id=$1 AND feature_key=$2 AND (expires_at IS NULL OR expires_at>NOW())",
    )
    .bind(user_id)
    .bind(key)
    .fetch_optional(pool)
    .await
}

fn rollout_member(user_id: Uuid, key: &str, percent: i32) -> bool {
    if percent <= 0 { return false; }
    if percent >= 100 { return true; }
    let mut hasher = Sha256::new();
    hasher.update(user_id.as_bytes());
    hasher.update(b":");
    hasher.update(key.as_bytes());
    let digest = hasher.finalize();
    let cohort = u64::from_be_bytes(digest[0..8].try_into().expect("SHA-256 has eight bytes")) % 10_000;
    cohort < (percent as u64 * 100)
}

fn plan_eligible(plans: &[String], ctx: &ContextRow) -> bool {
    plans.iter().any(|plan| match plan.as_str() {
        "free" => true,
        "lifetime" => ctx.has_lifetime,
        "supporter" => ctx.has_supporter,
        _ => false,
    })
}

#[derive(Clone, Copy)]
struct EvalInput {
    globally_enabled: bool,
    suspended: bool,
    restricted: bool,
    plan_or_grant: bool,
    rollout_eligible: bool,
    requested_enabled: bool,
    configuration_complete: bool,
}

fn reason(input: EvalInput) -> &'static str {
    if !input.globally_enabled { "global_off" }
    else if input.suspended || input.restricted { "suspended" }
    else if !input.plan_or_grant { "plan_locked" }
    else if !input.rollout_eligible { "rollout_excluded" }
    else if !input.requested_enabled { "owner_off" }
    else if !input.configuration_complete { "configuration_incomplete" }
    else { "enabled" }
}

fn has_valid_draw_card(draw: Option<&Value>) -> bool {
    let valid = |text: &str| {
        let text = text.trim();
        !text.is_empty() && text.chars().count() <= super::draw::CARD_MAX
    };
    match draw {
        Some(Value::String(text)) => text.lines().any(valid),
        Some(Value::Array(cards)) => cards.iter().filter_map(Value::as_str).any(valid),
        _ => false,
    }
}

fn night_minutes(value: Option<&Value>) -> Option<u32> {
    match value? {
        Value::Number(number) => number.as_u64().filter(|n| *n < 1440).map(|n| n as u32),
        Value::String(raw) => {
            if let Ok(minutes) = raw.parse::<u32>() {
                return (minutes < 1440).then_some(minutes);
            }
            let (hours, minutes) = raw.split_once(':')?;
            let hours = hours.parse::<u32>().ok()?;
            let minutes = minutes.parse::<u32>().ok()?;
            (hours < 24 && minutes < 60).then_some(hours * 60 + minutes)
        }
        _ => None,
    }
}

fn valid_night_schedule(night: &Value) -> bool {
    let start = night_minutes(night.get("from"));
    let end = night_minutes(night.get("to"));
    let timezone = night.get("tz").and_then(Value::as_str)
        .is_some_and(|name| name.parse::<chrono_tz::Tz>().is_ok());
    matches!((start, end), (Some(start), Some(end)) if start != end) && timezone
}

async fn configuration_complete(pool: &PgPool, user_id: Uuid, key: &str, config: &Value) -> Result<bool, sqlx::Error> {
    let settings = settings_of(Some(config));
    match key {
        "night_shift" => {
            let Some(night) = settings.get("night") else { return Ok(false); };
            Ok(valid_night_schedule(night))
        }
        "daily_draw" => {
            Ok(has_valid_draw_card(settings.get("draw")))
        }
        "time_capsule" => {
            // Draft profile edits are separate from the explicitly published
            // snapshot; they must not change what visitors can read.
            let publication: Option<(SqlJson<Value>,)> = sqlx::query_as(
                "SELECT state FROM feature_aux WHERE user_id=$1 AND feature='capsule_publication'",
            ).bind(user_id).fetch_optional(pool).await?;
            Ok(publication.is_some_and(|row| {
                let state = row.0.0;
                state.get("published").and_then(Value::as_bool) == Some(true)
                    && state.get("text").and_then(Value::as_str).is_some_and(|text| !text.trim().is_empty())
                    && state.get("at").and_then(Value::as_str)
                        .is_some_and(|time| DateTime::parse_from_rfc3339(time).is_ok())
            }))
        }
        "secret_word" => {
            let verifier: Option<(SqlJson<Value>,)> = sqlx::query_as(
                "SELECT state FROM feature_aux WHERE user_id=$1 AND feature='secret'",
            ).bind(user_id).fetch_optional(pool).await?;
            Ok(verifier.is_some_and(|row| {
                row.0.0.get("hash").and_then(Value::as_str).is_some_and(|s| !s.is_empty())
                    && row.0.0.get("url").and_then(Value::as_str).is_some_and(|s| !s.is_empty())
            }))
        }
        "tally" => {
            let published: bool = sqlx::query_scalar(
                "SELECT EXISTS(SELECT 1 FROM feature_tally_polls WHERE user_id=$1 AND status IN ('open','closed'))",
            ).bind(user_id).fetch_one(pool).await?;
            Ok(published)
        }
        // These groups have no required published body. Their requested switch
        // is the complete configuration; their route validates specific data.
        _ => Ok(true),
    }
}

async fn effective_state(pool: &PgPool, user_id: Uuid, key: &str) -> Result<Option<Value>, sqlx::Error> {
    let Some(feature) = definition(key) else { return Ok(None); };
    let Some(ctx) = context(pool, user_id).await? else { return Ok(None); };
    let policy = policy_row(pool, key).await?;
    let state = page_state(pool, user_id, key).await?;
    let override_row = active_override(pool, user_id, key).await?;
    let requested = state.as_ref().is_some_and(|s| s.requested_enabled);
    let now = Utc::now();
    let suspended = ctx.disabled_at.is_some()
        || ctx.suspended_at.is_some()
            && ctx.suspended_until.as_ref().map_or(true, |until| until > &now);
    let configured = if let Some(config) = ctx.config.as_ref() {
        configuration_complete(pool, user_id, key, &config.0).await?
    } else { false };
    let reason_code = match policy.as_ref() {
        None => "policy_missing",
        Some(p) => reason(EvalInput {
            globally_enabled: p.globally_enabled,
            suspended,
            restricted: override_row.as_ref().is_some_and(|row| row.restricted),
            plan_or_grant: plan_eligible(&p.eligible_plans, &ctx)
                || override_row.as_ref().is_some_and(|row| row.granted),
            rollout_eligible: rollout_member(user_id, key, p.rollout_percent),
            requested_enabled: requested,
            configuration_complete: configured,
        }),
    };
    Ok(Some(json!({
        "key": feature.key,
        "name": feature.name,
        "reference_tier": feature.reference_tier,
        "requested_enabled": requested,
        "effective_enabled": reason_code == "enabled",
        "reason_code": reason_code,
        "policy_version": policy.as_ref().map(|p| p.version).unwrap_or(0),
        "config_version": state.as_ref().map(|s| s.version).unwrap_or(0),
        "updated_at": state.as_ref().map(|s| s.updated_at.clone()).or_else(|| policy.as_ref().map(|p| p.updated_at.clone())),
    })))
}

pub async fn is_effective(pool: &PgPool, user_id: Uuid, key: &str) -> Result<bool, sqlx::Error> {
    Ok(effective_state(pool, user_id, key).await?.as_ref()
        .and_then(|state| state.get("effective_enabled"))
        .and_then(Value::as_bool).unwrap_or(false))
}

fn policy_json(row: &PolicyRow, requested_profile_count: i64) -> Value {
    let feature = definition(&row.key).expect("policy row belongs to registry");
    json!({
        "key": row.key, "name": feature.name, "reference_tier": feature.reference_tier,
        "globally_enabled": row.globally_enabled, "eligible_plans": row.eligible_plans,
        "rollout_percent": row.rollout_percent, "default_enabled": row.default_enabled,
        "version": row.version, "updated_at": row.updated_at,
        "requested_profile_count": requested_profile_count,
    })
}

fn db_error(error: sqlx::Error) -> (StatusCode, Json<Value>) {
    tracing::error!(%error, "feature policy store error");
    err(StatusCode::INTERNAL_SERVER_ERROR, "store_error")
}

pub async fn catalogue(State(pool): State<PgPool>) -> ApiResult {
    let rows: Vec<(String, i64)> = sqlx::query_as(
        "SELECT feature_key, COUNT(*) FROM feature_page_states WHERE requested_enabled GROUP BY feature_key",
    ).fetch_all(&pool).await.map_err(db_error)?;
    let counts: std::collections::HashMap<String, i64> = rows.into_iter().collect();
    let mut features = Vec::with_capacity(DEFINITIONS.len());
    for feature in DEFINITIONS {
        let Some(policy) = policy_row(&pool, feature.key).await.map_err(db_error)? else {
            return Err(err(StatusCode::INTERNAL_SERVER_ERROR, "policy_missing"));
        };
        features.push(policy_json(&policy, *counts.get(feature.key).unwrap_or(&0)));
    }
    Ok(Json(json!({ "features": features })))
}

pub async fn owner_states(State(pool): State<PgPool>, Path(user_id): Path<Uuid>) -> ApiResult {
    if context(&pool, user_id).await.map_err(db_error)?.is_none() {
        return Err(err(StatusCode::NOT_FOUND, "user_not_found"));
    }
    let mut features = Vec::with_capacity(DEFINITIONS.len());
    for feature in DEFINITIONS {
        features.push(effective_state(&pool, user_id, feature.key).await.map_err(db_error)?
            .expect("known user and registry feature"));
    }
    Ok(Json(json!({ "features": features })))
}

#[derive(Deserialize)]
pub struct PolicyWrite {
    globally_enabled: bool,
    eligible_plans: Vec<String>,
    rollout_percent: i32,
    default_enabled: bool,
    expected_version: i32,
    actor_id: Option<Uuid>,
    reason: Option<String>,
}

fn normalized_plans(plans: &[String]) -> Option<Vec<String>> {
    if plans.is_empty() || plans.len() > 3 { return None; }
    let mut normalized = Vec::new();
    for plan in plans {
        let plan = plan.trim().to_ascii_lowercase();
        if !matches!(plan.as_str(), "free" | "lifetime" | "supporter") || normalized.contains(&plan) {
            return None;
        }
        normalized.push(plan);
    }
    Some(normalized)
}

pub async fn update_policy(
    State(pool): State<PgPool>, Path(key): Path<String>, Json(body): Json<PolicyWrite>,
) -> ApiResult {
    if definition(&key).is_none() { return Err(err(StatusCode::NOT_FOUND, "unknown_feature")); }
    let Some(plans) = normalized_plans(&body.eligible_plans) else {
        return Err(err(StatusCode::UNPROCESSABLE_ENTITY, "invalid_eligible_plans"));
    };
    if !(0..=100).contains(&body.rollout_percent) {
        return Err(err(StatusCode::UNPROCESSABLE_ENTITY, "invalid_rollout"));
    }
    let mut tx = pool.begin().await.map_err(db_error)?;
    let existing: Option<PolicyRow> = sqlx::query_as(
        "SELECT key, globally_enabled, eligible_plans, rollout_percent, default_enabled,
                version, updated_at FROM feature_policies WHERE key=$1 FOR UPDATE",
    ).bind(&key).fetch_optional(&mut *tx).await.map_err(db_error)?;
    let Some(before) = existing else { return Err(err(StatusCode::NOT_FOUND, "policy_missing")); };
    if before.version != body.expected_version { return Err(err(StatusCode::CONFLICT, "version_conflict")); }
    let after: PolicyRow = sqlx::query_as(
        "UPDATE feature_policies SET globally_enabled=$2, eligible_plans=$3,
         rollout_percent=$4, default_enabled=$5, version=version+1, updated_at=NOW()
         WHERE key=$1 RETURNING key, globally_enabled, eligible_plans, rollout_percent,
         default_enabled, version, updated_at",
    ).bind(&key).bind(body.globally_enabled).bind(plans).bind(body.rollout_percent)
        .bind(body.default_enabled).fetch_one(&mut *tx).await.map_err(db_error)?;
    let prior = policy_json(&before, 0);
    let next = policy_json(&after, 0);
    sqlx::query(
        "INSERT INTO feature_policy_audit (actor_id, scope, feature_key, before_state, after_state, reason)
         VALUES ($1,'global',$2,$3,$4,$5)",
    ).bind(body.actor_id).bind(&key).bind(SqlJson(prior)).bind(SqlJson(next.clone()))
        .bind(body.reason.unwrap_or_default()).execute(&mut *tx).await.map_err(db_error)?;
    tx.commit().await.map_err(db_error)?;
    Ok(Json(next))
}

#[derive(Deserialize)]
pub struct OwnerWrite {
    requested_enabled: bool,
    expected_version: i32,
}

pub async fn update_owner_state(
    State(pool): State<PgPool>, Path((user_id, key)): Path<(Uuid, String)>, Json(body): Json<OwnerWrite>,
) -> ApiResult {
    if definition(&key).is_none() { return Err(err(StatusCode::NOT_FOUND, "unknown_feature")); }
    if context(&pool, user_id).await.map_err(db_error)?.is_none() {
        return Err(err(StatusCode::NOT_FOUND, "user_not_found"));
    }
    let mut tx = pool.begin().await.map_err(db_error)?;
    let existing: Option<PageStateRow> = sqlx::query_as(
        "SELECT requested_enabled, version, updated_at FROM feature_page_states
         WHERE user_id=$1 AND feature_key=$2 FOR UPDATE",
    ).bind(user_id).bind(&key).fetch_optional(&mut *tx).await.map_err(db_error)?;
    let version = existing.as_ref().map(|state| state.version).unwrap_or(0);
    if version != body.expected_version { return Err(err(StatusCode::CONFLICT, "version_conflict")); }
    if existing.is_some() {
        sqlx::query(
            "UPDATE feature_page_states SET requested_enabled=$3, version=version+1, updated_at=NOW()
             WHERE user_id=$1 AND feature_key=$2",
        ).bind(user_id).bind(&key).bind(body.requested_enabled)
            .execute(&mut *tx).await.map_err(db_error)?;
    } else {
        let result = sqlx::query(
            "INSERT INTO feature_page_states (user_id, feature_key, requested_enabled)
             VALUES ($1,$2,$3)",
        ).bind(user_id).bind(&key).bind(body.requested_enabled)
            .execute(&mut *tx).await;
        if let Err(error) = result {
            if error.as_database_error().is_some_and(|db| db.is_unique_violation()) {
                return Err(err(StatusCode::CONFLICT, "version_conflict"));
            }
            return Err(db_error(error));
        }
    }
    sqlx::query(
        "INSERT INTO feature_policy_audit (scope, user_id, feature_key, before_state, after_state)
         VALUES ('owner',$1,$2,$3,$4)",
    ).bind(user_id).bind(&key)
        .bind(SqlJson(json!({"requested_enabled": existing.as_ref().is_some_and(|s| s.requested_enabled), "version": version})))
        .bind(SqlJson(json!({"requested_enabled": body.requested_enabled, "version": version+1})))
        .execute(&mut *tx).await.map_err(db_error)?;
    tx.commit().await.map_err(db_error)?;
    let state = effective_state(&pool, user_id, &key).await.map_err(db_error)?
        .expect("known user and registry feature");
    Ok(Json(state))
}

#[derive(Deserialize)]
pub struct OverrideWrite {
    granted: bool,
    restricted: bool,
    expires_at: Option<DateTime<Utc>>,
    reason: String,
    expected_version: i32,
    actor_id: Option<Uuid>,
}

/// Staff authorization is applied by the authenticated FastAPI admin route.
/// A grant changes eligibility only; it cannot enable the owner's page or
/// override the hard global switch, a suspension, or a rollout exclusion.
pub async fn update_override(
    State(pool): State<PgPool>, Path((user_id, key)): Path<(Uuid, String)>, Json(body): Json<OverrideWrite>,
) -> ApiResult {
    if definition(&key).is_none() { return Err(err(StatusCode::NOT_FOUND, "unknown_feature")); }
    if context(&pool, user_id).await.map_err(db_error)?.is_none() {
        return Err(err(StatusCode::NOT_FOUND, "user_not_found"));
    }
    let reason = body.reason.trim();
    if reason.is_empty() || reason.chars().count() > 500 || (body.granted && body.restricted) {
        return Err(err(StatusCode::UNPROCESSABLE_ENTITY, "invalid_override"));
    }
    if body.expires_at.as_ref().is_some_and(|expiry| expiry <= &Utc::now()) {
        return Err(err(StatusCode::UNPROCESSABLE_ENTITY, "invalid_expiry"));
    }
    let mut tx = pool.begin().await.map_err(db_error)?;
    let existing: Option<OverrideVersionRow> = sqlx::query_as(
        "SELECT granted, restricted, reason, expires_at, version FROM feature_page_overrides
         WHERE user_id=$1 AND feature_key=$2 FOR UPDATE",
    ).bind(user_id).bind(&key).fetch_optional(&mut *tx).await.map_err(db_error)?;
    let version = existing.as_ref().map(|row| row.version).unwrap_or(0);
    if version != body.expected_version { return Err(err(StatusCode::CONFLICT, "version_conflict")); }
    if existing.is_some() {
        sqlx::query(
            "UPDATE feature_page_overrides SET granted=$3, restricted=$4, reason=$5,
             expires_at=$6, version=version+1, updated_at=NOW()
             WHERE user_id=$1 AND feature_key=$2",
        ).bind(user_id).bind(&key).bind(body.granted).bind(body.restricted)
            .bind(reason).bind(body.expires_at.clone()).execute(&mut *tx).await.map_err(db_error)?;
    } else {
        let result = sqlx::query(
            "INSERT INTO feature_page_overrides
             (user_id, feature_key, granted, restricted, reason, expires_at)
             VALUES ($1,$2,$3,$4,$5,$6)",
        ).bind(user_id).bind(&key).bind(body.granted).bind(body.restricted)
            .bind(reason).bind(body.expires_at.clone()).execute(&mut *tx).await;
        if let Err(error) = result {
            if error.as_database_error().is_some_and(|db| db.is_unique_violation()) {
                return Err(err(StatusCode::CONFLICT, "version_conflict"));
            }
            return Err(db_error(error));
        }
    }
    let before = existing.as_ref().map(|row| json!({
        "granted": row.granted, "restricted": row.restricted,
        "expires_at": row.expires_at, "reason": row.reason, "version": row.version,
    })).unwrap_or_else(|| json!({"version": 0}));
    let after = json!({
        "granted": body.granted, "restricted": body.restricted,
        "expires_at": body.expires_at, "reason": reason, "version": version+1,
    });
    sqlx::query(
        "INSERT INTO feature_policy_audit (actor_id, scope, user_id, feature_key,
         before_state, after_state, reason) VALUES ($1,'override',$2,$3,$4,$5,$6)",
    ).bind(body.actor_id).bind(user_id).bind(&key).bind(SqlJson(before))
        .bind(SqlJson(after.clone())).bind(reason).execute(&mut *tx).await.map_err(db_error)?;
    tx.commit().await.map_err(db_error)?;
    let effective = effective_state(&pool, user_id, &key).await.map_err(db_error)?
        .expect("known user and registry feature");
    Ok(Json(json!({"override": after, "state": effective})))
}

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/v1/feature-policies", get(catalogue))
        .route("/v1/feature-policies/{key}", put(update_policy))
        .route("/v1/features/{user_id}/policy", get(owner_states))
        .route("/v1/features/{user_id}/policy/{key}", put(update_owner_state))
        .route("/v1/features/{user_id}/policy/{key}/override", put(update_override))
}

fn public_feature(method: &Method, section: &str, action: Option<&str>) -> Option<&'static str> {
    match (section, action, method.as_str()) {
        ("guestbook", None, "GET" | "POST") => Some("guestbook"),
        ("asks", None, "GET" | "POST") => Some("ask_anything"),
        ("drawings", None, "GET" | "POST") => Some("chalkboard"),
        ("neighbours", Some("public"), "GET") => Some("neighbours"),
        ("moon", None, "GET") => Some("moon"),
        ("night", None, "GET") => Some("night_shift"),
        ("capsule", None, "GET") => Some("time_capsule"),
        ("tally", None, "GET") | ("tally", Some("vote"), "POST") => Some("tally"),
        ("secret", None, "POST") | ("secret", Some("grant"), "GET") => Some("secret_word"),
        ("draw", None, "GET") => Some("daily_draw"),
        ("alive", None, "POST") | ("alive", Some("count"), "GET") => Some("alive"),
        ("hits", None, "GET" | "POST") => Some("alive"),
        ("reverse", None, "GET") => Some("other_side"),
        _ => None,
    }
}

// Axum can dispatch HEAD to a GET handler. Some GET handlers have one-time
// effects (such as consuming a secret grant), so never let HEAD reach them.
fn reject_feature_head(method: &Method, parts: &[&str]) -> bool {
    *method == Method::HEAD && parts.len() >= 4 && parts[0] == "v1" && parts[1] == "features"
}

pub async fn require_public_policy(State(state): State<AppState>, request: Request, next: Next) -> Response {
    let parts: Vec<&str> = request.uri().path().split('/').filter(|p| !p.is_empty()).collect();
    if reject_feature_head(request.method(), &parts) {
        return StatusCode::METHOD_NOT_ALLOWED.into_response();
    }
    if parts.len() < 4 || parts[0] != "v1" || parts[1] != "features" {
        return next.run(request).await;
    }
    let Some(key) = public_feature(request.method(), parts[3], parts.get(4).copied()) else {
        return next.run(request).await;
    };
    let Ok(user_id) = Uuid::parse_str(parts[2]) else { return next.run(request).await; };
    let allowed = is_effective(&state.pool, user_id, key).await.unwrap_or(false);
    if !allowed {
        let status = if request.method() == Method::GET { StatusCode::NOT_FOUND } else { StatusCode::FORBIDDEN };
        return (status, Json(json!({"error":"FEATURE_UNAVAILABLE"}))).into_response();
    }
    let mut response = next.run(request).await;
    response.headers_mut().insert(header::CACHE_CONTROL, "no-store".parse().expect("valid header"));
    response
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::Body;
    use tower::ServiceExt;

    fn enabled_input() -> EvalInput {
        EvalInput { globally_enabled: true, suspended: false, restricted: false,
            plan_or_grant: true, rollout_eligible: true, requested_enabled: true,
            configuration_complete: true }
    }

    #[test]
    fn all_controls_are_required_and_precedence_is_stable() {
        assert_eq!(reason(enabled_input()), "enabled");
        let mut value = enabled_input();
        value.globally_enabled = false;
        value.suspended = true;
        assert_eq!(reason(value), "global_off");
        value.globally_enabled = true;
        assert_eq!(reason(value), "suspended");
        value.suspended = false;
        value.plan_or_grant = false;
        assert_eq!(reason(value), "plan_locked");
        value.plan_or_grant = true;
        value.rollout_eligible = false;
        assert_eq!(reason(value), "rollout_excluded");
        value.rollout_eligible = true;
        value.requested_enabled = false;
        assert_eq!(reason(value), "owner_off");
        value.requested_enabled = true;
        value.configuration_complete = false;
        assert_eq!(reason(value), "configuration_incomplete");
    }

    #[test]
    fn registry_and_rollout_are_bounded() {
        assert_eq!(DEFINITIONS.len(), 13);
        assert!(definition("unknown").is_none());
        let user = Uuid::nil();
        assert!(!rollout_member(user, "guestbook", 0));
        assert!(rollout_member(user, "guestbook", 100));
        assert_eq!(rollout_member(user, "guestbook", 37), rollout_member(user, "guestbook", 37));
        assert!(normalized_plans(&["free".into(), "free".into()]).is_none());
        assert!(normalized_plans(&["custom".into()]).is_none());
    }

    #[test]
    fn draw_requires_a_card_that_the_endpoint_will_keep() {
        let overlong = "x".repeat(super::super::draw::CARD_MAX + 1);
        assert!(!has_valid_draw_card(Some(&json!(overlong))));
        assert!(!has_valid_draw_card(Some(&json!(["  ", overlong]))));
        assert!(has_valid_draw_card(Some(&json!([overlong, " a valid card "]))));
        assert!(has_valid_draw_card(Some(&json!(" a valid card "))));
    }

    #[test]
    fn night_requires_a_real_nonzero_local_interval() {
        assert!(valid_night_schedule(&json!({"from":"23:00","to":"05:00","tz":"Europe/Berlin"})));
        assert!(valid_night_schedule(&json!({"from":1380,"to":300,"tz":"UTC"})));
        assert!(!valid_night_schedule(&json!({"from":"05:00","to":"05:00","tz":"UTC"})));
        assert!(!valid_night_schedule(&json!({"from":"25:00","to":"05:00","tz":"UTC"})));
        assert!(!valid_night_schedule(&json!({"from":"23:00","to":"05:00","tz":"No/Such_Zone"})));
    }

    #[test]
    fn only_public_routes_are_gated() {
        assert_eq!(public_feature(&Method::POST, "guestbook", None), Some("guestbook"));
        assert_eq!(public_feature(&Method::GET, "guestbook", Some("inbox")), None);
        assert_eq!(public_feature(&Method::POST, "secret", Some("set")), None);
        assert_eq!(public_feature(&Method::GET, "secret", Some("grant")), Some("secret_word"));
        assert_eq!(public_feature(&Method::POST, "hits", None), Some("alive"));
    }

    #[test]
    fn head_cannot_reach_get_handlers_that_consume_grants() {
        let secret_grant = ["v1", "features", "00000000-0000-0000-0000-000000000000", "secret", "grant", "token"];
        assert!(reject_feature_head(&Method::HEAD, &secret_grant));
        assert!(!reject_feature_head(&Method::GET, &secret_grant));
        assert!(!reject_feature_head(&Method::HEAD, &["v1", "feature-policies"]));
    }

    #[tokio::test]
    async fn head_grant_route_is_rejected_without_database_access() {
        let pool = sqlx::postgres::PgPoolOptions::new()
            .connect_lazy("postgres://localhost/misa_policy_test")
            .expect("valid PostgreSQL URL");
        let state = AppState { pool, api_key: String::new() };
        let app = super::super::router(state.clone()).with_state(state);
        let request = axum::http::Request::builder()
            .method(Method::HEAD)
            .uri(format!("/v1/features/{}/secret/grant/{}", Uuid::nil(), Uuid::nil()))
            .body(Body::empty())
            .expect("valid request");
        let response = app.oneshot(request).await.expect("router response");
        assert_eq!(response.status(), StatusCode::METHOD_NOT_ALLOWED);
    }
}
