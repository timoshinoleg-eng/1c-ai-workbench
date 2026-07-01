import { test, expect } from "@playwright/test";

test.describe("Search page", () => {
  test("mode tabs render and search input accepts text", async ({ page }) => {
    await page.goto("/search");
    await expect(page.getByRole("heading", { name: "Search" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Text" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Grep" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "MCP" })).toBeVisible();
    const input = page.getByPlaceholder(/ПриходТоваров|Номенклатура/);
    await input.fill("Номенклатура");
    await expect(input).toHaveValue("Номенклатура");
  });
});
