const { chromium } = require("C:/Users/labops/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core");

(async () => {
  const browser = await chromium.launch({
    executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
    headless: true,
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 950 }, deviceScaleFactor: 1.25 });
  const errors = [];
  page.on("pageerror", e => errors.push(e.message));
  page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
  await page.goto("file:///D:/DEV/blood/数据采集与分析周报_0727-0806.html");
  await page.waitForTimeout(2500);
  const canvases = await page.locator("canvas").count();
  const kpi0 = await page.locator(".kpi .v").first().textContent();
  const rows = await page.locator("table tr").count();
  console.log("canvases:", canvases, "| kpi0:", kpi0.trim(), "| table rows:", rows);
  await page.screenshot({ path: "D:/DEV/blood/周报_顶部.png", fullPage: false });
  await page.screenshot({ path: "D:/DEV/blood/周报_全页.png", fullPage: true });
  console.log("errors:", errors.length ? JSON.stringify(errors.slice(0, 4)) : "none");
  await browser.close();
})();
