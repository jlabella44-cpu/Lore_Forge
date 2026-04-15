import { test, expect } from "@playwright/test";

test("dashboard renders queue heading", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Book Queue" })).toBeVisible();
});
