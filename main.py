import asyncio
import logging
import re, json
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, ElementHandle
from src.llm.load_model import LoadGemini

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class WebsiteNavigator:
    def __init__(self):
        self.gemini_object = LoadGemini()
        self.MAX_TRIES=100
        self.url = None

    async def visit_website(self, prompt: str) -> Optional[Dict]:
        """
        Visits a website based on a prompt and extracts clickable elements.
        Returns navigation instructions from Gemini.
        """
        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.launch(headless=False, slow_mo=50)
                page = await browser.new_page()

                self.url = self._extract_url_from_prompt(prompt)
                if not self.url:
                    raise ValueError("No valid URL found in the prompt.")

                logger.info(f"Visiting URL: {self.url}")
                await page.goto(self.url, timeout=30000)

                for _ in range(self.MAX_TRIES):
                    elements = await self._extract_clickable_elements(page)
                    if not elements:
                        logger.warning("No clickable elements found on the page")
                        return None

                    processed_tags = await self._process_elements(elements)
                    
                    # Handle Gemini response synchronously or asynchronously based on implementation
                    try:
                        if asyncio.iscoroutinefunction(self.gemini_object.gemini_response):
                            response = await self.gemini_object.gemini_response(
                                self._create_gemini_prompt(prompt, processed_tags)
                            )
                        else:
                            response = self.gemini_object.gemini_response(
                                self._create_gemini_prompt(prompt, processed_tags)
                            )
                        check_if_clicked = await self._click_recommended_elements(page, response)
                        if check_if_clicked:
                            continue
                        else:
                            return False
                    except Exception as e:
                        logger.error(f"Error getting Gemini response: {str(e)}")
                        return None

            except Exception as e:
                logger.error(f"An error occurred: {str(e)}")
                return None
            finally:
                if browser:
                    await browser.close()
                    logger.info("Browser closed.")

    def _extract_url_from_prompt(self, prompt: str) -> Optional[str]:
        """Extracts URL from a given prompt with validation."""
        match = re.search(r"https?://[^\s\"]+", prompt)
        if not match:
            return None
        url = match.group(0)
        return url if url.startswith(('http://', 'https://')) else None

    async def _extract_clickable_elements(self, page: Page) -> List[ElementHandle]:
        """Extracts all clickable elements from the page."""
        elements = await page.query_selector_all("a, button")
        logger.info(f"Found {len(elements)} clickable elements")
        return elements

    async def _process_elements(self, elements: List[ElementHandle]) -> List[Dict]:
        """Processes extracted elements into a structured format."""
        processed_tags = []
        for element in elements:
            try:
                tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
                text = (await element.inner_text()).strip()
                attributes = await element.evaluate(
                    "el => Object.fromEntries([...el.attributes].map(attr => [attr.name, attr.value]))"
                )
                visible = await element.is_visible()

                if visible:  # Only include visible elements
                    processed_tags.append({
                        "tag": tag_name,
                        "content": {
                            "text": text if text else "[No Text]",
                            "attributes": attributes,
                            "visible": visible
                        }
                    })
                    logger.debug(f"Processed element: {tag_name} | Text: {text}")
            except Exception as e:
                logger.error(f"Error processing element: {str(e)}")
                continue

        return processed_tags

    async def _extract_json_from_gemini_response(self, recommended_action:str):
        clean_json = re.sub(r"^```json|```$", "", recommended_action, flags=re.MULTILINE).strip()

        # Parse JSON
        data = json.loads(clean_json)
        return data

    async def _click_recommended_elements(self, page: Page, recommended_action: str):
        logger.info(f"Gemini response \n {recommended_action}")
        recommended_action = await self._extract_json_from_gemini_response(recommended_action)

        try:
            logger.info("Gemini response successfully parsed as json")
        except Exception as e:
            logger.error(f"Error processing gemini response: {str(e)}")
            return False
        
        try:
        # Corrected access to element_text
            element_text = recommended_action['recommended_action']['element_text']
            logger.info(f"Attempting to click: {element_text}")

            # Extract href safely
            href = recommended_action['recommended_action']['element_attributes'].get('href')
            next_steps = recommended_action["next_steps"][0]
            print(logging.info(f"Next steps: {next_steps}"))
            if not href:
                logger.error("No href found in element attributes")
                return False
            
            logger.info(f"The requested attribute: {href}")

            # Define selector
            selectors = [
                f"a[href='{href}']",
                f"a:has-text('{element_text.strip()}')"  # Alternative selector using text
            ]

            # Try clicking using each selector
            for selector in selectors:
                try:
                    await page.click(selector, timeout=5000)
                    logger.info(f"Successfully clicked element using selector: {selector}")
                    await page.wait_for_timeout(10000)  # Ensure the page loads
                    
                    if next_steps == "exit_now":
                        return False
                    else: return True

                except Exception as e:
                    logger.warning(f"Failed to click with selector {selector}: {str(e)}")
                    continue

            logger.error("Failed to click element using all selectors")
            return False

        except Exception as e:
            logger.error(f"Error clicking recommended element: {str(e)}")
            return False

    def _create_gemini_prompt(self, user_prompt: str, tags: List[Dict]) -> str:
        """Creates a structured response from Gemini."""
        return f"""
            Task: {user_prompt}
            Website Elements Analysis:
            Found {len(tags)} clickable elements.
            
            Please analyze these elements and provide:
            1. The exact element to click on for completing the task
            2. Any subsequent steps needed
            3. Confirmation that this is the optimal path
            4. If you determine that the task has been fully accomplished, set "next_steps": ["exit_now"].
            
            Available elements: {tags}
            
            Return response as JSON:
            {{
                "recommended_action": {{
                    "element_tag": "string",
                    "element_text": "string",
                    "element_attributes": {{}},
                    "confidence": "high|medium|low",
                    "reasoning": "string"
                }},
                "next_steps": ["string"],
                "alternative_paths": ["string"]
            }}
        """
    

async def main():
    try:
        navigator = WebsiteNavigator()
        prompt = "Go to https://file-examples.com/ and download the smallest doc file."
        result = await navigator.visit_website(prompt)
        if result:
            print("\n🤖 Navigation Instructions:")
            print(result)
    except Exception as e:
        logger.error(f"Main execution error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())