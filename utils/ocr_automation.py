"""
OCR-based automation fallback for visual UI interaction.
This is the final fallback layer when both Playwright and Selenium fail.

Uses OCR to:
1. Detect elements visually (text, buttons, inputs)
2. Calculate click coordinates
3. Perform interactions based on visual recognition
4. Handle canvas-rendered or non-semantic UIs

This layer is only activated when DOM-based automation fails completely.
"""
import os
import time
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from utils.logger import get_logger

logger = get_logger(name="ocr_automation")

# Try to import OCR dependencies
try:
    import cv2
    import numpy as np
    from PIL import Image, ImageGrab
    import pytesseract
    import pyautogui
    OCR_AVAILABLE = True
    logger.info("OCR automation dependencies available")
except ImportError as e:
    OCR_AVAILABLE = False
    logger.warning(f"OCR automation not available - install dependencies: pip install opencv-python pillow pytesseract pyautogui. Error: {e}")


class OCRAutomation:
    """
    OCR-based automation for visual UI interaction.
    Final fallback when DOM-based automation fails.
    """
    
    def __init__(self, confidence_threshold: float = 0.7):
        self.available = OCR_AVAILABLE
        self.confidence_threshold = confidence_threshold
        self.last_screenshot: Optional[np.ndarray] = None
        self.screen_width, self.screen_height = None, None
        
        if self.available:
            # Get screen dimensions
            self.screen_width, self.screen_height = pyautogui.size()
            # Set PyAutoGUI safety features
            pyautogui.FAILSAFE = True  # Move mouse to corner to abort
            pyautogui.PAUSE = 0.5  # Pause between actions
    
    def is_available(self) -> bool:
        """Check if OCR automation is available"""
        return self.available
    
    def capture_screen(self, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[np.ndarray]:
        """
        Capture screenshot for OCR analysis
        
        Args:
            region: Optional (x, y, width, height) tuple to capture specific region
        
        Returns:
            OpenCV image array (BGR format)
        """
        if not self.available:
            return None
        
        try:
            if region:
                x, y, width, height = region
                screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
            else:
                screenshot = ImageGrab.grab()
            
            # Convert PIL image to OpenCV format
            img_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            self.last_screenshot = img_cv
            return img_cv
        except Exception as e:
            logger.error(f"Failed to capture screen: {e}")
            return None
    
    def find_text_on_screen(
        self, 
        text: str, 
        region: Optional[Tuple[int, int, int, int]] = None,
        case_sensitive: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Find text on screen using OCR
        
        Returns:
            Dictionary with location info: {x, y, width, height, confidence}
        """
        if not self.available:
            return None
        
        try:
            # Capture screen
            img = self.capture_screen(region)
            if img is None:
                return None
            
            # Perform OCR
            ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            
            # Search for matching text
            search_text = text if case_sensitive else text.lower()
            
            for i, detected_text in enumerate(ocr_data['text']):
                if not detected_text.strip():
                    continue
                
                compare_text = detected_text if case_sensitive else detected_text.lower()
                confidence = float(ocr_data['conf'][i])
                
                # Check for match
                if search_text in compare_text and confidence > self.confidence_threshold * 100:
                    x = ocr_data['left'][i]
                    y = ocr_data['top'][i]
                    width = ocr_data['width'][i]
                    height = ocr_data['height'][i]
                    
                    # Adjust coordinates if region was specified
                    if region:
                        x += region[0]
                        y += region[1]
                    
                    result = {
                        'x': x,
                        'y': y,
                        'width': width,
                        'height': height,
                        'text': detected_text,
                        'confidence': confidence / 100.0
                    }
                    
                    logger.info(f"Found text '{text}' at ({x}, {y}) with confidence {confidence:.1f}%")
                    return result
            
            logger.warning(f"Text '{text}' not found on screen")
            return None
            
        except Exception as e:
            logger.error(f"OCR text search failed: {e}")
            return None
    
    def click_on_text(
        self, 
        text: str, 
        region: Optional[Tuple[int, int, int, int]] = None,
        offset_x: int = 0,
        offset_y: int = 0
    ) -> bool:
        """
        Click on text found via OCR
        
        Args:
            text: Text to find and click
            region: Optional region to search in
            offset_x, offset_y: Offset from center of text (useful for buttons)
        """
        if not self.available:
            return False
        
        try:
            # Find text location
            location = self.find_text_on_screen(text, region)
            
            if not location:
                return False
            
            # Calculate click coordinates (center of text + offset)
            click_x = location['x'] + location['width'] // 2 + offset_x
            click_y = location['y'] + location['height'] // 2 + offset_y
            
            # Move mouse and click
            pyautogui.moveTo(click_x, click_y, duration=0.3)
            time.sleep(0.1)
            pyautogui.click()
            
            logger.info(f"✓ OCR click succeeded on text '{text}' at ({click_x}, {click_y})")
            return True
            
        except Exception as e:
            logger.error(f"OCR click failed: {e}")
            return False
    
    def type_text(self, text: str, interval: float = 0.05) -> bool:
        """
        Type text character-by-character
        
        Args:
            text: Text to type
            interval: Delay between keystrokes
        """
        if not self.available:
            return False
        
        try:
            pyautogui.write(text, interval=interval)
            logger.info(f"✓ OCR type succeeded: {len(text)} characters")
            return True
        except Exception as e:
            logger.error(f"OCR type failed: {e}")
            return False
    
    def click_at_coordinates(self, x: int, y: int, clicks: int = 1) -> bool:
        """Click at specific coordinates"""
        if not self.available:
            return False
        
        try:
            pyautogui.click(x, y, clicks=clicks)
            logger.info(f"✓ OCR click at ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"OCR click at coordinates failed: {e}")
            return False
    
    def scroll(self, amount: int, direction: str = "down") -> bool:
        """
        Scroll the page
        
        Args:
            amount: Scroll amount (positive integer)
            direction: 'up' or 'down'
        """
        if not self.available:
            return False
        
        try:
            scroll_amount = amount if direction == "down" else -amount
            pyautogui.scroll(scroll_amount)
            logger.info(f"✓ OCR scroll {direction}: {amount}")
            return True
        except Exception as e:
            logger.error(f"OCR scroll failed: {e}")
            return False
    
    def detect_buttons(
        self, 
        region: Optional[Tuple[int, int, int, int]] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect button-like elements using OCR and image processing
        
        Returns list of detected buttons with their properties
        """
        if not self.available:
            return []
        
        try:
            # Capture screen
            img = self.capture_screen(region)
            if img is None:
                return []
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply edge detection
            edges = cv2.Canny(gray, 50, 150)
            
            # Find contours (potential buttons)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            buttons = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                
                # Filter by size (typical button dimensions)
                if 20 < w < 300 and 15 < h < 100:
                    # Adjust if region specified
                    if region:
                        x += region[0]
                        y += region[1]
                    
                    buttons.append({
                        'x': x,
                        'y': y,
                        'width': w,
                        'height': h,
                        'center_x': x + w // 2,
                        'center_y': y + h // 2
                    })
            
            logger.debug(f"Detected {len(buttons)} potential button elements")
            return buttons
            
        except Exception as e:
            logger.error(f"Button detection failed: {e}")
            return []
    
    def find_and_click_button(
        self, 
        button_text: str,
        region: Optional[Tuple[int, int, int, int]] = None
    ) -> bool:
        """
        Find a button by text and click it
        Combines OCR text detection with button shape detection
        """
        if not self.available:
            return False
        
        try:
            # First try direct text click
            if self.click_on_text(button_text, region):
                return True
            
            # Fallback: detect buttons and check for matching text
            buttons = self.detect_buttons(region)
            
            for button in buttons:
                # Extract button region
                button_region = (
                    button['x'],
                    button['y'],
                    button['width'],
                    button['height']
                )
                
                # Search for text within button region
                text_location = self.find_text_on_screen(button_text, button_region)
                
                if text_location:
                    # Click center of button
                    pyautogui.click(button['center_x'], button['center_y'])
                    logger.info(f"✓ OCR button click succeeded: '{button_text}'")
                    return True
            
            logger.warning(f"Button with text '{button_text}' not found")
            return False
            
        except Exception as e:
            logger.error(f"OCR button click failed: {e}")
            return False
    
    def find_input_field_and_type(
        self,
        label_text: str,
        value: str,
        region: Optional[Tuple[int, int, int, int]] = None
    ) -> bool:
        """
        Find an input field by its label and type text into it
        """
        if not self.available:
            return False
        
        try:
            # Find label text
            label_location = self.find_text_on_screen(label_text, region)
            
            if not label_location:
                logger.warning(f"Label '{label_text}' not found")
                return False
            
            # Click slightly to the right and below the label (typical input field position)
            input_x = label_location['x'] + label_location['width'] + 20
            input_y = label_location['y'] + label_location['height'] // 2
            
            # Click to focus input field
            pyautogui.click(input_x, input_y)
            time.sleep(0.2)
            
            # Clear existing content (Ctrl+A, Delete)
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            pyautogui.press('delete')
            time.sleep(0.1)
            
            # Type the value
            self.type_text(value)
            
            logger.info(f"✓ OCR input field type succeeded for label '{label_text}'")
            return True
            
        except Exception as e:
            logger.error(f"OCR input field type failed: {e}")
            return False
    
    def wait_for_text(
        self,
        text: str,
        timeout: int = 10,
        region: Optional[Tuple[int, int, int, int]] = None
    ) -> bool:
        """
        Wait for text to appear on screen
        """
        if not self.available:
            return False
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            location = self.find_text_on_screen(text, region)
            if location:
                logger.info(f"Text '{text}' appeared after {time.time() - start_time:.1f}s")
                return True
            time.sleep(0.5)
        
        logger.warning(f"Text '{text}' did not appear within {timeout}s")
        return False
    
    def save_screenshot(self, filepath: str) -> bool:
        """Save the last captured screenshot"""
        if not self.available or self.last_screenshot is None:
            return False
        
        try:
            cv2.imwrite(filepath, self.last_screenshot)
            logger.info(f"Screenshot saved to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to save screenshot: {e}")
            return False

