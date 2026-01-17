import fs from "node:fs";
import path from "node:path";

const TOKEN = process.env.POSTMARK_SERVER_TOKEN;
const FROM = process.env.REGLAG_FROM_EMAIL;
const REPLY_TO = process.env.REGLAG_REPLY_TO;
const ENABLED = (process.env.EMAIL_SEND_ENABLED || "false").toLowerCase() === "true";

const SITE_DIR = path.resolve("publish/site");
const BRIEFINGS_DIR = path.join(SITE_DIR, "briefings");

const SUBSCRIBERS_CSV = path.resolve("subscribers.csv");
const SENT_LOG_PATH = path.resolve("email/sent-log.json");

// Postmark Broadcast stream id is typically "broadcast"
const MESSAGE_STREAM = "broadcast";

function spelledDate(yyyy_mm_dd) {
  const [y, m, d] = yyyy_mm_dd.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  return new Intl.DateTimeFormat("en-US", { month: "long", day: "numeric", year: "numeric" }).format(dt);
}

function readFile(p) {
  return fs.readFileSync(p, "utf-8");
}

function loadSentLog() {
  if (!fs.existsSync(SENT_LOG_PATH)) return {};
  return JSON.parse(readFile(SENT_LOG_PATH));
}

function saveSentLog(log) {
  fs.mkdirSync(path.dirname(SENT_LOG_PATH), { recursive: true });
  fs.writeFileSync(SENT_LOG_PATH, JSON.stringify(log, null, 2) + "\n");
}

function parseSubscribers() {
  const csv = readFile(SUBSCRIBERS_CSV).trim().split("\n");
  const header = csv.shift();
  const rows = [];
  for (const line of csv) {
    if (!line.trim()) continue;
    const [email, name, status] = line.split(",").map((s) => s.trim());
    if (!email) continue;
    rows.push({ email: email.toLowerCase(), name: name || "", status: status || "" });
  }
  return rows.filter((r) => r.status === "active");
}

function extractMainHtml(fullHtml) {
  const m = fullHtml.match(/<main[^>]*>([\s\S]*?)<\/main>/i);
  return m ? m[1] : fullHtml;
}

function detectPostType(fullHtml) {
  // Your pages include <h3 class="post-type">Weekend Deep Dive</h3> or Daily Briefing
  const m = fullHtml.match(/class="post-type"[^>]*>\s*([^<]+)\s*</i);
  return m ? m[1].trim() : "Daily Briefing";
}

function subjectFor(postType, spelled) {
  if (postType === "Weekend Deep Dive") {
    return `RegLag — Weekend Deep Dive — ${spelled}`;
  }
  return `RegLag — Daily Financial Regulatory Briefing — ${spelled}`;
}

async function postmarkSend(toEmail, subject, htmlBody) {
  const res = await fetch("https://api.postmarkapp.com/email", {
    method: "POST",
    headers: {
      "Accept": "application/json",
      "Content-Type": "application/json",
      "X-Postmark-Server-Token": TOKEN,
    },
    body: JSON.stringify({
      From: `RegLag <${FROM}>`,
      To: toEmail,
      ReplyTo: REPLY_TO,
      Subject: subject,
      HtmlBody: htmlBody,
      MessageStream: MESSAGE_STREAM,
    }),
  });

  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`Postmark send failed (${res.status}): ${txt}`);
  }
}

async function main() {
  if (!ENABLED) {
    console.log("EMAIL_SEND_ENABLED is false; skipping sends.");
    return;
  }
  if (!TOKEN || !FROM || !REPLY_TO) throw new Error("Missing required env vars/secrets.");

  // Determine “today’s briefing” as newest HTML file in publish/site/briefings/
  const htmlFiles = fs.readdirSync(BRIEFINGS_DIR).filter(f => /^\d{4}-\d{2}-\d{2}\.html$/.test(f)).sort().reverse();
  if (htmlFiles.length === 0) throw new Error("No briefing HTML files found.");

  const latestHtml = htmlFiles[0];
  const dateStr = latestHtml.replace(".html", "");

  const sentLog = loadSentLog();
  if (sentLog[dateStr]) {
    console.log(`Already sent ${dateStr}; exiting (idempotent).`);
    return;
  }

  const fullHtml = readFile(path.join(BRIEFINGS_DIR, latestHtml));
  const postType = detectPostType(fullHtml);
  const spelled = spelledDate(dateStr);
  const subject = subjectFor(postType, spelled);

  // Email body: main content only; wrapped in a simple, email-safe container
  const mainHtml = extractMainHtml(fullHtml);
  const emailHtml = `
    <div style="max-width:820px;margin:0 auto;padding:16px 18px;font-family:Georgia,serif;font-size:16px;line-height:1.6;color:#111;">
      ${mainHtml}
    </div>
  `;

  const recipients = parseSubscribers();
  if (recipients.length === 0) throw new Error("No active subscribers in subscribers.csv.");

  // Send one-by-one (simple + transparent). You can batch later if needed.
  console.log(`Sending ${dateStr} to ${recipients.length} recipients via Postmark broadcast stream...`);

  for (const r of recipients) {
    await postmarkSend(r.email, subject, emailHtml);
  }

  // Mark sent (idempotency)
  sentLog[dateStr] = { sent_at: new Date().toISOString(), count: recipients.length };
  saveSentLog(sentLog);
  console.log(`Sent + logged ${dateStr}.`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
