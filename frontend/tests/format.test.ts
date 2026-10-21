import assert from "node:assert/strict";
import { test } from "node:test";

import { buildQuery, confidenceLevel, formatDelay, isNew, relativeTime, safeExternalUrl } from "../lib/format.ts";

test("safeExternalUrl n'autorise que http(s)", () => {
  assert.equal(safeExternalUrl("https://example.com/a"), "https://example.com/a");
  assert.equal(safeExternalUrl("javascript:alert(1)"), null);
  assert.equal(safeExternalUrl("data:text/html,<script>"), null);
  assert.equal(safeExternalUrl("pas une url"), null);
});

test("confidenceLevel", () => {
  assert.equal(confidenceLevel(null), "inconnu");
  assert.equal(confidenceLevel(0.8), "eleve");
  assert.equal(confidenceLevel(0.6), "moyen");
  assert.equal(confidenceLevel(0.2), "faible");
});

test("relativeTime et isNew", () => {
  const now = new Date("2026-10-21T10:00:00Z");
  assert.equal(relativeTime("2026-10-21T09:30:00Z", now), "il y a 30 min");
  assert.equal(relativeTime("2026-10-21T12:00:00Z", now), "dans 2 h");
  assert.equal(relativeTime(null, now), "jamais");
  assert.equal(isNew("2026-10-21T00:00:00Z", now), true);
  assert.equal(isNew("2026-10-19T00:00:00Z", now), false);
});

test("formatDelay", () => {
  assert.equal(formatDelay(null), "non calculable");
  assert.equal(formatDelay(42), "42 min");
  assert.equal(formatDelay(90), "1,5 h");
});

test("buildQuery ignore les valeurs vides", () => {
  assert.equal(buildQuery({ q: "drone", category: "", page: 2, x: undefined }), "?q=drone&page=2");
  assert.equal(buildQuery({}), "");
});
