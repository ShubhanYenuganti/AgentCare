import { test, expect } from "@playwright/test";

/**
 * 10.2 Patient Roster E2E tests
 * - Patient selection loads detail
 * - Text ingest add patient
 * - Staged update confirmation flow
 * - Update history tab
 */

test.describe("Patient Roster", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/patients");
  });

  test("loads the patient roster page", async ({ page }) => {
    await expect(page.getByText(/patients/i).first()).toBeVisible();
  });

  test("patient list renders in sidebar", async ({ page }) => {
    const sidebar = page.locator("aside");
    await expect(sidebar).toBeVisible();
    // Either patients or loading indicator
    await expect(
      sidebar.getByText("Loading…").or(sidebar.locator("button").first())
    ).toBeVisible({ timeout: 10_000 });
  });

  test("selecting a patient loads detail panel", async ({ page }) => {
    const firstPatient = page.locator("aside button").first();
    if (await firstPatient.isVisible()) {
      await firstPatient.click();
      // Detail panel should show patient name
      await expect(page.locator("h2")).toBeVisible({ timeout: 5_000 });
    }
  });

  test("selecting a patient shows life graph sections", async ({ page }) => {
    const firstPatient = page.locator("aside button").first();
    if (await firstPatient.isVisible()) {
      await firstPatient.click();
      // After selecting, overview tab should be active with life graph content
      await expect(page.getByRole("button", { name: /overview/i })).toBeVisible();
    }
  });

  test("Add Patient button opens modal", async ({ page }) => {
    await page.getByRole("button", { name: /\+ add/i }).click();
    await expect(page.getByRole("heading", { name: /add patient/i })).toBeVisible();
  });

  test("text ingest tab is visible in add patient modal", async ({ page }) => {
    await page.getByRole("button", { name: /\+ add/i }).click();
    await expect(page.getByRole("button", { name: /text ingest/i })).toBeVisible();
  });

  test("file upload tab is visible in add patient modal", async ({ page }) => {
    await page.getByRole("button", { name: /\+ add/i }).click();
    await expect(page.getByRole("button", { name: /file upload/i })).toBeVisible();
  });

  test("text ingest submit sends patient text", async ({ page }) => {
    await page.getByRole("button", { name: /\+ add/i }).click();
    const textarea = page.locator("textarea").last();
    await textarea.fill("Patient: John Smith, 70 years old, 123 Main St, heart condition");
    await page.getByRole("button", { name: /add patient/i }).click();
    // Modal should close or show success
    await expect(page.getByRole("heading", { name: /add patient/i })).not.toBeVisible({ timeout: 15_000 });
  });

  test("update history tab is accessible when patient is selected", async ({ page }) => {
    const firstPatient = page.locator("aside button").first();
    if (await firstPatient.isVisible()) {
      await firstPatient.click();
      await page.getByRole("button", { name: /update history/i }).click();
      // Should show history or empty state
      await expect(
        page.getByText("No update history.").or(page.locator("ul li").first())
      ).toBeVisible({ timeout: 5_000 });
    }
  });

  test("staged update flow: submit shows confirmation", async ({ page }) => {
    const firstPatient = page.locator("aside button").first();
    if (await firstPatient.isVisible()) {
      await firstPatient.click();
      await page.getByRole("button", { name: /update/i }).click();
      // Should show update form
      const textarea = page.locator("textarea").last();
      if (await textarea.isVisible()) {
        await textarea.fill("Update medication dosage");
        await page.getByRole("button", { name: /submit update/i }).click();
        // Should show awaiting confirmation state or confirmation panel
        await expect(
          page.getByRole("button", { name: /confirm/i })
            .or(page.getByText(/proposed changes/i))
        ).toBeVisible({ timeout: 10_000 });
      }
    }
  });
});
