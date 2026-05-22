import os
import sys
import time
try:
    import fcntl
    _HAS_FCNTL = True
except Exception:
    _HAS_FCNTL = False

uc = None
from config.settings import settings
from core.logger import logger
from core.proxy_manager import proxy_manager

# When the pipeline is launched by the Task Scheduler (no real console/TTY),
# Chrome needs extra flags to behave identically to an interactive launch.
# scheduler.py sets SCHEDULER_LAUNCHED=1 in the subprocess environment so
# BrowserService can detect this case and apply the correct flags.
_LAUNCHED_BY_SCHEDULER = os.environ.get("SCHEDULER_LAUNCHED", "0") == "1"


def _get_chrome_version():
    """Retrieves the installed Chrome version on Windows or Linux."""
    if sys.platform == "win32":
        import winreg
        # Locations to check for Chrome version in registry
        paths = [
            (winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon", "version"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Google Chrome", "DisplayVersion"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Google Chrome", "DisplayVersion"),
        ]
        for root, path, value_name in paths:
            try:
                key = winreg.OpenKey(root, path)
                version, _ = winreg.QueryValueEx(key, value_name)
                major_version = int(version.split('.')[0])
                logger.info(f"Detected Chrome version: {major_version} (from {path})")
                return major_version
            except Exception:
                continue
    
    # Fallback/Linux: Try to get version from command line
    try:
        import subprocess
        output = subprocess.check_output(["google-chrome", "--version"], stderr=subprocess.STDOUT).decode()
        # "Google Chrome 114.0.5735.90"
        major_version = int(output.split()[2].split('.')[0])
        return major_version
    except Exception:
        pass

    # Default fallback
    logger.warning("Could not detect Chrome version dynamically; using default 146.")
    return 146


class BrowserService:
    def __init__(self):
        self.driver = None
        self.lock_file = None

    def _acquire_lock(self):
        """Ensures only one instance touches the profile. fcntl not available on Windows."""
        profile_path = settings.chrome_profile_path
        os.makedirs(profile_path, exist_ok=True)
        lock_path = os.path.join(profile_path, "profile.lock")

        self.lock_file = None
        if not _HAS_FCNTL:
            logger.info("fcntl not available on this platform; skipping profile locking.")
            return

        self.lock_file = open(lock_path, 'w')
        try:
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            logger.info(f"Acquired lock on profile: {profile_path}")
        except IOError:
            logger.critical(f"Could not acquire lock on {lock_path}. Is another instance running?")
            raise RuntimeError("Browser profile is locked by another process.")

    def _release_lock(self):
        if not _HAS_FCNTL:
            return
        if self.lock_file:
            try:
                fcntl.flock(self.lock_file, fcntl.LOCK_UN)
            except Exception:
                pass
            self.lock_file.close()
            logger.info("Released profile lock.")

    def _apply_scheduler_flags(self, options) -> None:
        """
        Apply Chrome flags that make scheduler-launched Chrome behave like
        an interactive browser session.

        ROOT CAUSE OF THE BLOCKING ISSUE
        ─────────────────────────────────
        Windows Task Scheduler runs processes with no console window (no TTY).
        Even with CREATE_NEW_CONSOLE in Popen, Chrome internally checks several
        signals to decide whether it is in an "automated" context:

          1. Whether a real desktop session owns the process (Session 1 vs 0)
          2. Whether certain Chrome internals flags are present that signal
             automation (e.g. --enable-automation, which undetected-chromedriver
             removes, but other flags can re-introduce the signal)
          3. Navigator.webdriver — uc already patches this
          4. The absence of normal user-profile state / extensions that a
             real browser accumulates

        The flags below address these signals:
          --disable-blink-features=AutomationControlled
              Removes the most obvious automation fingerprint from Blink.
          --disable-infobars
              Suppresses the "Chrome is being controlled by automated software"
              banner — its presence in the DOM is detectable.
          --no-first-run / --no-service-autorun / --password-store=basic
              Prevent first-run dialogs and background services that behave
              differently in a headless context.
          --window-size / --start-maximized
              A zero-size or minimized window is an automation fingerprint.
              Sites can read window.outerWidth; a maximized window matches
              normal user behaviour.
          --disable-dev-shm-usage / --disable-gpu
              Required on Linux (no /dev/shm in Docker/Task environments).
          --lang=en-US / --accept-lang=en-US
              Ensures Accept-Language header matches a real user locale.
        """
        flags = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-first-run",
            "--no-service-autorun",
            "--password-store=basic",
            "--lang=en-US",
            "--accept-lang=en-US",
        ]

        if sys.platform != "win32":
            # Linux (including WSL / CI) — Chrome needs these in non-desktop sessions
            flags += [
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-sandbox",
            ]

        for f in flags:
            options.add_argument(f)

        # Window size: maximized look even if the desktop session has no monitor
        if settings.HEADLESS:
            options.add_argument("--window-size=1920,1080")
        else:
            options.add_argument("--start-maximized")

        if _LAUNCHED_BY_SCHEDULER:
            logger.info("Scheduler-mode: applied anti-detection Chrome flags.")

    @staticmethod
    def _force_kill_chrome():
        """Kill all running Chrome and ChromeDriver processes to clear stale sessions."""
        import subprocess
        for proc in ("chrome.exe", "chromedriver.exe"):
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", proc],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
        time.sleep(2)  # Give OS time to release file handles on the profile

    def _get_safe_chromedriver_dir(self) -> str:
        """Determines a writeable and executable-safe directory to bypass AppLocker."""
        # 1. Use setting override if configured
        if settings.CHROMEDRIVER_PATH:
            return os.path.abspath(settings.CHROMEDRIVER_PATH)

        # 2. Use 'bin' directory in project root (safe from both AppLocker and venv write-restrictions)
        from pathlib import Path
        project_root = Path(__file__).resolve().parent.parent
        bin_dir = os.path.join(project_root, "bin")
        os.makedirs(bin_dir, exist_ok=True)
        logger.info(f"Using project bin directory for ChromeDriver: {bin_dir}")
        return bin_dir

    def _create_options(self, is_uc: bool):
        """Creates a fresh ChromeOptions instance to prevent options reuse issues."""
        if is_uc:
            options = uc.ChromeOptions()
        else:
            from selenium.webdriver import ChromeOptions
            options = ChromeOptions()

        options.add_argument(f"--user-data-dir={settings.chrome_profile_path}")

        proxy_arg = proxy_manager.get_proxy_option()
        if proxy_arg:
            options.add_argument(proxy_arg)

        if settings.HEADLESS:
            options.add_argument("--headless=new")

        self._apply_scheduler_flags(options)
        return options

    def start_browser(self):
        self._acquire_lock()

        try:
            import undetected_chromedriver as uc_local
            global uc
            uc = uc_local

            # Monkey-patch uc.Patcher.patch_exe to handle Windows real-time scanning / AV file locks
            if sys.platform == "win32":
                original_patch_exe = uc.Patcher.patch_exe
                def retry_patch_exe(self_patcher):
                    for i in range(15):
                        try:
                            return original_patch_exe(self_patcher)
                        except PermissionError:
                            if i == 14:
                                raise
                            time.sleep(0.5)
                uc.Patcher.patch_exe = retry_patch_exe
        except ModuleNotFoundError as e:
            logger.warning(f"undetected_chromedriver import failed: {e}. Falling back to selenium webdriver.")
            uc = None

        if uc:
            chrome_version = _get_chrome_version()
            # Set the patcher's data path to a safe, whitelisted location (AppLocker evasion)
            safe_dir = self._get_safe_chromedriver_dir()
            uc.Patcher.data_path = safe_dir

            # Attempt 1 — normal launch
            try:
                options = self._create_options(is_uc=True)
                self.driver = uc.Chrome(
                    options=options,
                    use_subprocess=True,
                    version_main=chrome_version,
                )
                logger.info(f"Browser started successfully (undetected-chromedriver v{chrome_version}).")
            except Exception as e:
                logger.warning(
                    f"uc.Chrome attempt 1 failed (v{chrome_version}): {e}\n"
                    "Force-killing stale Chrome processes and retrying..."
                )
                self._force_kill_chrome()
                # Attempt 2 — retry with a fresh options object after killing stale processes
                try:
                    options = self._create_options(is_uc=True)
                    self.driver = uc.Chrome(
                        options=options,
                        use_subprocess=True,
                        version_main=chrome_version,
                    )
                    logger.info(f"Browser started on retry (undetected-chromedriver v{chrome_version}).")
                except Exception as e2:
                    logger.error(
                        f"uc.Chrome attempt 2 also failed (v{chrome_version}): {e2}\n"
                        "Falling back to webdriver-manager."
                    )

        # Fallback — webdriver-manager
        if not self.driver:
            try:
                from selenium import webdriver
                from selenium.webdriver.chrome.service import Service as ChromeService
                from webdriver_manager.chrome import ChromeDriverManager
                from webdriver_manager.core.driver_cache import DriverCacheManager

                safe_dir = self._get_safe_chromedriver_dir()
                cache_manager = DriverCacheManager(root_dir=safe_dir)
                service = ChromeService(ChromeDriverManager(cache_manager=cache_manager).install())
                options = self._create_options(is_uc=False)
                self.driver = webdriver.Chrome(service=service, options=options)
                logger.info("Browser started successfully (webdriver-manager fallback).")
            except Exception as e3:
                logger.error(f"Failed to start browser with fallback: {e3}")
                self._release_lock()
                raise

        # Fail-fast guard — never proceed with a None driver
        if not self.driver:
            self._release_lock()
            raise RuntimeError(
                "BrowserService.start_browser() failed: driver is None after all attempts. "
                "Check Chrome installation and profile lock files."
            )

        if not settings.HEADLESS:
            try:
                self.driver.maximize_window()
            except Exception as e:
                logger.warning(f"Could not maximize window: {e}")

        return self.driver

    def stop_browser(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.warning(f"Error closing driver: {e}")
            finally:
                self.driver = None

        self._release_lock()


browser_service = BrowserService()
