import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { PDFDocument } from "pdf-lib";

const SITE_DIR = path.resolve("publish/site");
const BRIEFINGS_DIR = path.join(SITE_DIR, "briefings");

function listBriefingHtmlFiles() {
  return fs
    .readdirSync(BRIEFINGS_DIR)
    .filter((f) => f.endsWith(".html"))
    .filter((f) => f !== "index.html") // skip archive
    .sort();
}

function shortFooter() {
  return `
    <div style="
      max-width: 820px;
      margin: 0 auto;
      font-size: 9px;
      color: #777;
      font-family: 'JetBrains Mono', ui-monospace, monospace;
      display: flex;
      justify-content: space-between;
      box-sizing: border-box;
    ">
      <div>© 2026 RegLag | reglag.com</div>
      <div><span class="pageNumber"></span> / <span class="totalPages"></span></div>
    </div>
  `;
}

function firstPageFooter() {
  return `
    <div style="
      max-width: 820px;
      margin: 0 auto;
      font-size: 9px;
      color: #777;
      font-family: 'JetBrains Mono', ui-monospace, monospace;
      box-sizing: border-box;
    ">
      <div>Original RegLag analysis and commentary. Informational only; not investment, legal, or regulatory advice.</div>
      <div>Free to share in full for non-commercial purposes with attribution to RegLag.</div>
      <div style="display:flex; justify-content:space-between; margin-top:4px;">
        <div>© 2026 RegLag | reglag.com</div>
        <div><span class="pageNumber"></span> / <span class="totalPages"></span></div>
      </div>
    </div>
  `;
}

async function mergePage1AndRemainder(page1Bytes, remainderBytes) {
  const out = await PDFDocument.create();

  const doc1 = await PDFDocument.load(page1Bytes);
  const pages1 = await out.copyPages(doc1, doc1.getPageIndices());
  pages1.forEach((p) => out.addPage(p));

  if (remainderBytes && remainderBytes.length > 0) {
    const docR = await PDFDocument.load(remainderBytes);
    const pagesR = await out.copyPages(docR, docR.getPageIndices());
    pagesR.forEach((p) => out.addPage(p));
  }

  return await out.save();
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
    await page.waitForTimeout(250);

    // 1) Render full document with short footer (all pages)
    const fullShort = await page.pdf({
      format: "Letter",
      printBackground: true,
      margin: { top: "0.75in", right: "0.75in", bottom: "0.85in", left: "0.75in" },
      displayHeaderFooter: true,
      headerTemplate: `<div></div>`,
      footerTemplate: shortFooter(),
    });

    const doc = await PDFDocument.load(fullShort);
    const pageCount = doc.getPageCount();

    // 2) Render page 1 with expanded footer (page 1 only)
    const page1Long = await page.pdf({
      format: "Letter",
      printBackground: true,
      margin: { top: "0.75in", right: "0.75in", bottom: "0.85in", left: "0.75in" },
      displayHeaderFooter: true,
      headerTemplate: `<div></div>`,
      footerTemplate: firstPageFooter(),
      pageRanges: "1",
    });

    // 3) Extract pages 2+ from the fullShort PDF (no re-render)
    let remainderBytes = null;
    if (pageCount > 1) {
      const remainderDoc = await PDFDocument.create();
      const indices = Array.from({ length: pageCount - 1 }, (_, i) => i + 1); // 1..n-1 (0-based)
      const pages = await remainderDoc.copyPages(doc, indices);
      pages.forEach((p) => remainderDoc.addPage(p));
      remainderBytes = await remainderDoc.save();
    }

    // 4) Merge into final output
    const finalPdf = await mergePage1AndRemainder(page1Long, remainderBytes);
    fs.writeFileSync(outPath, finalPdf);
  }

  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
