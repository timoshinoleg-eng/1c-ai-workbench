import { test, expect } from "@playwright/test";

test.describe("Cockpit page", () => {
  test("renders server cards and starts one server", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Cockpit" })).toBeVisible();
    await expect(page.getByRole("button", { name: /start all/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /stop all/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /health check/i })).toBeVisible();
    // 5 MCP server cards are rendered from the static catalog.
    await expect(page.getByText("1C Code Index")).toBeVisible();
    await expect(page.getByText("1C Skills")).toBeVisible();
    await expect(page.getByText("1C Prompt Gallery")).toBeVisible();
    await expect(page.getByText("1C Help Index")).toBeVisible();
    await expect(page.getByText("1C ibcmd")).toBeVisible();

    const codeIndexCard = page.getByTestId("server-card-1c-code-index");
    await expect(codeIndexCard.getByText("stopped")).toBeVisible();
    await codeIndexCard.getByRole("button", { name: "Start 1C Code Index", exact: true }).click();
    await expect(codeIndexCard.getByText("running")).toBeVisible();
  });
});
