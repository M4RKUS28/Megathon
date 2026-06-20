import { describe, expect, it } from "vitest";
import { hasPassed, isRenderable, scorePct } from "./utils";

describe("scorePct", () => {
  it("returns 100 for an empty quiz", () => {
    expect(scorePct([], {})).toBe(100);
  });
  it("computes percentage of correct answers", () => {
    expect(scorePct([0, 1, 2, 3], { 0: 0, 1: 1, 2: 9, 3: 3 })).toBe(75);
  });
});

describe("hasPassed", () => {
  it("enforces the 80% gate by default", () => {
    expect(hasPassed(80)).toBe(true);
    expect(hasPassed(79)).toBe(false);
  });
});

describe("isRenderable", () => {
  it("requires at least one chapter", () => {
    expect(isRenderable(null)).toBe(false);
    expect(isRenderable({ title: "x", chapters: [] })).toBe(false);
    expect(
      isRenderable({ title: "x", chapters: [{ id: "a", title: "A", pages: [], quiz: { passing_pct: 80, retryable: true, questions: [] } }] }),
    ).toBe(true);
  });
});
