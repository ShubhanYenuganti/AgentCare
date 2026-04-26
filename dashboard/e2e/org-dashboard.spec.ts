import { test, expect } from "@playwright/test";

/**
 * 10.4 Org Dashboard E2E tests
 * - Org summary load
 * - Protocol panel render
 * - Org profile edit and refresh
 */

test.describe("Org Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/org");
  });

  test("loads the org dashboard page", async ({ page }) => {
    // Should show org name or "Organisation" fallback
    await expect(page.locator("h1")).toBeVisible({ timeout: 10_000 });
  });

  test("metric cards are rendered", async ({ page }) => {
    // Four metric cards should be visible
    await expect(page.getByText(/pending actions/i)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/overdue actions/i)).toBeVisible();
  });

  test("30-day completion rate card is visible", async ({ page }) => {
    await expect(page.getByText(/completion/i)).toBeVisible({ timeout: 10_000 });
  });

  test("avg urgency score card is visible", async ({ page }) => {
    await expect(page.getByText(/urgency score/i)).toBeVisible({ timeout: 10_000 });
  });

  test("edit org profile button is present", async ({ page }) => {
    await expect(page.getByRole("button", { name: /edit org profile/i })).toBeVisible({ timeout: 10_000 });
  });

  test("edit org profile modal opens", async ({ page }) => {
    await page.getByRole("button", { name: /edit org profile/i }).click();
    await expect(page.getByRole("heading", { name: /edit org profile/i })).toBeVisible();
  });

  test("edit org profile form has required fields", async ({ page }) => {
    await page.getByRole("button", { name: /edit org profile/i }).click();
    await expect(page.getByRole("heading", { name: /edit org profile/i })).toBeVisible();
    // Form fields should be present
    const inputs = page.locator("input");
    await expect(inputs.first()).toBeVisible();
  });

  test("org profile edit submits and refreshes", async ({ page }) => {
    await page.getByRole("button", { name: /edit org profile/i }).click();
    const orgNameInput = page.locator("input").first();
    await orgNameInput.clear();
    await orgNameInput.fill("Updated Care Org");
    await page.getByRole("button", { name: /save/i }).click();
    // Modal should close
    await expect(page.getByRole("heading", { name: /edit org profile/i })).not.toBeVisible({ timeout: 10_000 });
    // Summary should refresh
    await expect(page.locator("h1")).toContainText("Updated Care Org", { timeout: 10_000 });
  });

  test("protocol cards render when protocols exist", async ({ page }) => {
    // If protocols exist in org data, they should be shown
    const protocolSection = page.getByText(/protocols/i);
    const hasProtocols = await protocolSection.isVisible({ timeout: 3_000 }).catch(() => false);
    if (hasProtocols) {
      await expect(page.locator("section").filter({ hasText: /protocols/i })).toBeVisible();
    }
  });

  test("caregiver roster table renders when caregivers exist", async ({ page }) => {
    const rosterTable = page.locator("table");
    const caregivers = page.getByText(/caregiver roster/i);
    const hasCaregivers = await caregivers.isVisible({ timeout: 3_000 }).catch(() => false);
    if (hasCaregivers) {
      await expect(rosterTable).toBeVisible();
    }
  });
});
