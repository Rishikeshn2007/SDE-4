
import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test.describe('Session Studio E2E', () => {
  test('completes the session controls flow', async ({ page }) => {
    await page.goto('/')

    // Check that the application opens in mock mode.
    await expect(
      page.getByRole('heading', { name: /session studio/i }).first(),
    ).toBeVisible()

    await expect(page.getByText(/mock mode/i).first()).toBeVisible()

    // Start the session using the keyboard.
    const startButton = page.getByRole('button', {
      name: 'Start session',
    })

    await startButton.focus()
    await page.keyboard.press('Enter')

    await expect(page.getByText('CAPTURING')).toBeVisible()

    // Pause the session.
    const pauseButton = page.getByRole('button', {
      name: 'Pause session',
    })

    await pauseButton.click()
    await expect(page.getByText('PAUSED', { exact: true })).toBeVisible()

    // Resume the session.
    await page.getByRole('button', {
      name: 'Resume session',
    }).click()

    await expect(page.getByText('CAPTURING')).toBeVisible()

    // Stop the session.
    await page.getByRole('button', {
      name: 'Stop session',
    }).click()

    await expect(page.getByText('INACTIVE')).toBeVisible()
  })

  test('rejects approval without executing an action', async ({ page }) => {
    await page.goto('/')

    // Load the mock workflow.
    await page.getByRole('button', {
      name: /load mock transcript/i,
    }).click()

    // Wait until the approval step becomes available.
    const reviewButton = page.getByRole('button', {
      name: 'Review Approval',
    })

    await expect(reviewButton).toBeEnabled({ timeout: 25000 })
    await reviewButton.click()

    // Check the approval dialog.
    await expect(page.getByRole('dialog')).toBeVisible()

    // Reject the approval.
    await page.getByRole('button', {
      name: /reject/i,
    }).click()

    // Confirm rejection and ensure the dialog closes.
    await expect(
      page.getByText('Rejected. No action was executed.'),
    ).toBeVisible()

    await expect(page.getByRole('dialog')).not.toBeVisible()
  })

  test('recovers when the browser goes offline and comes online', async ({ page, context }) => {
    await page.goto('/')

    // Start the mock event stream.
    await page.getByRole('button', {
      name: /load mock transcript/i,
    }).click()

    await expect(page.getByText('CONNECTED', { exact: true })).toBeVisible()

    // Simulate an offline connection.
    await context.setOffline(true)

    await expect(
      page.getByText('DISCONNECTED', { exact: true }),
    ).toBeVisible()

    // Restore the connection.
    await context.setOffline(false)

    await expect(
      page.getByText('CONNECTED', { exact: true }),
    ).toBeVisible({ timeout: 10000 })
  })

  test('has no automatically detectable accessibility violations', async ({ page }) => {
    await page.goto('/')

    const accessibilityScan = await new AxeBuilder({ page }).analyze()

    expect(accessibilityScan.violations).toEqual([])
  })
  test('displays correctly on a mobile screen', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })

  await page.goto('/')

  await expect(
    page.getByRole('heading', { name: /session studio/i }).first(),
  ).toBeVisible()

  await expect(
    page.getByRole('button', { name: 'Start session' }),
  ).toBeVisible()

  const pageWidth = await page.locator('body').evaluate(
    (element) => element.scrollWidth,
  )

  expect(pageWidth).toBeLessThanOrEqual(390)
})
})
