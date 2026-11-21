// Entry program for the make.fun bounty "bring-the-humans-03"
// (Bring the humans with a TikTok ad).
//
// The entry itself is the TikTok video; this program hands in its address.
// It copies VIDEO.json from the repository root (MAKEFUN_BOT_DIR, "." when
// run locally) into the output directory (MAKEFUN_OUTPUT_DIR, "/output" on
// the grader) so the judges can read the video's URL from a known place.
//
// Node 22, standard library only, no network.

import { copyFileSync, mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const botDir = process.env.MAKEFUN_BOT_DIR ?? ".";
const outDir = process.env.MAKEFUN_OUTPUT_DIR ?? "/output";

mkdirSync(outDir, { recursive: true });
const dest = join(outDir, "VIDEO.json");
copyFileSync(join(botDir, "VIDEO.json"), dest);

// Hand-in summary: echo what was delivered so the run log shows the entry.
const { url } = JSON.parse(readFileSync(dest, "utf8"));
console.log(`bring-the-humans-03 entry handed in: ${dest}`);
console.log(`TikTok video: ${url}`);
