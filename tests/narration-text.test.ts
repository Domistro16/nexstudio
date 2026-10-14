import assert from "node:assert/strict";
import { normalizeNarration } from "../src/lib/narration-text";

// The production failure xr-ba9ac66e: chat-tool bold markers were spoken as
// "asterisk asterisk" and drawn as an oversized promoted word.
const pasted = "Imagine if every time you sent money, anyone could look.\r\n\r\nBut **Zcash does something different.**\r\n\r\nIt uses **zero-knowledge proofs**, specifically zk-SNARKs.\r\n\r\n**The ability to keep their financial transactions private while still proving they're valid.**";
assert.equal(normalizeNarration(pasted),
  "Imagine if every time you sent money, anyone could look.\n\nBut Zcash does something different.\n\nIt uses zero-knowledge proofs, specifically zk-SNARKs.\n\nThe ability to keep their financial transactions private while still proving they're valid.");

assert.equal(normalizeNarration("Mix *gently* and fold __slowly__. ~~Skip~~ this."), "Mix gently and fold slowly. Skip this.");
assert.equal(normalizeNarration("See [the guide](https://example.com) and `npm test`."), "See the guide and npm test.");
assert.equal(normalizeNarration("- three ripe bananas\n* one egg\n2) a pinch of salt."), "three ripe bananas.\none egg.\na pinch of salt.");
assert.equal(normalizeNarration("> Quoted line\n---\nAfter the rule"), "Quoted line\nAfter the rule");
assert.equal(normalizeNarration("```\nconst x = 1;\n```"), "const x = 1;");
assert.equal(normalizeNarration("**Broken bold at the end"), "Broken bold at the end");

// Ordinary narration is left exactly as written.
for (const plain of ["5 * 3 is fifteen.", "snake_case_names stay intact.", "Bake at 350 degrees — about fifty minutes!"]) {
  assert.equal(normalizeNarration(plain), plain);
}
assert.equal(normalizeNarration("It's *not* hard."), "It's not hard.");

// Explainers speak headings as their own sentence; board scenes keep them as structure.
assert.equal(normalizeNarration("## Why it **matters**\nIt is fast."), "Why it matters.\nIt is fast.");
assert.equal(normalizeNarration("# Banana Bread\r\n## Mixing\r\nStir the batter.", { keepHeadings: true }), "# Banana Bread\n## Mixing\nStir the batter.");
assert.equal(normalizeNarration("\r\n\r\n\r\n\r\nOne.\r\n\r\n\r\n\r\nTwo.\r\n"), "One.\n\nTwo.");

console.log("Narration text normalization checks passed.");
