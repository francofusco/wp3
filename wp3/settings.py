from collections import UserDict
from copy import deepcopy
import logging
import pathlib
from PyQt5.QtWidgets import QApplication, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget
import sys
import urllib.request
import ruamel.yaml

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


def open_project():
    # Create a QApplication to run all GUIs.
    app = QApplication([])

    # If the directory "projects" is available, we want projects to be stored
    # there. Otherwise, just use the current location as base path.
    projects_dir = pathlib.Path("projects")
    if not projects_dir.is_dir():
        logger.debug("Directory 'projects' not found: setting projects root as "
                     "current directory.")
        projects_dir = pathlib.Path(".")

    # Create a message box that asks the user to create or load a project.
    new_or_load_message_box = QMessageBox()
    new_or_load_message_box.setWindowTitle("WP3 Designer")
    new_or_load_message_box.setText("Do you want to create a new project or load an existing one?")
    new_or_load_message_box.setIcon(QMessageBox.Question)
    new_btn = new_or_load_message_box.addButton("New", QMessageBox.YesRole)
    load_btn = new_or_load_message_box.addButton("Load", QMessageBox.NoRole)
    new_or_load_message_box.addButton("Cancel", QMessageBox.RejectRole)

    # Wait for user's response, then take an action.
    logger.debug("Waiting for user to interact with message box.")
    new_or_load_message_box.exec()
    logger.debug(f"User clicked on '{new_or_load_message_box.clickedButton()}'.")
    if new_or_load_message_box.clickedButton() == new_btn:
        logger.debug("Creating new project.")

        # When creating a new project, pre-fill the settings using the values
        # stored in the default configuration file.
        settings = SettingsDict.parser.load(fix_pyinstaller_path("config.yaml"))

        # Create a dialog window that allows the user to change the default
        # project settings.
        new_project_dialog = QDialog()
        main_layout = QVBoxLayout()
        new_project_dialog.setLayout(main_layout)
        new_project_dialog.setWindowTitle("Project settings")

        # Create a form to enter the desired settings.
        form = QFormLayout()
        project_name = QLineEdit()
        form.addRow("Project name", project_name)
        tile_type = QLineEdit(settings["panels"]["type"])
        form.addRow("Tile type", tile_type)
        side_length = QLineEdit(str(settings["panels"]["side_length"]))
        form.addRow("Tiles side length", side_length)
        spacing = QLineEdit(str(settings["panels"]["spacing"]))
        form.addRow("Tiles spacing", spacing)
        rows = QLineEdit(str(settings["panels"]["rows"]))
        form.addRow("Canvas rows", rows)
        columns = QLineEdit(str(settings["panels"]["columns"]))
        form.addRow("Canvas columns", columns)

        # Buttons to confirm or cancel project creation.
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        # Auxiliary function that validates the project name. A project name is
        # valid if it points to a non-existing directory or to one that exists
        # but is empty. If an invalid value is given, the function opens a
        # message box and then returns. If the value is valid, it calls the
        # accept() method on the dialog parameter.
        def accept_if_directory_is_empty(project_name, dialog):
            if project_name == "":
                QMessageBox.critical(None, "Error", "Empty project name")
                return
            dir = projects_dir.joinpath(project_name)
            if dir.exists():
                if dir.is_file():
                    QMessageBox.critical(None, "Error", "Project name exists as a file")
                    return
                elif any(dir.iterdir()):
                    QMessageBox.critical(None, "Error", "Project directory is not empty")
                    return
            dialog.accept()

        # Connect signals and slots to validate or cancel project creation.
        buttonBox.accepted.connect(lambda: accept_if_directory_is_empty(project_name.text(), new_project_dialog))
        buttonBox.rejected.connect(new_project_dialog.reject)

        # Add the form and the buttons to the main layout of the dialog.
        main_layout.addLayout(form)
        main_layout.addWidget(buttonBox)

        logger.debug("Created form dialog to create new project from given "
                     "settings. Waiting for user interaction.")

        # If the user clicks on "Cancel", quit.
        if not new_project_dialog.exec():
            logger.debug("The user did not validate the form. Quitting.")
            sys.exit()

        # Create the directory that will contain the project.
        project_dir = projects_dir.joinpath(project_name.text())
        project_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Creating new project in '{project_dir}'.")

        # Change the default settings by using those provided in the form.
        settings["panels"]["type"] = tile_type.text()
        settings["panels"]["side_length"] = float(side_length.text())
        settings["panels"]["spacing"] = float(spacing.text())
        settings["panels"]["rows"] = int(rows.text())
        settings["panels"]["columns"] = int(columns.text())

        # Convert the dictionary into a SettingsDict
        settings = SettingsDict(settings)

        # Save the new settings to re-load the project in the future.
        logger.debug("Creating the file 'config.yaml' for the project.")
        settings.save_to_yaml(project_dir.joinpath("config.yaml"))

        # Return project location and settings.
        return project_dir, settings
    elif new_or_load_message_box.clickedButton() == load_btn:
        logger.debug("Loading project.")

        # Load an existing project.
        file_name, _ = QFileDialog.getOpenFileName(None, "Open project",
                                                   str(projects_dir),
                                                   "YAML (*.yaml *.yml)")
        logger.debug(f"User selected file '{file_name}'.")

        # If no selection was made, quit.
        if file_name == "":
            logger.debug("File name is empty: quitting.")
            sys.exit()

        # Return project location and settings.
        project_dir = pathlib.Path(file_name).parent
        logger.debug(f"Project directory: '{project_dir}'.")
        return project_dir, SettingsDict.from_yaml(file_name)
    else:
        logger.debug("The user did not click on neither 'New' nor 'Load'. "
                     "Quitting.")
        # The user clicked on "Cancel" or closed the window: quit.
        sys.exit()


def update_initial_tiling(project_dir, settings, initial_tiling):
    logger.debug("Saving tiling into 'config.yaml'.")
    store_seq(project_dir, settings, initial_tiling, ["panels", "initial_tiling"])


def update_cached_routing(project_dir, settings, routing):
    logger.debug("Saving routing into 'config.yaml'.")
    store_seq(project_dir, settings, routing, ["routing", "cache"])


def store_seq(project_dir, settings, sequence, namespace):
    """Store the given sequence in a compact way in the `config.yaml` file.

    Args:
        project_dir: a Pathlib instance pointing to the project directory.
        settings: a SettingsDict instance that will be updated by adding the
            given sequence.
        sequence: list (or possibly nested list of lists).
        namespace: a list of keys that tells where the parameter is to be stored
            in the YAML configuration file.
    """
    # Convert the given sequence to a format used in ruamel and make sure that
    # it is stored in a compact form.
    item_seq = SettingsDict.parser.seq(sequence)
    item_seq.fa.set_flow_style()
    logger.debug("Converted input sequence into ruamel-friendly format.")
    # Add the sequence to the SettingsDict in the proper place.
    item = settings.data
    for key in namespace[:-1]:
        logger.debug(f"Accessing namespace '{key}'.")
        item = item[key]
    logger.debug(f"Storing sequence into '{namespace[-1]}'.")
    item[namespace[-1]] = item_seq
    # Overwrite current settings.
    logger.debug(f"Overwriting 'config.yaml'.")
    settings.save_to_yaml(project_dir.joinpath("config.yaml"))


def load_materials(settings):
    """Create a list of materials from different sources.

    The list of materials is populated as follows:
    - Try to download the file `materials.yaml` from the online repository;
    - Add materials from a local `materials.yaml` list;
    - Include materials from local project settings.

    Args:
        settings: a SettingsDict instance. Materials are pulled from the
            namespaces `"materials/leds"` and `"materials/sheets"`.
    Returns:
        A SettingsDict with the list of materials.
    """
    # Try to initialize the list of materials from an online file.
    try:
        materials_url = "https://raw.githubusercontent.com/francofusco/wp3/main/materials.yaml"
        logger.debug(f"Sending HTTP request to retrieve '{materials_url}'.")
        hosted_materials_file, _ = urllib.request.urlretrieve(materials_url)
        with open(hosted_materials_file, "r") as f:
            materials = SettingsDict.parser.load(f)
        logger.info(f"Loaded list of materials from '{materials_url}'.")
    except (urllib.error.URLError, urllib.error.HTTPError):
        logger.debug(f"HTTP request failed.")
        materials = {}

    # Make sure that the materials dictionary contains the sub-dictionary
    # "leds".
    if "leds" not in materials:
        logger.debug("Adding namespace 'leds' to list of materials.")
        materials["leds"] = {}

    # Make sure that the materials dictionary contains the sub-dictionary
    # "sheets".
    if "sheets" not in materials:
        logger.debug("Adding namespace 'sheets' to list of materials.")
        materials["sheets"] = {}

    # Try to read materials from a local file.
    local_materials_file = pathlib.Path("materials.yaml")
    if local_materials_file.is_file():
        logger.info("Updating list of materials from 'materials.yaml'.")
        # Read the local list of materials.
        with open(local_materials_file, "r") as f:
            local_materials = SettingsDict.parser.load(f)

        # Expand or replace materials using the content of the local file.
        if "leds" in local_materials:
            for k, v in local_materials["leds"].items():
                logger.debug(f"Updating entry for '{k}' (leds).")
                materials["leds"][k] = v
        if "sheets" in local_materials:
            for k, v in local_materials["sheets"].items():
                logger.debug(f"Updating entry for '{k}' (sheets).")
                materials["sheets"][k] = v

    # Expand or replace materials using the content of project settings.
    logger.info("Updating list of materials from 'config.yaml'.")
    if settings.has("materials", "leds"):
        for k, v in settings["materials"].extract("leds").items():
            logger.debug(f"Updating entry for '{k}' (leds).")
            materials["leds"][k] = v

    if settings.has("materials", "sheets"):
        for k, v in settings["materials"].extract("sheets").items():
            logger.debug(f"Updating entry for '{k}' (sheets).")
            materials["sheets"][k] = v

    for k in materials["sheets"]:
        # Make sure that panel sizes are parsed as arrays of floats. By default,
        # they are read as arrays of strings. This also allows to use inf as a
        # value for panels whose cost is dependent on the size.
        logger.debug(f"Casting 'size' to floats for material '{k}'.")
        materials["sheets"][k]["size"] = list(map(float, materials["sheets"][k]["size"]))

        # Make sure that the cost of the sheet is positive, or at least
        # non-negative.
        cost = materials["sheets"][k].get("cost")
        if cost is None:
            logger.warning(f"No cost specified for sheet '{k}'.")
        elif cost == 0:
            logger.warning(f"Cost of sheet '{k}' is null.")
        elif cost < 0:
            raise RuntimeError(f"Cost of sheet '{k}' is negative.")

    for k in materials["leds"]:
        # Make sure that the cost of the LED strip is positive, or at least
        # non-negative.
        cost = materials["leds"][k].get("cost")
        if cost is None:
            logger.warning(f"No cost specified for leds '{k}'.")
        elif cost == 0:
            logger.warning(f"Cost of leds '{k}' is null.")
        elif cost < 0:
            raise RuntimeError(f"Cost of leds '{k}' is negative.")

    # Return the list of materials, as a SettingsDict instance.
    logger.debug(f"List of materials loaded. There are "
                  f"{len(materials['sheets'])} sheets and "
                  f"{len(materials['leds'])} leds.")
    return SettingsDict(materials)


class SettingsDict(UserDict):
    """Special dictionary to access the settings in the YAML configuration file.

    This class emulates a dictionary with few "superpowers" justified by the
    fact that the dictionary should be populated by reading YAML files.

    In particular, the features of this class are:
    - The dictionary is read-only, by default. The goal should be to access
      data and not to set it. There is nothing to stop one to change the magic
      varable "read_only" from True to False to allow changes. Just remember
      uncle Ben's teachings.
    - When accessing elements, if the key exists and the value is a dictionary,
      the returned value is converted to a SettingsDict object itself. This
      allows to keep trace of who was its "parent" key and provide a more
      informative error message when an item is missing. As an example, consider
      the instruction `settings["foo"]["bar"]["foo"]`, wherein `settings` is a
      SettingsDict. If the key `"foo"` is missing in `settings`, the dictionary
      informs the user that `"foo"` is missing from the namespace "/". However,
      if `"foo"` is missing from `settings["foo"]["bar"]`, the error message
      tells that the key is missing from the namespace "foo/bar", which is
      hopefully more informative and helps the user correct the issue faster.
    - By default, when a key is missing, the error message is printed on the
      console and the sys.exit() is called to halt execution. However, one can
      switch to exceptions at any time by changing the variable use_exceptions
      from False (the default) to True.
    """

    def __init__(self, *args, read_only=True, **kwargs):
        """Initialize the dictionary.

        Args:
            args: positional arguments that will be forwared to the constructor
                of the base class, UserDict.
            kwargs: keyword arguments that will be forwared to the constructor
                of the base class, UserDict.
        """
        # Initialize the namespace to be empty. If this dictionary has been
        # created in a call to __getitem__, the field will be updated to keep
        # track of nested namespaces.
        self.ns = None

        # This variable decides how to notify the user of missing keys in the
        # dictionary. If use_exceptions is False (default), when __getitem__ is
        # called with a missing key, an error message is print on the console
        # and the execution of the whole program is stopped by calling
        # sys.exit(). This is done because the primary goal of the SettingsDict
        # is to store the settings provided in the YAML configuration file, and
        # the program should halt when a mandatory information is missing.
        # Directly calling sys.exit() avoids repeating a bunch of try...except
        # blocks every time a mandatory key is to be accessed. Nonetheless, if
        # such behavior is preferable, one can set use_exceptions to True to
        # have a KeyError raised instead.
        self.use_exceptions = True

        # Initialize the dictionary by calling the constructor of the base
        # class. Upon initialization, the dictionary is set in writeable mode
        # (otherwise, __setitem__ would throw a RuntimeError). Afterwards, it
        # becomes read-only.
        self.read_only = False
        super().__init__(*args, **kwargs)
        self.read_only = read_only

    def __setitem__(self, key, value):
        """Set a value in the dictionary, if the instance is not read-only.

        If the dictionary is not in read-only mode, set a value inside it using
        the syntax object[key] = value. If the dictionary is in read-only mode,
        raise an RuntimeError instead. This method overrides the base method in
        UserDict.
        """
        if self.read_only:
            raise RuntimeError(f"The settings dictionary is read-only, cannot set key '{key}'.")
        else:
            super().__setitem__(key, value)

    def _get_deepcopy(self, key):
        """Get a deep-copy of the value associated to the given key.

        This is equivalent to __getitem__(key) if the value associated to the
        key is not a dictionary. Otherwise, it returns a deepcopy of the
        dictionary and not a SettingsDict.
        """
        # When the key is missing, an error message is printed on the console
        # and the execution is stoppped via sys.exit(). If use_exceptions is
        # True, an KeyError with the same error message is raised instead.
        if key not in self:
            msg = f"The required key '{key}' could not be found in the namespace '{self.ns or '/'}'. Please, check your YAML configuration file."
            if self.use_exceptions:
                raise KeyError(msg)
            else:
                logger.debug(msg)
                print(msg)
                sys.exit()

        # Retrieve and return the value using the "normal" __getitem__.
        return deepcopy(super().__getitem__(key))

    def __getitem__(self, key):
        """Access a value or a nested dictionary.

        Retrieve a value from the dictionary using the syntax object[key].
        Overrides the base method in UserDict.
        """
        # Get a copy of the desired value, if possible.
        value = self._get_deepcopy(key)

        # If the obtained value is a dictionary, convert it to a SettingsDict
        # and extend its namespace.
        if isinstance(value, dict):
            value = SettingsDict(value, read_only=self.read_only)
            value.ns = key if self.ns is None else f"{self.ns}/{key}"

        # Return the retrieved value.
        return value

    def get(self, key, default=None):
        """Return the value for key if key is in the dictionary, else default.

        This is just like dict.get, but is reimplemented for technical reasons.

        Args:
            key: the key associated with the desired value.
            default: value to return if the key is not found.
        Returns:
            The value for key if key is in the dictionary, else default.
        """
        return self[key] if key in self else default


    def extract(self, key, default=None):
        """Get a deep-copy of the value associated to the given key.

        This is equivalent to get(key, default) if the value associated to the
        key is not a dictionary. Otherwise, it returns a deepcopy of the
        dictionary and not a SettingsDict.
        """
        return self._get_deepcopy(key) if key in self else default

    def has(self, key, *keys):
        """Checks if the given sequence of keys is present in the settings.

        Given as set of keys k1, k2, k3, etc., this method checks if the
        instructions object[k1], object[k1][k2], object[k1][k2][k3], etc., would
        all be valid.

        Args:
            key: the first key to be checked.
            keys: list of all other keys to be checked.
        """
        # If the current key is not in the dictionary, just return False.
        if not key in self:
            return False

        # If there are no other keys left to check, then all keys were valid.
        if len(keys) == 0:
            return True

        # Since there are other keys, get the value associated to the current
        # one. If this value is not a SettingsDict, then the other keys are not
        # in the SettingsDict. Otherwise, check it recursively!
        value = self[key]
        return isinstance(value, SettingsDict) and value.has(*keys)

    @staticmethod
    def yaml_parser():
        """Create a custom YAML parser."""
        p = ruamel.yaml.YAML()
        p.width = 1024
        return p

    parser = yaml_parser.__func__()

    @staticmethod
    def from_yaml(file_name):
        """Create a SettingsDict instance from a YAML file."""
        with open(file_name, "r") as f:
            return SettingsDict(SettingsDict.parser.load(f))

    def save_to_yaml(self, file_name):
        """Dump a SettingsDict to a YAML file."""
        with open(file_name, "w") as f:
            SettingsDict.parser.dump(self.data, f)
