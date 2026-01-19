import fs from "node:fs";
import path from "node:path";

const CF_TOKEN = process.env.CLOUDFLARE_API_TOKEN;
const CF_ACCOUNT = process.env.CLOUDFLARE_ACCOUNT_ID;
const CF_NAMESPACE = process.env.CLOUDFLARE_KV_NAMESPACE_ID;

const POSTMARK_TOKEN = process.env.POSTMARK_SERVER_TOKEN;
const POSTMARK_STREAM = "broadcast";

const OUT_CSV = path.resolve("subscribers.csv");

function csvEscape(s) {
  if (s == null) return "";
  const v = String(s);
  if (/[",\n]/.test(v)) return `"${v.replace(/"/g, '""')}"`;
  return v;
}

async function cfFetch(url) {
  const res = await fetch(url, {
    headers: {
      "Authorization": `Bearer ${CF_TOKEN}`,
      "Content-Type": "application/json",
    },
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`Cloudflare API ${res.status}: ${t}`);
  }
  return res.json();
}

async function cfFetchText(url) {
  const res = await fetch(url, {
    headers: { "Authorization": `Bearer ${CF_TOKEN}` },
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`Cloudflare API ${res.status}: ${t}`);
  }
  return res.text();
}

async function listKvKeys(prefix) {
  let cursor = undefined;
  const keys = [];
  while (true) {
    const u = new URL(`https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT}/storage/kv/namespaces/${CF_NAMESPACE}/keys`);
    if (prefix) u.searchParams.set("prefix", prefix);
    u.searchParams.set("limit", "1000");
    if (cursor) u.searchParams.set("cursor", cursor);

    const j = await cfFetch(u.toString());
    if (!j.success) throw new Error(`Cloudflare keys list failed: ${JSON.stringify(j.errors || j)}`);

    keys.push(...(j.result || []).map(k => k.name));
    cursor = j.result_info?.cursor;
    if (!cursor) break;
  }
  return keys;
}

async function getKvJson(key) {
  const url = `https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT}/storage/kv/namespaces/${CF_NAMESPACE}/values/${encodeURIComponent(key)}`;
  const text = await cfFetchText(url);
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

async function postmarkGet(url) {
  const res = await fetch(url, {
    headers: {
      "Accept": "application/json",
      "X-Postmark-Server-Token": POSTMARK_TOKEN,
    },
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`Postmark API ${res.status}: ${t}`);
  }
  return res.json();
}

async function getPostmarkSuppressedEmails() {
  const suppressed = new Set();

  // Try dump endpoint first, fall back to paging if unavailable.
  const dumpUrls = [
    `https://api.postmarkapp.com/message-streams/${POSTMARK_STREAM}/suppressions/dump`,
    `https://api.postmarkapp.com/message-streams/${POSTMARK_STREAM}/suppressions/dump?format=json`,
  ];

  for (const u of dumpUrls) {
    try {
      const j = await postmarkGet(u);
      const arr = j.Suppressions || j.Results || j.Suppressed || (Array.isArray(j) ? j : null);
      if (Array.isArray(arr)) {
        for (const item of arr) {
          const email = (item.EmailAddress || item.email || item.Address || "").toLowerCase();
          if (email) suppressed.add(email);
        }
        return suppressed;
      }
    } catch {
      // ignore and fall back
    }
  }

  let offset = 0;
  const count = 500;
  while (true) {
    const u = `https://api.postmarkapp.com/message-streams/${POSTMARK_STREAM}/suppressions?count=${count}&offset=${offset}`;
    const j = await postmarkGet(u);
    const arr = j.Suppressions || j.Results || [];
    for (const item of arr) {
      const email = (item.EmailAddress || item.Email || "").toLowerCase();
      if (email) suppressed.add(email);
    }
    const total = j.TotalCount ?? j.Total ?? null;
    if (total != null) {
      offset += count;
      if (offset >= total) break;
    } else {
      if (!arr || arr.length < count) break;
      offset += count;
    }
  }
  return suppressed;
}

function isoDate(isoString) {
  if (!isoString) return "";
  const d = new Date(isoString);
  if (Number.isNaN(d.getTime())) return "";
  return d.toISOString().slice(0, 10);
}

async function main() {
  if (!CF_TOKEN || !CF_ACCOUNT || !CF_NAMESPACE) {
    throw new Error("Missing Cloudflare env vars: CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_KV_NAMESPACE_ID");
  }
  if (!POSTMARK_TOKEN) throw new Error("Missing Postmark token env var POSTMARK_SERVER_TOKEN");

  const keys = await listKvKeys("sub:");
  const kvRows = [];
  for (const key of keys) {
    const email = key.slice(4).toLowerCase();
    const rec = await getKvJson(key);
    const subscribed_at = isoDate(rec?.subscribed_at) || isoDate(rec?.last_seen_at) || "";
    const status = (rec?.status || "active").toLowerCase();
    if (email) kvRows.push({ email, subscribed_at, status });
  }

  const suppressed = await getPostmarkSuppressedEmails();

  const header = ["email", "name", "status", "subscribed_at"].join(",");
  const lines = [header];

  const byEmail = new Map();
  for (const r of kvRows) byEmail.set(r.email, r);

  const emails = Array.from(byEmail.keys()).sort();
  for (const email of emails) {
    const r = byEmail.get(email);
    const isSuppressed = suppressed.has(email);
    const kvUnsub = r.status === "unsubscribed";
    const status = (isSuppressed || kvUnsub) ? "unsubscribed" : "active";
    lines.push([csvEscape(email), "", status, csvEscape(r.subscribed_at)].join(","));
  }

  fs.writeFileSync(OUT_CSV, lines.join("\n") + "\n", "utf-8");
  console.log(`Wrote ${OUT_CSV} with ${emails.length} rows.`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
