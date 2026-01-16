import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const SITE_DIR = path.resolve("publish/site");
const BRIEFINGS_DIR = path.join(SITE_DIR, "briefings");

function listBriefingHtmlFiles() {
  const files = fs.readdirSync(BRIEFINGS_DIR)
    .filter(f => f.endsWith(".html"))
    .filter(f => f !== "index.html") // skip archive
    .sort();
  return files;
}

async function main() {
  if (!fs.existsSync(BRIEFINGS_DIR)) {
    console.error(`Missing directory: ${BRIEFINGS_DIR}`);
    process.exit(1);
  }

  const files = listBriefingHtmlFiles();
  if (files.length === 0) {
    console.log("No briefing HTML files found to render.");
    return;
  }

  // Start a local server so relative assets (/assets/...) resolve correctly
  // We assume the workflow starts a server at http://127.0.0.1:8000
  const baseUrl = "http://127.0.0.1:8000";

  const browser = await chromium.launch();
  const context = await browser.newContext();

  // Block external network calls (analytics, etc.) to keep output deterministic
  await context.route("**/*", (route) => {
    const url = route.request().url();
    const isLocal = url.startsWith(baseUrl);
    const isData = url.startsWith("data:");
    if (isLocal || isData) return route.continue();
    return route.abort();
  });

  const page = await context.newPage();

  for (const htmlFile of files) {
    const url = `${baseUrl}/briefings/${htmlFile}`;
    const pdfFile = htmlFile.replace(/\.html$/i, ".pdf");
    const outPath = path.join(BRIEFINGS_DIR, pdfFile);

    console.log(`Rendering ${url} -> ${outPath}`);

    await page.goto(url, { waitUntil: "load" });

    // Ensure fonts/layout settle
    await page.waitForTimeout(250);

    await page.pdf({
      path: outPath,
      format: "Letter",
      printBackground: true,
      margin: {
        top: "0.75in",
        right: "0.75in",
        bottom: "0.85in",
        left: "0.75in",
      },
      displayHeaderFooter: true,
      headerTemplate: `<div></div>`,
      footerTemplate: `
        <div style="width:100%; font-size:9px; color:#777; padding:0 0.75in; display:flex; justify-content:space-between;">
          <div>RegLag — reglag.com</div>
          <div><span class="pageNumber"></span> / <span class="totalPages"></span></div>
        </div>
      `,
    });
  }

  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
