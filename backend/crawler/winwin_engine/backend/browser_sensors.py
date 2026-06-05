"""
Shared Selenium sensor helpers for UI automation.

These helpers avoid blind sleeps by checking whether the browser state is
actually ready for the next action: an element is visible, stable, focused, and
text was really entered.
"""

from __future__ import annotations

import time
from typing import Callable, Iterable, Optional, Sequence, Tuple

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


LogFunc = Optional[Callable[[str], None]]
Selector = Tuple[str, str]


class BrowserSensorError(Exception):
    """Raised when a browser readiness sensor cannot satisfy its condition."""


def _log(log: LogFunc, message: str) -> None:
    if log:
        try:
            log(message)
        except Exception:
            pass


def normalize_text(text: str) -> str:
    return " ".join((text or "").replace("\u200b", "").split())


def is_driver_alive(driver) -> bool:
    try:
        _ = driver.current_url
        return True
    except Exception:
        return False


def apply_quiet_chrome_options(options):
    """Suppress Chrome UI prompts that interfere with automation."""
    for arg in (
        "--disable-notifications",
        "--disable-popup-blocking",
        "--disable-save-password-bubble",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-session-crashed-bubble",
        "--hide-crash-restore-bubble",
    ):
        try:
            options.add_argument(arg)
        except Exception:
            pass

    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.password_manager_leak_detection": False,
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_setting_values.popups": 2,
        "profile.default_content_setting_values.geolocation": 2,
        "safebrowsing.enabled": True,
    }
    try:
        options.add_experimental_option("prefs", prefs)
    except Exception:
        pass
    # excludeSwitches 및 useAutomationExtension 등은 undetected_chromedriver에서 기본 지원하므로 생략.
    return options


def get_editable_text(driver, editor) -> str:
    try:
        return driver.execute_script(
            """
            const el = arguments[0];
            return (el.innerText || el.textContent || '').trim();
            """,
            editor,
        ) or ""
    except Exception:
        return ""


def clear_editable(driver, editor) -> None:
    try:
        driver.execute_script(
            """
            arguments[0].focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('delete', false, null);
            """,
            editor,
        )
        return
    except Exception:
        pass

    try:
        ActionChains(driver).key_down(Keys.CONTROL).send_keys("a").key_up(
            Keys.CONTROL
        ).send_keys(Keys.BACKSPACE).perform()
    except Exception:
        pass


def verify_text_prefix(
    driver,
    editor,
    expected_text: str,
    timeout: float = 5,
    prefix_len: int = 24,
    log: LogFunc = None,
) -> bool:
    expected = normalize_text(expected_text)
    if not expected:
        return True

    prefix = expected[: min(prefix_len, len(expected))]
    end_at = time.time() + timeout
    while time.time() < end_at:
        actual = normalize_text(get_editable_text(driver, editor))
        if actual.startswith(prefix) or prefix in actual[: max(80, len(prefix) + 10)]:
            return True
        time.sleep(0.25)

    actual = normalize_text(get_editable_text(driver, editor))
    _log(log, f"본문 검증 실패: 기대 시작='{prefix[:20]}', 실제 시작='{actual[:20]}'")
    return False


def _element_ready_rect(driver, element, min_width: int, min_height: int):
    return driver.execute_script(
        """
        const el = arguments[0];
        const minWidth = arguments[1];
        const minHeight = arguments[2];
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        const disabled = el.disabled
            || el.getAttribute('aria-disabled') === 'true'
            || el.getAttribute('contenteditable') === 'false';
        const visible = style.display !== 'none'
            && style.visibility !== 'hidden'
            && style.opacity !== '0'
            && rect.width >= minWidth
            && rect.height >= minHeight
            && rect.bottom > 0
            && rect.right > 0;
        return {
            ok: visible && !disabled,
            rect: [
                Math.round(rect.left),
                Math.round(rect.top),
                Math.round(rect.width),
                Math.round(rect.height)
            ]
        };
        """,
        element,
        min_width,
        min_height,
    ) or {}


def wait_contenteditable_ready(
    driver,
    selectors: Optional[Sequence[str]] = None,
    timeout: float = 25,
    min_width: int = 120,
    min_height: int = 40,
    stable_polls: int = 2,
    frame_selectors: str = "iframe[class*='editor'],iframe[title*='editor'],iframe,frame",
    log: LogFunc = None,
    label: str = "editor",
):
    selectors = selectors or (
        "div[contenteditable='true']",
        "div.contentEditor",
        "div._richEditor",
        "div.uEditorArea",
        "[contenteditable='true']",
    )
    end_at = time.time() + timeout
    last_rect = None
    stable_hits = 0
    last_error = None

    while time.time() < end_at:
        try:
            driver.switch_to.default_content()
        except Exception as exc:
            last_error = exc

        contexts = [None]
        try:
            contexts.extend(driver.find_elements(By.CSS_SELECTOR, frame_selectors))
        except Exception:
            pass

        for frame in contexts:
            try:
                driver.switch_to.default_content()
                if frame is not None:
                    driver.switch_to.frame(frame)
            except Exception as exc:
                last_error = exc
                continue

            for selector in selectors:
                try:
                    candidates = driver.find_elements(By.CSS_SELECTOR, selector)
                except Exception as exc:
                    last_error = exc
                    continue

                for editor in candidates:
                    try:
                        ready = _element_ready_rect(
                            driver, editor, min_width=min_width, min_height=min_height
                        )
                        if not ready.get("ok"):
                            continue

                        rect = tuple(ready.get("rect") or [])
                        if rect == last_rect:
                            stable_hits += 1
                        else:
                            stable_hits = 0
                            last_rect = rect

                        try:
                            ActionChains(driver).move_to_element(editor).click().perform()
                        except Exception:
                            driver.execute_script("arguments[0].focus();", editor)

                        focused = driver.execute_script(
                            """
                            const el = arguments[0];
                            const active = document.activeElement;
                            return active === el || el.contains(active);
                            """,
                            editor,
                        )
                        if focused and stable_hits >= stable_polls:
                            _log(log, f"{label} ready")
                            time.sleep(0.15)
                            return editor
                    except Exception as exc:
                        last_error = exc
                        continue

        time.sleep(0.25)

    try:
        driver.switch_to.default_content()
    except Exception:
        pass

    if last_error:
        raise BrowserSensorError(
            f"{label} ready wait failed: {str(last_error)[:120]}"
        )
    raise BrowserSensorError(f"{label} ready wait failed: editable area not found")


def find_visible_element(
    driver,
    selectors: Iterable[Selector],
    timeout: float = 10,
    min_width: int = 1,
    min_height: int = 1,
):
    end_at = time.time() + timeout
    last_error = None

    while time.time() < end_at:
        for by, selector in selectors:
            try:
                for element in driver.find_elements(by, selector):
                    ready = _element_ready_rect(
                        driver, element, min_width=min_width, min_height=min_height
                    )
                    if ready.get("ok"):
                        return element
            except Exception as exc:
                last_error = exc
        time.sleep(0.2)

    if last_error:
        raise BrowserSensorError(
            f"visible element wait failed: {str(last_error)[:120]}"
        )
    raise BrowserSensorError("visible element wait failed: no matching element")
