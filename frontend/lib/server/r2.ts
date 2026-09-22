import "server-only";

import { DeleteObjectCommand, PutObjectCommand, S3Client } from "@aws-sdk/client-s3";

function required(name: string) {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required for R2 uploads.`);
  return value;
}

let client: S3Client | undefined;

function r2() {
  if (!client) {
    client = new S3Client({
      region: "auto",
      endpoint: required("R2_ENDPOINT"),
      credentials: { accessKeyId: required("R2_ACCESS_KEY_ID"), secretAccessKey: required("R2_SECRET_ACCESS_KEY") },
    });
  }
  return client;
}

export function r2Enabled() {
  return Boolean(
    process.env.R2_ENDPOINT &&
    process.env.R2_BUCKET &&
    process.env.R2_ACCESS_KEY_ID &&
    process.env.R2_SECRET_ACCESS_KEY &&
    process.env.R2_PUBLIC_BASE_URL
  );
}

export function r2PublicUrl(key: string) {
  return `${required("R2_PUBLIC_BASE_URL").replace(/\/+$/, "")}/${key.split("/").map(encodeURIComponent).join("/")}`;
}

export async function uploadToR2(key: string, body: Uint8Array, contentType: string) {
  await r2().send(new PutObjectCommand({
    Bucket: required("R2_BUCKET"),
    Key: key,
    Body: body,
    ContentType: contentType,
    CacheControl: "public, max-age=31536000, immutable",
  }));
  return r2PublicUrl(key);
}

export async function deleteFromR2(key: string) {
  if (!r2Enabled()) return;
  await r2().send(new DeleteObjectCommand({
    Bucket: required("R2_BUCKET"),
    Key: key,
  })).catch(() => {});
}
