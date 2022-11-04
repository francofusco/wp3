from selenium import webdriver
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager
import logging
import pathlib
import time

logger = logging.getLogger(__name__)


def open_browser(download_dir):
    """Open a (Chrome) browser with a custom download location.

    Args:
        download_dir: pathlib.Path object pointing to an existing directory.
    Returns:
        A WebDriver object representing a Chrome browser.
    """
    # Currently, only Chrome is supported. I will try to make it less
    # browser-dependent...
    logger.debug(
        f"Creating Chrome browser with download location set to {download_dir}."
    )
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_experimental_option(
        "prefs", {"download.default_directory": str(download_dir)}
    )
    return webdriver.Chrome(
        ChromeDriverManager().install(), options=chrome_options
    )


def wait_for_download(dir, timeout, num_files):
    """Wait for a download to finish with a specified timeout.

    Args:
        dir: Path to the folder where a file is being downloaded.
        timeout: Seconds to wait until timing out.
        num_files: Expected number of files (after download).
    Returns:
        True if a download has been completed, False otherwise.
    """
    for _ in range(timeout):
        # Check if the number of files is the expected one and if no file ends
        # with the ".crdownload" extension. If this is the case, the download
        # has been completed!
        files = list(dir.glob("*"))
        if len(files) == num_files and not any(
            str(f).endswith(".crdownload") for f in files
        ):
            return True

        # The download was not completed: wait one second.
        time.sleep(1)

    # The file was not downloaded within the alloted time.
    return False


def download_pico_firmware(
    destination, firmware_name, leds_channel_1, leds_channel_2
):
    """Configure and download the Pico firmware from SRGBmods.

    Args:
        destination: pathlib.Path object representing the directory where the
            firmware will be stored.
        firmware_name: name to be given to the downloaded firmware.
        leds_channel_1: list of integers, telling how many LEDs per pin should
            be allocated in the first channel.
        leds_channel_2: like above, but for the second channel.
    """
    # Make sure that there are some LEDs to allocate.
    if sum(leds_channel_1) == 0 and sum(leds_channel_2) == 0:
        raise RuntimeError("There are no LEDs to assign to any channel.")

    # The Pico firmware features a maximum of 26 pins, and 512 LEDs per channel.
    if len(leds_channel_1) + len(leds_channel_2) > 26:
        raise RuntimeError(
            "The Pico firmware supports a maximum of 26 channels. However,"
            f" channel 1 requires {len(leds_channel_1)} pins, and channel 2"
            f" requires {len(leds_channel_2)}, for a total of"
            f" {len(leds_channel_1)+len(leds_channel_2)} pins."
        )
    for i, ch in enumerate([leds_channel_1, leds_channel_2]):
        if sum(ch) > 512:
            raise RuntimeError(
                "The Pico firmware allows to control 512 LEDs per channel."
                f" However, channel {i+1} features {sum(ch)} LEDs."
            )

    # Open a browser.
    browser = open_browser(destination)

    # Go to Pico's SRGBmods page.
    browser.get("https://srgbmods.net/picoled/")

    # For each strip in channel 1, assign LEDs to pins.
    for pin, num_leds in enumerate(leds_channel_1):
        # Pins 23, 24 and 25 are not available: skip them!
        if pin > 22:
            pin += 3

        # Select which channel the pin is assigned to.
        Select(browser.find_element_by_id(f"CH_PIN{pin}")).select_by_value("1")

        # Select the number of LEDs used by the current pin.
        leds = browser.find_element_by_id(f"LEDS_PIN{pin}")
        leds.clear()
        leds.send_keys(str(num_leds))

    # For each strip in channel 2, assign LEDs to pins.
    for pin, num_leds in enumerate(leds_channel_2):
        # Keep going from the pins used by the first channel.
        pin += len(leds_channel_1)

        # Pins 23, 24 and 25 are not available: skip them!
        if pin > 22:
            pin += 3

        # Select the number of LEDs used by the current pin.
        Select(browser.find_element_by_id(f"CH_PIN{pin}")).select_by_value("2")

        # Select the number of LEDs used by the current pin.
        leds = browser.find_element_by_id(f"LEDS_PIN{pin}")
        leds.clear()
        leds.send_keys(str(num_leds))

    # Store the files in the target directory before downloading the script.
    files_pre_download = list(destination.glob("*"))

    # Download the Pico firmware. If the download is successful, rename it as
    # well.
    browser.find_element_by_id("srgbmodsplcform").submit()
    if wait_for_download(destination, 5, len(files_pre_download) + 1):
        # Look for the name of the firmware. It should be the only file in the
        # destination directory that was not there before the download.
        for file in destination.glob("*"):
            if file not in files_pre_download:
                # Firmare found: rename it!
                new_firmware_name = destination.joinpath(firmware_name)
                if new_firmware_name.exists():
                    logger.debug(
                        f"Firmare name '{new_firmware_name}' exists already."
                        " Removing it."
                    )
                    new_firmware_name.unlink()
                file.rename(new_firmware_name)
                logger.info(
                    f"Firmware found: '{file}'. Renamed to"
                    f" '{new_firmware_name}'."
                )
    #
    # # Close the browser.
    # browser.close()
