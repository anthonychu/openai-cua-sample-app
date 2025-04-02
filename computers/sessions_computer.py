import json
import os
import time
from typing import Literal, Tuple, Dict, List, Union, Optional
from playwright.sync_api import Browser, Page, BrowserContext, Error as PlaywrightError
from .base_playwright import BasePlaywrightComputer
from browserbase import Browserbase
from dotenv import load_dotenv
import base64
from .sessions import CodeInterpreterSession

load_dotenv()


# Optional: key mapping if your model uses "CUA" style keys
CUA_KEY_TO_PLAYWRIGHT_KEY = {
    "/": "Divide",
    "\\": "Backslash",
    "alt": "Alt",
    "arrowdown": "ArrowDown",
    "arrowleft": "ArrowLeft",
    "arrowright": "ArrowRight",
    "arrowup": "ArrowUp",
    "backspace": "Backspace",
    "capslock": "CapsLock",
    "cmd": "Meta",
    "ctrl": "Control",
    "delete": "Delete",
    "end": "End",
    "enter": "Enter",
    "esc": "Escape",
    "home": "Home",
    "insert": "Insert",
    "option": "Alt",
    "pagedown": "PageDown",
    "pageup": "PageUp",
    "shift": "Shift",
    "space": " ",
    "super": "Meta",
    "tab": "Tab",
    "win": "Meta",
}


class SessionsCodeInterpreterBrowser():
    environment: Literal["browser"] = "browser"
    dimensions = (1024, 768)
    
    def __init__(
        self,
        width: int = 1024,
        height: int = 768,
        virtual_mouse: bool = False,
    ):
        """
        Initialize the Browserbase instance. Additional configuration options for features such as persistent cookies, ad blockers, file downloads and more can be found in the Browserbase API documentation: https://docs.browserbase.com/reference/api/create-a-session

        Args:
            width (int): The width of the browser viewport. Default is 1024.
            height (int): The height of the browser viewport. Default is 768.
            virtual_mouse (bool): Whether to enable the virtual mouse cursor. Default is True.
        """
        self.aca_session = CodeInterpreterSession(pool_management_endpoint=os.getenv("POOL_MANAGEMENT_ENDPOINT"))
        self.dimensions = (width, height)
        self.virtual_mouse = virtual_mouse


    def __enter__(self):
        self._get_browser_and_page()
        return self


    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


    def _get_browser_and_page(self) -> Tuple[Browser, Page]:
        """
        Initialize the code interpreter session.

        Returns:
            Tuple[Browser, Page]: A tuple containing the connected browser and page objects.
        """

        print(f'Using session ID: {self.aca_session.session_id}')

        width, height = self.dimensions

        script = f"""
        from playwright.async_api import async_playwright

        width = {width}
        height = {height}
        virtual_mouse = {str(self.virtual_mouse)}

        launch_args = [f"--window-size={{width}},{{height}}", "--disable-extensions", "--disable-file-system"]

        p = await async_playwright().start()

        browser = await p.chromium.launch(
            headless=True,
            args=launch_args
        )

        context = await browser.new_context()

        page = await context.new_page()
        await page.set_viewport_size({{"width": width, "height": height}})

        await page.goto("https://bing.com")
        await page.wait_for_load_state("networkidle")
        """

        self.aca_session.execute(script)


    def get_current_url(self) -> str:
        print("*** Getting current URL")
        script = """
        page.url
        """
        response = self.aca_session.execute(script)
        return response['result']

    screenshot_count = 0
    def screenshot(self) -> str:
            """Capture only the viewport (not full_page)."""
            print("*** Taking screenshot...")

            script = """
            s = await page.screenshot(
                full_page=False,
                path='/mnt/data/screenshot.png'
            )
            """

            self.aca_session.execute(script)

            binary_data = self.aca_session.download_file(remote_file_path="screenshot.png")
            base64_data = base64.b64encode(binary_data.getvalue()).decode('utf-8')

            self.screenshot_count += 1
            os.makedirs("logs", exist_ok=True)
            with open(f"logs/screenshot{self.screenshot_count}.png", "wb") as f:
                f.write(base64.b64decode(base64_data))

            return base64_data


    def click(self, x: int, y: int, button: str = "left") -> None:
        print(f"*** Clicking at ({x}, {y}) with button '{button}'")
        match button:
            case "back":
                self.back()
                return
            case "forward":
                self.forward()
                return
            case "wheel":
                script = f"""
                await page.mouse.wheel({{"x": {x}, "y": {y}}})
                """
            case _:
                button_mapping = {"left": "left", "right": "right"}
                button_type = button_mapping.get(button, "left")
                script = f"""
                await page.mouse.click({x}, {y}, button="{button_type}")
                """
        self.aca_session.execute(script)


    def double_click(self, x: int, y: int) -> None:
        print(f"*** Double-clicking at ({x}, {y})")
        script = f"""
        await page.mouse.dblclick({{"x": {x}, "y": {y}}})
        """
        self.aca_session.execute(script)


    def scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> None:
        print(f"*** Scrolling at ({x}, {y}) with scroll ({scroll_x}, {scroll_y})")
        script = f"""
        await page.mouse.move({x}, {y})
        await page.evaluate(f"window.scrollBy({scroll_x}, {scroll_y})")
        """
        self.aca_session.execute(script)

    
    def type(self, text: str) -> None:
        print(f"*** Typing text: {text}")
        # Escape special characters in the text
        escaped_text = text.replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
        
        script = f"""
        await page.keyboard.type("{escaped_text}")
        """
        self.aca_session.execute(script)


    def wait(self, ms: int = 1000) -> None:
        print(f"*** Waiting for {ms} milliseconds")
        time.sleep(ms / 1000)

        
    def move(self, x: int, y: int) -> None:
        print(f"*** Moving mouse to ({x}, {y})")
        script = f"""
        await page.mouse.move({x}, {y})
        """
        self.aca_session.execute(script)
    

    def keypress(self, keys: List[str]) -> None:
        print(f"*** Pressing keys: {keys}")
        mapped_keys = [CUA_KEY_TO_PLAYWRIGHT_KEY.get(key.lower(), key) for key in keys]
        script = f"""
        mapped_keys = {mapped_keys}
        for key in mapped_keys:
            await page.keyboard.down(key)
        for key in reversed(mapped_keys):
            await page.keyboard.up(key)
        """
        self.aca_session.execute(script)


    def drag(self, path: List[Dict[str, int]]) -> None:
        print(f"*** Dragging along path: {path}")
        if not path:
            return
        script = f"""
        path = {path}
        await page.mouse.move({path[0]["x"]}, {path[0]["y"]})
        await page.mouse.down()
        for point in path[1:]:
            await page.mouse.move(point["x"], point["y"])
        await page.mouse.up()
        """
        self.aca_session.execute(script)


    # --- Extra browser-oriented actions ---
    def goto(self, url: str) -> None:
        print(f"*** Navigating to URL: {url}")
        try:
            script = f"""
            await page.goto("{url}")
            """
            result = self.aca_session.execute(script)
            print(json.dumps(result, indent=4))
        except Exception as e:
            print(f"Error navigating to {url}: {e}")


    def back(self) -> None:
        print("*** Going back in browser history")
        script = """
        await page.go_back()
        """
        self.aca_session.execute(script)


    def forward(self) -> None:
        print("*** Going forward in browser history")
        script = """
        await page.go_forward()
        """
        self.aca_session.execute(script)


