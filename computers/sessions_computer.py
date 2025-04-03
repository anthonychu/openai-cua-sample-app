import os
import time
from typing import Literal, Dict, List
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
    ):
        """
        Initialize a sessions code interpreter with Playwright and Chromium.

        Args:
            width (int): The width of the browser viewport. Default is 1024.
            height (int): The height of the browser viewport. Default is 768.
        """
        self.aca_session = CodeInterpreterSession(pool_management_endpoint=os.getenv("POOL_MANAGEMENT_ENDPOINT"))
        self.dimensions = (width, height)


    def __enter__(self):
        self._get_browser_and_page()
        return self


    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


    def _get_browser_and_page(self):
        """
        Initialize the code interpreter session.
        """

        print(f'Using session ID: {self.aca_session.session_id}')

        width, height = self.dimensions

        script = f"""
        from playwright.async_api import async_playwright

        width = {width}
        height = {height}

        launch_args = [f"--window-size={{width}},{{height}}", "--disable-extensions", "--disable-file-system"]

        p = await async_playwright().start()

        browser = await p.chromium.launch(
            headless=True,
            args=launch_args
        )

        context = await browser.new_context()

        def _handle_new_page(new_page):
            global page
            print("New page created")
            page = new_page

        context.on("page", _handle_new_page)

        page = await context.new_page()
        await page.set_viewport_size({{"width": width, "height": height}})

        await page.goto("https://bing.com")
        await page.wait_for_load_state("networkidle")
        """

        self.aca_session.execute(script)


    def get_current_url(self) -> str:
        script = """
        page.url
        """
        response = self.aca_session.execute(script)
        return response['result']

    screenshot_count = 0
    def screenshot(self) -> str:
            """Capture only the viewport (not full_page)."""

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
        script = f"""
        await page.mouse.dblclick({{"x": {x}, "y": {y}}})
        """
        self.aca_session.execute(script)


    def scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> None:
        script = f"""
        await page.mouse.move({x}, {y})
        await page.evaluate(f"window.scrollBy({scroll_x}, {scroll_y})")
        """
        self.aca_session.execute(script)

    
    def type(self, text: str) -> None:
        # Escape special characters in the text
        escaped_text = text.replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
        
        script = f"""
        await page.keyboard.type("{escaped_text}")
        """
        self.aca_session.execute(script)


    def wait(self, ms: int = 1000) -> None:
        time.sleep(ms / 1000)

        
    def move(self, x: int, y: int) -> None:
        script = f"""
        await page.mouse.move({x}, {y})
        """
        self.aca_session.execute(script)
    

    def keypress(self, keys: List[str]) -> None:
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
        try:
            script = f"""
            await page.goto("{url}")
            """
            result = self.aca_session.execute(script)
        except Exception as e:
            print(f"Error navigating to {url}: {e}")


    def back(self) -> None:
        script = """
        await page.go_back()
        """
        self.aca_session.execute(script)


    def forward(self) -> None:
        script = """
        await page.go_forward()
        """
        self.aca_session.execute(script)
