"""Browser-level checks for the report controller: disclosures, hash links, tabs, copy and print."""
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


class TestReportControllerBrowser(unittest.TestCase):
    def test_disclosures_hash_links_tabs_copy_and_print(self):
        playwright = playwright_module()
        if not playwright:
            self.skipTest("Node Playwright is not installed in this environment")
        disclosure = render_discovery.prepare_progressive_disclosures(
            '<details id="fold"><summary>Open the inventory</summary>'
            '<div data-token-inventory-tabs><div role="tablist">'
            '<button role="tab" aria-selected="true" aria-controls="inventory-panel-color"></button>'
            '<button role="tab" aria-selected="false" aria-controls="inventory-panel-typography"></button>'
            '</div><div role="tabpanel" id="inventory-panel-color"></div>'
            '<div role="tabpanel" id="inventory-panel-typography"></div></div>'
            '</details>'
        )
        probe = """<script>
          const results = {};
          const fold = document.getElementById("fold");
          const copy = document.querySelector("[data-copy]");
          results.initial = !fold.open &&
            document.documentElement.classList.contains("report--ready") &&
            getComputedStyle(copy).display !== "none";
          window.location.hash = "#inventory-panel-typography";
          window.setTimeout(() => {
            results.hash = fold.open &&
              !document.getElementById("inventory-panel-typography").hidden &&
              document.getElementById("inventory-panel-color").hidden;
            fold.open = false;
            window.dispatchEvent(new Event("beforeprint"));
            results.beforeprint = fold.open;
            window.dispatchEvent(new Event("afterprint"));
            results.afterprint = !fold.open;
            document.body.dataset.browserResults = encodeURIComponent(JSON.stringify(results));
          }, 25);
        </script>"""
        document = """<!doctype html><html><head><style>
          .copy { display: none; }
          .report--ready .copy { display: inline-block; }
        </style></head><body>
          <section id="inventory">%s</section>
          <div class="cmd-row"><code data-copy-source>python3 tools/x.py .</code>
          <button type="button" class="copy" data-copy>Copy</button></div>
          %s%s</body></html>""" % (
            disclosure, render_discovery.INVENTORY_TABS_SCRIPT, probe
        )
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "report-controller-test.html")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(document)
            runner = os.path.join(root, "run-report-controller-test.js")
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
            {"initial": True, "hash": True,
             "beforeprint": True, "afterprint": True},
        )


if __name__ == "__main__":
    unittest.main()
