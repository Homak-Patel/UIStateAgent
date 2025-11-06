"""
Enhanced Selenium fallback support for when Playwright fails on JavaScript-heavy sites.
This module provides a resilient fallback mechanism using Selenium WebDriver with:
- Advanced wait conditions (ExpectedConditions)
- iframe and shadow DOM handling
- ActionChains for complex interactions
- Custom polling for dynamic content
- Better error recovery
"""
import os
import time
from typing import Optional, Dict, Any, List
from utils.logger import get_logger

logger = get_logger(name="selenium_fallback")

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.common.exceptions import (
        TimeoutException, 
        NoSuchElementException, 
        StaleElementReferenceException,
        ElementClickInterceptedException,
        ElementNotInteractableException,
        NoSuchFrameException
    )
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger.warning("Selenium not available - fallback will not work. Install with: pip install selenium")


class SeleniumFallback:
    """Enhanced Selenium fallback for when Playwright fails - with advanced resilience"""
    
    def __init__(self, headless: bool = True, default_timeout: int = 10):
        self.driver: Optional[webdriver.Chrome] = None
        self.headless = headless
        self.available = SELENIUM_AVAILABLE
        self.default_timeout = default_timeout
        self.current_iframe = None  # Track current iframe context
    
    def is_available(self) -> bool:
        """Check if Selenium is available"""
        return self.available
    
    def start(self, url: Optional[str] = None):
        """Start Selenium WebDriver"""
        if not self.available:
            raise RuntimeError("Selenium is not available")
        
        try:
            options = ChromeOptions()
            if self.headless:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--window-size=1920,1080')
            
            # Try to use existing Chrome installation
            try:
                self.driver = webdriver.Chrome(options=options)
            except Exception:
                # Try with service
                service = ChromeService()
                self.driver = webdriver.Chrome(service=service, options=options)
            
            if url:
                self.driver.get(url)
            
            logger.info("Selenium WebDriver started successfully")
        except Exception as e:
            logger.error(f"Failed to start Selenium: {e}")
            raise
    
    def _find_element_with_fallbacks(
        self, 
        selector: str, 
        timeout: int = None,
        search_iframes: bool = True
    ) -> Optional[Any]:
        """
        Enhanced element finding with multiple fallback strategies:
        1. Direct CSS selector
        2. XPath variations
        3. Text-based search
        4. Search within iframes
        5. Shadow DOM traversal
        """
        timeout = timeout or self.default_timeout
        wait = WebDriverWait(self.driver, timeout)
        
        # Strategy 1: Try main document first
        element = self._try_find_in_context(selector, wait)
        if element:
            return element
        
        # Strategy 2: Search in iframes if enabled
        if search_iframes:
            element = self._search_in_iframes(selector)
            if element:
                return element
        
        # Strategy 3: Try shadow DOM
        element = self._search_shadow_dom(selector)
        if element:
            return element
        
        return None
    
    def _try_find_in_context(self, selector: str, wait: WebDriverWait) -> Optional[Any]:
        """Try finding element in current context with multiple strategies"""
        strategies = [
            # CSS selector
            (By.CSS_SELECTOR, selector),
            # ID-based
            (By.ID, selector.replace('#', '')) if selector.startswith('#') else None,
            # XPath for text content
            (By.XPATH, f"//button[contains(text(), '{selector}')]"),
            (By.XPATH, f"//a[contains(text(), '{selector}')]"),
            (By.XPATH, f"//*[contains(text(), '{selector}')]"),
            # ARIA label
            (By.XPATH, f"//*[@aria-label='{selector}']"),
            # Placeholder
            (By.XPATH, f"//input[@placeholder='{selector}']"),
        ]
        
        for by, value in strategies:
            if value is None:
                continue
            try:
                element = wait.until(EC.presence_of_element_located((by, value)))
                logger.debug(f"Found element with strategy: {by}={value}")
                return element
            except (TimeoutException, NoSuchElementException):
                continue
        
        return None
    
    def _search_in_iframes(self, selector: str) -> Optional[Any]:
        """Search for element within iframes"""
        try:
            # Get all iframes
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            
            for i, iframe in enumerate(iframes):
                try:
                    self.driver.switch_to.frame(iframe)
                    self.current_iframe = i
                    
                    # Try to find element in this iframe
                    wait = WebDriverWait(self.driver, 2)  # Shorter timeout for iframe search
                    element = self._try_find_in_context(selector, wait)
                    
                    if element:
                        logger.info(f"Found element in iframe {i}")
                        return element
                    
                    # Switch back to parent
                    self.driver.switch_to.parent_frame()
                except (NoSuchFrameException, TimeoutException):
                    # Switch back and continue
                    try:
                        self.driver.switch_to.default_content()
                    except:
                        pass
                    continue
            
            # Reset to default content
            self.driver.switch_to.default_content()
            self.current_iframe = None
        except Exception as e:
            logger.debug(f"Iframe search failed: {e}")
            try:
                self.driver.switch_to.default_content()
            except:
                pass
        
        return None
    
    def _search_shadow_dom(self, selector: str) -> Optional[Any]:
        """Search within shadow DOM"""
        try:
            # Find all elements with shadow root
            script = """
            function findInShadowDOM(selector) {
                function searchShadow(root) {
                    // Try direct query
                    let elem = root.querySelector(selector);
                    if (elem) return elem;
                    
                    // Search in shadow roots
                    let elements = root.querySelectorAll('*');
                    for (let el of elements) {
                        if (el.shadowRoot) {
                            elem = searchShadow(el.shadowRoot);
                            if (elem) return elem;
                        }
                    }
                    return null;
                }
                return searchShadow(document);
            }
            return findInShadowDOM(arguments[0]);
            """
            element = self.driver.execute_script(script, selector)
            if element:
                logger.info(f"Found element in shadow DOM: {selector}")
                return element
        except Exception as e:
            logger.debug(f"Shadow DOM search failed: {e}")
        
        return None
    
    def _wait_for_dom_ready(self, timeout: int = 10):
        """Wait for DOM to be fully ready beyond document.readyState"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Check document ready state
                ready_state = self.driver.execute_script("return document.readyState")
                if ready_state != "complete":
                    time.sleep(0.1)
                    continue
                
                # Check for pending network requests
                pending = self.driver.execute_script("""
                    const entries = performance.getEntriesByType('resource');
                    const now = performance.now();
                    return entries.some(e => e.responseEnd === 0 && (now - e.startTime) < 1000);
                """)
                
                if not pending:
                    return True
                
                time.sleep(0.1)
            except:
                time.sleep(0.1)
        
        return False
    
    def click(self, selector: str, timeout: int = None, use_action_chains: bool = False) -> bool:
        """
        Enhanced click with multiple resilience strategies:
        1. Wait for element to be clickable
        2. Handle stale elements
        3. Try ActionChains for complex interactions
        4. Retry on intercept exceptions
        5. Search in iframes if needed
        """
        if not self.driver:
            raise RuntimeError("Selenium driver not started")
        
        timeout = timeout or self.default_timeout
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Wait for DOM to be ready
                self._wait_for_dom_ready(timeout=5)
                
                # Find element with advanced search
                element = self._find_element_with_fallbacks(selector, timeout)
                
                if not element:
                    raise NoSuchElementException(f"Element not found: {selector}")
                
                # Wait for element to be clickable
                wait = WebDriverWait(self.driver, timeout)
                element = wait.until(EC.element_to_be_clickable(element))
                
                # Scroll into view with offset to avoid fixed headers
                self.driver.execute_script("""
                    arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});
                    window.scrollBy(0, -100);
                """, element)
                time.sleep(0.3)  # Wait for scroll animation
                
                # Click strategy based on use_action_chains flag
                if use_action_chains:
                    # Use ActionChains for complex interactions
                    actions = ActionChains(self.driver)
                    actions.move_to_element(element).pause(0.1).click().perform()
                    logger.info(f"✓ Selenium ActionChains click succeeded: {selector}")
                else:
                    # Try regular click first
                    try:
                        element.click()
                        logger.info(f"✓ Selenium click succeeded: {selector}")
                    except (ElementClickInterceptedException, ElementNotInteractableException):
                        # Fallback to JavaScript click
                        self.driver.execute_script("arguments[0].click();", element)
                        logger.info(f"✓ Selenium JS click succeeded: {selector}")
                
                # Wait for any animations/transitions
                time.sleep(0.3)
                return True
                
            except StaleElementReferenceException:
                if attempt < max_retries - 1:
                    logger.warning(f"Stale element, retrying ({attempt + 1}/{max_retries})")
                    time.sleep(0.5)
                    continue
                else:
                    logger.error(f"Selenium click failed after {max_retries} attempts (stale element)")
                    return False
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Click attempt {attempt + 1} failed: {e}, retrying...")
                    time.sleep(0.5)
                    continue
                else:
                    logger.error(f"Selenium click failed after {max_retries} attempts: {e}")
                    return False
        
        return False
    
    def type(self, selector: str, text: str, clear_first: bool = True, timeout: int = None) -> bool:
        """
        Enhanced type with resilience:
        1. Find element with fallback strategies
        2. Handle stale elements
        3. Character-by-character typing for JS validation
        4. Trigger proper input events
        """
        if not self.driver:
            raise RuntimeError("Selenium driver not started")
        
        timeout = timeout or self.default_timeout
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Wait for DOM
                self._wait_for_dom_ready(timeout=5)
                
                # Find element with advanced search
                element = self._find_element_with_fallbacks(selector, timeout)
                
                if not element:
                    raise NoSuchElementException(f"Element not found: {selector}")
                
                # Wait for element to be visible and enabled
                wait = WebDriverWait(self.driver, timeout)
                element = wait.until(EC.element_to_be_clickable(element))
                
                # Scroll into view
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                time.sleep(0.2)
                
                # Focus the element
                element.click()
                time.sleep(0.1)
                
                # Clear if needed
                if clear_first:
                    try:
                        element.clear()
                    except:
                        # Fallback: select all and delete
                        from selenium.webdriver.common.keys import Keys
                        element.send_keys(Keys.CONTROL + "a")
                        element.send_keys(Keys.DELETE)
                    time.sleep(0.1)
                
                # Type character by character for JS validation
                for char in text:
                    element.send_keys(char)
                    time.sleep(0.02)  # Small delay for JS to process
                
                # Trigger input events for JS frameworks
                self.driver.execute_script("""
                    arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));
                """, element)
                
                logger.info(f"✓ Selenium type succeeded: {selector}")
                return True
                
            except StaleElementReferenceException:
                if attempt < max_retries - 1:
                    logger.warning(f"Stale element on type, retrying ({attempt + 1}/{max_retries})")
                    time.sleep(0.5)
                    continue
                else:
                    logger.error(f"Selenium type failed after {max_retries} attempts (stale element)")
                    return False
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Type attempt {attempt + 1} failed: {e}, retrying...")
                    time.sleep(0.5)
                    continue
                else:
                    logger.error(f"Selenium type failed after {max_retries} attempts: {e}")
                    return False
        
        return False
    
    def hover(self, selector: str, timeout: int = None) -> bool:
        """Hover over an element using ActionChains"""
        if not self.driver:
            raise RuntimeError("Selenium driver not started")
        
        timeout = timeout or self.default_timeout
        
        try:
            # Find element
            element = self._find_element_with_fallbacks(selector, timeout)
            
            if not element:
                raise NoSuchElementException(f"Element not found: {selector}")
            
            # Wait for element to be visible
            wait = WebDriverWait(self.driver, timeout)
            element = wait.until(EC.visibility_of(element))
            
            # Perform hover with ActionChains
            actions = ActionChains(self.driver)
            actions.move_to_element(element).pause(0.2).perform()
            
            logger.info(f"✓ Selenium hover succeeded: {selector}")
            return True
        except Exception as e:
            logger.error(f"Selenium hover failed: {e}")
            return False
    
    def wait_for_element(self, selector: str, state: str = "visible", timeout: int = None) -> bool:
        """
        Wait for element with different states:
        - visible: Element is visible
        - clickable: Element is clickable
        - present: Element exists in DOM
        """
        if not self.driver:
            raise RuntimeError("Selenium driver not started")
        
        timeout = timeout or self.default_timeout
        wait = WebDriverWait(self.driver, timeout)
        
        try:
            if state == "visible":
                wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))
            elif state == "clickable":
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
            elif state == "present":
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            else:
                raise ValueError(f"Unknown state: {state}")
            
            logger.info(f"✓ Element {selector} is {state}")
            return True
        except TimeoutException:
            logger.warning(f"Timeout waiting for element {selector} to be {state}")
            return False
    
    def scroll_to_element(self, selector: str) -> bool:
        """Scroll to an element using Selenium"""
        if not self.driver:
            raise RuntimeError("Selenium driver not started")
        
        try:
            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
            logger.info(f"✓ Selenium scroll succeeded: {selector}")
            return True
        except Exception as e:
            logger.error(f"Selenium scroll failed: {e}")
            return False
    
    def get_url(self) -> str:
        """Get current URL"""
        if not self.driver:
            return ""
        return self.driver.current_url
    
    def close(self):
        """Close Selenium WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

