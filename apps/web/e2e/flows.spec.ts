import { test, expect } from "@playwright/test";

// End-to-end coverage of the critical flows against the live dev stack (run `make demo-reset`
// first so the 8 invoices are seeded + extracted).

async function signIn(page, personaName: string) {
  await page.goto("/");
  await page.getByRole("combobox").selectOption({ label: personaName });
  await expect(page.getByText(personaName.split(" (")[0])).toBeVisible();
}

test("persona sign-in shows command center KPIs", async ({ page }) => {
  await signIn(page, "Alex Park (AP Accountant)");
  await expect(page.getByRole("heading", { name: "Command Center" })).toBeVisible();
  await expect(page.getByText("Total invoices")).toBeVisible();
});

test("inbox lists invoices and opens the workbench", async ({ page }) => {
  await signIn(page, "Alex Park (AP Accountant)");
  await page.goto("/inbox");
  await expect(page.getByRole("heading", { name: "Invoice Inbox" })).toBeVisible();
  await page.getByRole("link", { name: /LP-/ }).first().click();
  await expect(page.getByText("Original document")).toBeVisible();
  await expect(page.getByText("Audit timeline")).toBeVisible();
});

test("blocking duplicate is surfaced with an exception", async ({ page }) => {
  await signIn(page, "Alex Park (AP Accountant)");
  await page.goto("/exceptions");
  await expect(page.getByText("POSSIBLE_DUPLICATE")).toBeVisible();
  await expect(page.getByText("BLOCKING")).toBeVisible();
});

test("construction rate-mismatch exception is surfaced", async ({ page }) => {
  await signIn(page, "Alex Park (AP Accountant)");
  await page.goto("/exceptions");
  await expect(page.getByText("RATE_ABOVE_CONTRACT")).toBeVisible();
});
