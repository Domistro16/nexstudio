import assert from "node:assert/strict";
import { chooseVideoTitle, cleanTitle, fallbackTitle } from "../src/lib/video-title";

for (const key of ["STUDIO_SCRIPT_OPENAI_API_KEY", "STUDIO_PLAN_PREVIEW_OPENAI_API_KEY", "OPENAI_API_KEY"]) delete process.env[key];

const banana = "Banana bread is one of the easiest and most comforting treats you can bake at home.\r\nStart by preheating your oven to 350 degrees.";

assert.equal(cleanTitle("**Banana Bread Basics.**"), "Banana Bread Basics");
assert.equal(cleanTitle("\"How Zcash Keeps Payments Private\""), "How Zcash Keeps Payments Private");
assert.equal(cleanTitle("one two three four five six seven eight nine ten").split(" ").length, 8);
assert.equal(cleanTitle(""), "");

assert.equal(fallbackTitle(banana), "Banana bread");
assert.equal(fallbackTitle("Imagine if every time you sent money, anyone could look up the transaction."), "Imagine if every time you sent");
assert.equal(fallbackTitle("Solar panels turn sunlight into power."), "Solar panels");

// NexMind's title wins, then the script's own `# Title`, then one derived from the narration — never the job id.
assert.equal(await chooseVideoTitle(banana, "Banana Bread Basics"), "Banana Bread Basics");
assert.equal(await chooseVideoTitle(`# Bake Better Bread\n${banana}`, ""), "Bake Better Bread");
assert.equal(await chooseVideoTitle(banana, null), "Banana bread");
assert.equal(await chooseVideoTitle("", null), "");

console.log("Video title checks passed.");
