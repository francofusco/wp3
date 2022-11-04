import logging
import pathlib
import sys

logger = logging.getLogger(__name__)


def fix_pyinstaller_path(relative_path):
    """Return the path to a file bundled in the PyInstaller executable.

    This function allows to retrieve files that have been added to the
    PyInstaller executable using the --add-data option. These files are copied
    at runtime in a temporary folder, whose path is stored in sys._MEIPASS. To
    allow running the code both from source and from the PyInstaller-generated
    executable, this function checks if sys._MEIPASS exists. If so, it will
    append the given relative path and return the result. Otherwise, it will
    append the relative path to the current working directory, `"."`.

    Args:
        relative_path: path to a file that should be found in the current
            directory when the code is run from source, or that has been added
            to the PyInstaller-generated executable via the --add-data option.
    Returns:
        Complete path to the resource.
    """
    logger.debug(f"Resolving relative path '{relative_path}'.")
    try:
        base_path = sys._MEIPASS
        logger.debug(f"sys._MEIPASS found: running as PyInstaller exe.")
    except Exception:
        base_path = "."
        logger.debug(f"sys._MEIPASS not found: running as regular script.")
    resolved_path = pathlib.Path(base_path).joinpath(relative_path)
    logger.debug(f"'{resolved_path}' resolved to '{resolved_path}'.")
    return resolved_path
