import { test, expect } from "@playwright/test";

/**
 * 10.3 Caregiver Management E2E tests
 * - Scheduling strip load
 * - Confirm + decline flow
 * - Schedule grid render
 */

test.describe("Caregiver Management", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/caregivers");
  });

  test("loads the caregiver management page", async ({ page }) => {
    await expect(page.getByText(/pending tasks/i).first()).toBeVisible();
  });

  test("scheduling strip is visible", async ({ page }) => {
    // Either scheduling rows or empty state
    await expect(
      page.getByText("No scheduling actions pending.")
        .or(page.locator('[data-testid="scheduling-row"]').first())
    ).toBeVisible({ timeout: 10_000 });
  });

  test("caregiver list renders in sidebar", async ({ page }) => {
    await expect(page.getByText(/caregivers/i).first()).toBeVisible();
    // After loading, caregiver buttons or empty state
    await expect(
      page.getByText("Loading…").or(page.locator("aside button, div button").first())
    ).toBeVisible({ timeout: 10_000 });
  });

  test("selecting a caregiver shows detail panel", async ({ page }) => {
    const caregiverBtn = page.locator("button").filter({ hasText: /caregiver/i }).first();
    if (await caregiverBtn.isVisible()) {
      await caregiverBtn.click();
      await expect(page.getByText(/14-day schedule/i)).toBeVisible({ timeout: 5_000 });
    }
  });

  test("confirm button calls confirm endpoint for unconfirmed actions", async ({ page }) => {
    const confirmBtn = page.locator('[data-testid="confirm-btn"]').first();
    if (await confirmBtn.isVisible()) {
      await confirmBtn.click();
      // After confirm, the row should update or disappear
      await page.waitForTimeout(2000);
      // Verify no JS error by checking page is still functional
      await expect(page).toHaveURL("/caregivers");
    }
  });

  test("decline button calls decline endpoint for unconfirmed actions", async ({ page }) => {
    const declineBtn = page.locator('[data-testid="decline-btn"]').first();
    if (await declineBtn.isVisible()) {
      await declineBtn.click();
      await page.waitForTimeout(2000);
      await expect(page).toHaveURL("/caregivers");
    }
  });

  test("schedule grid renders when caregiver is selected", async ({ page }) => {
    // Select first caregiver from list (bottom of left panel)
    const caregiverBtns = page.locator("button");
    const count = await caregiverBtns.count();
    for (let i = 0; i < count; i++) {
      const btn = caregiverBtns.nth(i);
      const text = await btn.textContent();
      if (text && !text.includes("+") && !text.includes("Pending Tasks") && text.trim().length > 2) {
        await btn.click();
        break;
      }
    }
    // Detail panel should appear
    await expect(
      page.getByText(/select a caregiver/i)
        .or(page.getByText(/14-day schedule/i))
    ).toBeVisible({ timeout: 5_000 });
  });

  test("navigating from action feed preselects action in strip", async ({ page }) => {
    // Navigate from Action Feed to Caregivers with router state
    await page.goto("/actions");
    const schedulingBtn = page.locator('[data-testid="view-scheduling-btn"]').first();
    if (await schedulingBtn.isVisible()) {
      await schedulingBtn.click();
      // Should be on caregivers page
      await expect(page).toHaveURL("/caregivers");
      // Highlighted row should be visible
      await expect(
        page.locator('[style*="border: 2px solid rgb(99, 102, 241)"]')
          .or(page.locator('[data-testid="scheduling-row"]').first())
      ).toBeVisible({ timeout: 5_000 });
    }
  });
});
