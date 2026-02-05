import fs from "node:fs";
import path from "node:path";

const TOKEN = process.env.POSTMARK_SERVER_TOKEN;
const FROM = process.env.REGLAG_FROM_EMAIL;
const REPLY_TO = process.env.REGLAG_REPLY_TO;
const ENABLED = (process.env.EMAIL_SEND_ENABLED || "false").toLowerCase() === "true";

const SITE_URL = "https://reglag.com";

const SITE_DIR = path.resolve("publish/site");
const BRIEFINGS_DIR = path.join(SITE_DIR, "briefings");

const SUBSCRIBERS_CSV = path.resolve("subscribers.csv");
const SENT_LOG_PATH = path.resolve("email/sent-log.json");

// Postmark message stream for compliant unsubscribe handling
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
  csv.shift(); // header
  const rows = [];
  for (const line of csv) {
    if (!line.trim()) continue;
    // naive CSV parse (matches our simple format)
    const [email, name, status] = line.split(",").map((s) => (s || "").trim());
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
  const m = fullHtml.match(/class="post-type"[^>]*>\s*([^<]+)\s*</i);
  return m ? m[1].trim() : "Daily Briefing";
}

function subjectFor(postType, spelled) {
  if (postType === "Weekend Deep Dive") {
    return `RegLag — Weekend Deep Dive — ${spelled}`;
  }
  return `RegLag — Daily Financial Regulatory Briefing — ${spelled}`;
}

/**
 * Email hygiene transforms:
 * - remove the PDF download link block (pdf-link) from email
 * - make all root-relative links absolute (href="/x" -> "https://reglag.com/x")
 */
function normalizeEmailHtml(html) {
  // Remove pdf-link paragraphs
  html = html.replace(/<p[^>]*class="pdf-link"[^>]*>[\s\S]*?<\/p>/gi, "");

  // Make href/src absolute for root-relative URLs
  html = html.replace(/\s(href|src)=["']\/(?!\/)([^"']+)["']/gi, (match, attr, rest) => {
    return ` ${attr}="${SITE_URL}/${rest}"`;
  });

  return html;
}

/**
 * Some email clients strip or ignore <style> blocks.
 * Inline key typography on headings to ensure consistent rendering.
 */
function applyInlineEmailStyles(html) {
  const h1Style = 'style="font-size:16px !important; line-height:1.2 !important; margin:0 0 10px 0 !important; font-weight:600 !important; letter-spacing:-0.005em !important; font-family:Georgia, serif !important;"';
  const h2Style = 'style="font-size:16px !important; line-height:1.25 !important; margin:20px 0 8px 0 !important; font-weight:600 !important; font-family:Georgia, serif !important;"';
  const h3Style = 'style="font-size:14px !important; line-height:1.25 !important; margin:16px 0 6px 0 !important; font-weight:600 !important; font-family:Georgia, serif !important;"';

  // Demote TL;DR from heading to label in email
  html = html.replace(/<h2[^>]*>\s*TL;DR\s*<\/h2>/gi,
    '<p style="font-size:13px; font-weight:600; margin:12px 0 4px 0; font-family: Georgia, serif !important;">TL;DR</p>'
  );

  // Handle bare tags and tags with attributes separately to avoid malformed markup.
  html = html.replace(/<h1>/gi, `<h1 ${h1Style}>`);
  html = html.replace(/<h1\s+/gi, `<h1 ${h1Style} `);

  html = html.replace(/<h2>/gi, `<h2 ${h2Style}>`);
  html = html.replace(/<h2\s+/gi, `<h2 ${h2Style} `);

  html = html.replace(/<h3>/gi, `<h3 ${h3Style}>`);
  html = html.replace(/<h3\s+/gi, `<h3 ${h3Style} `);

  return html;
}


async function postmarkSend(toEmail, subject, htmlBody) {
  const res = await fetch("https://api.postmarkapp.com/email", {
    method: "POST",
    headers: {
      Accept: "application/json",
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

  const htmlFiles = fs
    .readdirSync(BRIEFINGS_DIR)
    .filter((f) => /^\d{4}-\d{2}-\d{2}\.html$/.test(f))
    .sort()
    .reverse();

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

  const mainHtmlRaw = extractMainHtml(fullHtml);
  const mainHtml = applyInlineEmailStyles(normalizeEmailHtml(mainHtmlRaw));

  // Email-safe typography overrides (tighten H1 + spacing)
  const emailCss = `
    <style>
      /* Basic reset */
      body { margin: 0; padding: 0; }
      h1 {
      font-size: 16px !important;
      line-height: 1.2 !important;
      margin: 0 0 10px 0 !important;
      font-weight: 600 !important;
      letter-spacing: -0.005em !important;
      font-family: Georgia, serif !important;
    }

    h1 * {
      font-size: inherit !important;
      line-height: inherit !important;
    }
      h2 { font-size: 16px; line-height: 1.25; margin: 20px 0 8px 0; }
      h3 { font-size: 14px; line-height: 1.25; margin: 16px 0 6px 0; }
      p { margin: 0 0 10px 0; }
      ul, ol { margin: 0 0 10px 18px; padding: 0; }
      li { margin: 0 0 6px 0; }
      a { color: inherit; text-decoration: none; }
      a:hover { text-decoration: underline; }
    </style>
  `;

  const emailHtml = `
    ${emailCss}
    <div style="max-width:600px;margin:0 auto;padding:16px 18px;font-family:Georgia,serif;font-size:16px;line-height:1.6;color:#111;">
      ${mainHtml}
    </div>
  `;

  const recipients = parseSubscribers();
  if (recipients.length === 0) throw new Error("No active subscribers in subscribers.csv.");

  console.log(`Sending ${dateStr} to ${recipients.length} recipients via Postmark broadcast stream...`);

  for (const r of recipients) {
    await postmarkSend(r.email, subject, emailHtml);
  }

  sentLog[dateStr] = { sent_at: new Date().toISOString(), count: recipients.length };
  saveSentLog(sentLog);
  console.log(`Sent + logged ${dateStr}.`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
