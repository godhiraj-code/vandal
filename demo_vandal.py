import asyncio
import os
import argparse
from pathlib import Path
from playwright.async_api import async_playwright
from vandal import Vandal

async def run_demo(headless=True):
    async with async_playwright() as p:
        slow_mo = 1500 if not headless else 0
        browser = await p.chromium.launch(headless=headless, slow_mo=slow_mo)
        page = await browser.new_page()
        
        # Load local demo app
        file_path = Path(__file__).with_name("vandal_demo_app.html").resolve().as_uri()
        
        print("\n--- PHASE 1: Normal Test (Expect Success) ---")
        await page.goto(file_path)
        await page.click("#login-btn")
        msg = await page.inner_text("#message")
        if msg == 'Logged In Successfully!':
            print("Normal test passed.")
        else:
            print("Normal test failed.")

        print("\n--- PHASE 2: Vandalized Test (Expect Failure) ---")
        await page.goto(file_path) # Reset page
        
        try:
            async with Vandal(page) as v:
                # We "Vandalize" the login button by stripping its pointer events (Stealth Disable)
                await v.apply_mutation("stealth_disable", "#login-btn")
                
                # The click will now 'fail' to trigger the handler
                await page.click("#login-btn", force=True, timeout=3000)
                
                # Check if the message appeared
                msg = await page.inner_text("#message")
                assert msg == 'Logged In Successfully!', "Message did not appear!"
                print("Test passed (Mutant Survived!)")
        except Exception:
            # Vandal's __aexit__ already recorded the 'killed' status
            pass

        v.report()
        if not headless:
            print("Holding browser open for 5 seconds...")
            await asyncio.sleep(5)
        await browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--headed", action="store_true", help="Run in headed mode")
    parser.add_argument("--headless", action="store_true", default=True, help="Run in headless mode")
    args = parser.parse_args()
    
    headless_mode = not args.headed
    asyncio.run(run_demo(headless=headless_mode))
