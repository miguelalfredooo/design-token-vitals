"""Browser-level checks for the report view controller."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_discovery


def playwright_module():
    if not shutil.which("node"):
        return None
    result = subprocess.run(
        ["node", "-e", "console.log(require.resolve('playwright'))"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


class TestReportViewsBrowser(unittest.TestCase):
    def test_switching_hash_promotion_and_print_restoration(self):
        playwright = playwright_module()
        if not playwright:
            self.skipTest("Node Playwright is not installed in this environment")
        switcher = render_discovery.render_report_view_switcher("snapshot")
        disclosure = render_discovery.prepare_progressive_disclosures(
            '<details id="evidence-detail"><summary>Evidence</summary>'
            '<p>Complete finding</p></details>'
        )
        probe = """<script>
          const results = {};
          const action = document.getElementById("summary");
          const evidence = document.getElementById("inventory");
          const detail = document.getElementById("evidence-detail");
          results.initial = document.body.dataset.reportView === "snapshot" &&
            getComputedStyle(action).display === "none" &&
            getComputedStyle(evidence).display === "none" && !detail.open &&
            getComputedStyle(document.querySelector(".report-view-switcher")).display === "block";
          document.querySelector('[data-report-view-button="action"]').click();
          results.action = document.body.dataset.reportView === "action" &&
            getComputedStyle(action).display !== "none" &&
            getComputedStyle(evidence).display === "none";
          window.location.hash = "#inventory-panel-typography";
          window.setTimeout(() => {
            results.hash = document.body.dataset.reportView === "evidence" &&
              !document.getElementById("inventory-panel-typography").hidden &&
              document.getElementById("inventory-panel-color").hidden;
            window.dispatchEvent(new Event("beforeprint"));
            results.beforeprint = detail.open;
            window.dispatchEvent(new Event("afterprint"));
            results.afterprint = !detail.open;
            document.body.dataset.browserResults = encodeURIComponent(JSON.stringify(results));
          }, 25);
        </script>"""
        document = """<!doctype html><html><head><style>
          .report-view-switcher { display: none; }
          .report-views--ready .report-view-switcher { display: block; }
          .report-views--ready body[data-report-view="snapshot"] section[data-report-views]:not([data-report-views~="snapshot"]),
          .report-views--ready body[data-report-view="action"] section[data-report-views]:not([data-report-views~="action"]) { display: none; }
        </style></head><body data-report-view="snapshot">%s
          <section id="glance" data-report-views="snapshot action evidence"></section>
          <section id="summary" data-report-views="action evidence"></section>
          <section id="inventory" data-report-views="evidence">
            <div data-token-inventory-tabs><div role="tablist">
              <button role="tab" aria-selected="true" aria-controls="inventory-panel-color"></button>
              <button role="tab" aria-selected="false" aria-controls="inventory-panel-typography"></button>
            </div><div role="tabpanel" id="inventory-panel-color"></div>
            <div role="tabpanel" id="inventory-panel-typography"></div></div>%s
          </section>%s%s</body></html>""" % (
            switcher, disclosure, render_discovery.INVENTORY_TABS_SCRIPT, probe
        )
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "report-view-test.html")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(document)
            runner = os.path.join(root, "run-report-view-test.js")
            with open(runner, "w", encoding="utf-8") as handle:
                handle.write("""
                  const { chromium } = require(process.argv[3]);
                  (async () => {
                    const browser = await chromium.launch({ headless: true, channel: "chrome" });
                    const page = await browser.newPage();
                    await page.goto(process.argv[2]);
                    await page.waitForFunction(() => document.body.dataset.browserResults);
                    console.log(await page.getAttribute("body", "data-browser-results"));
                    await browser.close();
                  })().catch((error) => {
                    console.error(error.stack || error);
                    process.exit(1);
                  });
                """)
            result = subprocess.run(
                ["node", runner, Path(path).as_uri(), playwright],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=20,
            )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        results = json.loads(urllib.parse.unquote(result.stdout.strip()))
        self.assertEqual(
            results,
            {"initial": True, "action": True, "hash": True,
             "beforeprint": True, "afterprint": True},
        )


if __name__ == "__main__":
    unittest.main()
