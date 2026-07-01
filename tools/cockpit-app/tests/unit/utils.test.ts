import { describe, it, expect } from "vitest";
import { formatTimestamp, debounce } from "@/lib/utils";

describe("formatTimestamp", () => {
  it("returns a placeholder for nullish input", () => {
    expect(formatTimestamp(null)).toBe("—");
    expect(formatTimestamp(undefined)).toBe("—");
    expect(formatTimestamp("not-a-date")).toBe("—");
  });

  it("formats ISO timestamps into a Russian-locale string", () => {
    const out = formatTimestamp("2026-06-23T10:15:00Z");
    expect(out).toMatch(/\d{2}\.\d{2}\.\d{4}/);
  });
});

describe("debounce", () => {
  it("coalesces rapid calls", async () => {
    let count = 0;
    const fn = debounce(() => count++, 25);
    fn();
    fn();
    fn();
    await new Promise((r) => setTimeout(r, 60));
    expect(count).toBe(1);
  });
});
