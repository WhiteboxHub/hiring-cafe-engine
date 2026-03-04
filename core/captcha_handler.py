"""
CAPTCHA Handler Module

Provides utilities for handling CAPTCHA challenges:
- Manual solving with timeout
- Interactive waiting for user input
- Visual feedback and countdown
"""

import time
from core.logger import logger


class CaptchaHandler:
    """Handles CAPTCHA challenges with user interaction"""
    
    def __init__(self, driver, timeout=120):
        """
        Initialize CAPTCHA handler
        
        Args:
            driver: Selenium WebDriver instance
            timeout: Default timeout in seconds for automatic countdown
        """
        self.driver = driver
        self.timeout = timeout
    
    def wait_for_captcha_solution(self, custom_timeout=None):
        """
        Wait for user to solve CAPTCHA manually with countdown
        Automatically proceeds after timeout
        
        Args:
            custom_timeout: Override the default timeout for this call
        """
        timeout = custom_timeout if custom_timeout is not None else self.timeout
        
        print(f"\n{'='*120}")
        print("🔒 CAPTCHA DETECTED!")
        print(f"Please solve the CAPTCHA within {timeout} seconds...")
        print(f"The automation will continue automatically after {timeout} seconds.")
        print(f"{'='*120}\n")
        
        logger.info(f"CAPTCHA detected - waiting {timeout} seconds for manual solution")
        
        # Visual countdown
        for remaining in range(timeout, 0, -1):
            if remaining % 10 == 0 or remaining <= 5:
                print(f"\rTime remaining: {remaining} seconds... ", end='', flush=True)
            time.sleep(1)
        
        print("\n\n✓ Timeout reached - proceeding with form submission...")
        logger.info("CAPTCHA wait timeout completed")
        time.sleep(2)  # Brief pause before continuing
    
    def wait_for_captcha_interactive(self):
        """
        Wait for user to manually confirm CAPTCHA is solved
        No timeout - waits indefinitely for user input
        Best for ensuring CAPTCHA is actually solved before proceeding
        """
        print(f"\n{'='*60}")
        print("🔒 CAPTCHA DETECTED!")
        print("Please solve the CAPTCHA manually in the browser.")
        print("Once solved, press ENTER in this console to continue...")
        print(f"{'='*60}\n")
        
        logger.info("CAPTCHA detected - waiting for user confirmation")
        
        try:
            input("👉 Press ENTER after solving CAPTCHA... ")
            print("\n✓ User confirmed CAPTCHA solved - continuing automation...")
            logger.info("User confirmed CAPTCHA solution")
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n⚠️ User interrupted - stopping automation")
            logger.warning("User interrupted CAPTCHA wait")
            raise
    
    def wait_for_captcha_smart(self, check_interval=2, max_wait=60):
        """
        Smart CAPTCHA wait - periodically checks if CAPTCHA is solved
        Automatically proceeds when CAPTCHA disappears from page
        
        Args:
            check_interval: How often to check if CAPTCHA is solved (seconds)
            max_wait: Maximum time to wait before giving up (seconds)
        """
        print(f"\n{'='*60}")
        print("🔒 CAPTCHA DETECTED!")
        print("Please solve the CAPTCHA manually in the browser.")
        print(f"Checking every {check_interval} seconds (max {max_wait}s)...")
        print(f"{'='*60}\n")
        
        logger.info(f"CAPTCHA detected - smart wait (max {max_wait}s)")
        
        from selenium.webdriver.common.by import By
        
        elapsed = 0
        while elapsed < max_wait:
            # Check if CAPTCHA iframe still exists
            try:
                recaptcha_frames = self.driver.find_elements(
                    By.CSS_SELECTOR, 
                    "iframe[src*='recaptcha']"
                )
                
                # Check if challenge iframe is visible (means unsolved)
                challenge_visible = False
                for frame in recaptcha_frames:
                    if frame.is_displayed() and 'bframe' in frame.get_attribute('src'):
                        challenge_visible = True
                        break
                
                if not challenge_visible:
                    # Check if checkbox is checked
                    try:
                        self.driver.switch_to.frame(recaptcha_frames[0])
                        checkmark = self.driver.find_elements(
                            By.CSS_SELECTOR, 
                            "span.recaptcha-checkbox-checked"
                        )
                        self.driver.switch_to.default_content()
                        
                        if checkmark:
                            print("\n✅ CAPTCHA appears to be solved!")
                            logger.info("CAPTCHA solved - detected checkmark")
                            time.sleep(1)
                            return True
                    except Exception:
                        self.driver.switch_to.default_content()
                
                # CAPTCHA still present, wait and check again
                print(f"\r⏳ Waiting... ({elapsed}s / {max_wait}s)", end='', flush=True)
                time.sleep(check_interval)
                elapsed += check_interval
                
            except Exception as e:
                logger.debug(f"CAPTCHA check error: {e}")
                # If we can't find CAPTCHA elements, assume it's solved
                print("\n✓ CAPTCHA elements not found - assuming solved")
                return True
        
        print(f"\n\n⚠️ Max wait time ({max_wait}s) reached - proceeding anyway...")
        logger.warning(f"CAPTCHA wait timeout ({max_wait}s)")
        time.sleep(1)
        return False
    
    def notify_captcha_detected(self, wait_type='countdown'):
        """
        Main entry point for CAPTCHA handling
        
        Args:
            wait_type: Type of wait strategy:
                - 'countdown': Fixed timeout with countdown (default 30s)
                - 'interactive': Wait for user to press Enter
                - 'smart': Automatically detect when CAPTCHA is solved
        """
        if wait_type == 'interactive':
            self.wait_for_captcha_interactive()
        elif wait_type == 'smart':
            self.wait_for_captcha_smart()
        else:  # countdown (default)
            self.wait_for_captcha_solution()
