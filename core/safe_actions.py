import time
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, ElementClickInterceptedException
from core.logger import logger
from core.human_behavior import HumanBehavior

class SafeActions:
    def __init__(self, driver):
        self.driver = driver
        self.human = HumanBehavior(driver)
        
    def _random_sleep(self, min_s=2.1, max_s=4.5):
        """Use HumanBehavior for consistent random delays"""
        HumanBehavior.random_delay(min_s, max_s)

    def _micro_move(self, element):
        """Moves mouse slightly offset from center before clicking."""
        try:
            action = ActionChains(self.driver)
            # Standard move to element
            action.move_to_element(element)
            # Add small random offset
            x_offset = random.randint(1, 10)
            y_offset = random.randint(1, 10)
            action.move_by_offset(x_offset, y_offset)
            action.perform()
        except Exception:
            # Fallback if move fails (e.g. element hidden?), just ignore
            pass

    def safe_click(self, selector, by=By.CSS_SELECTOR, timeout=10, retries=3):
        """
        Attempts to find and click an element with retries on Stale/Intercepted exceptions.
        Tries JS click as a fallback when normal click is intercepted.
        """
        attempt = 0
        while attempt < retries:
            try:
                element = self.driver.find_element(by, selector)
                self._micro_move(element)
                self._random_sleep(0.5, 1.5)
                try:
                    element.click()
                    logger.debug(f"Clicked element: {selector}")
                    return True
                except ElementClickInterceptedException as e:
                    # Try JS click as fallback
                    try:
                        self.driver.execute_script("arguments[0].click();", element)
                        logger.debug(f"Clicked element via JS fallback: {selector}")
                        return True
                    except Exception:
                        logger.warning(f"JS click fallback failed for {selector}, will retry ({attempt+1}/{retries})")
                        time.sleep(1)
                        attempt += 1
                        continue
            except StaleElementReferenceException as e:
                logger.warning(f"Click failed (StaleElementReferenceException) on {selector}, retrying ({attempt+1}/{retries})")
                time.sleep(1)
                attempt += 1
            except NoSuchElementException:
                logger.error(f"Element not found: {selector}")
                return False
            except Exception as e:
                logger.error(f"Unexpected error clicking {selector}: {e}")
                return False
        return False

    def safe_click_element(self, element, retries: int = 3):
        """Attempts to click a WebElement directly with retries and JS fallback."""
        attempt = 0
        while attempt < retries:
            try:
                self._micro_move(element)
                self._random_sleep(0.3, 0.9)
                try:
                    element.click()
                    return True
                except ElementClickInterceptedException:
                    try:
                        self.driver.execute_script("arguments[0].click();", element)
                        return True
                    except Exception:
                        attempt += 1
                        time.sleep(0.8)
                        continue
            except StaleElementReferenceException:
                time.sleep(0.8)
                attempt += 1
            except Exception as e:
                logger.debug(f"safe_click_element unexpected error: {e}")
                return False
        return False

    def safe_type(self, selector, text, by=By.CSS_SELECTOR, retries=3):
        """Type text with human-like delays between keystrokes"""
        attempt = 0
        while attempt < retries:
            try:
                element = self.driver.find_element(by, selector)
                element.clear()
                self._random_sleep(0.3, 0.7)
                # Use HumanBehavior for more realistic typing
                self.human.human_type(element, text)
                return True
            except StaleElementReferenceException:
                time.sleep(1)
                attempt += 1
            except Exception as e:
                logger.error(f"Error typing in {selector}: {e}")
                return False
        return False

    def check_exists(self, selector, by=By.CSS_SELECTOR):
        try:
            self.driver.find_element(by, selector)
            return True
        except NoSuchElementException:
            return False
