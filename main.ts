// Entry point for this make.fun submission.
//
// The entry itself is one public TikTok post. Its address lives in
// VIDEO.json next to this file, and the runner expects that address
// back as plain text in /output/entry.txt, so this program is only a
// small courier between the two.

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const repoDir = dirname(fileURLToPath(import.meta.url));
const manifest = JSON.parse(
  readFileSync(join(repoDir, "VIDEO.json"), "utf8"),
) as { url?: unknown };

const link = typeof manifest.url === "string" ? manifest.url.trim() : "";
if (link.length === 0) {
  throw new Error("VIDEO.json is missing its url field");
}

mkdirSync("/output", { recursive: true });
writeFileSync("/output/entry.txt", `${link}\n`, "utf8");
console.log(`wrote /output/entry.txt with ${link}`);
