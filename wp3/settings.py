from collections import UserDict
from copy import deepcopy
import os
import pathlib
from PyQt5.QtWidgets import QApplication, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget
import sys
import urllib.request
import yaml


def open_project():
    # Create a QApplication to run all GUIs.
    app = QApplication([])

    # Create a message box that asks the user to create or load a project.
    new_or_load_message_box = QMessageBox()
    new_or_load_message_box.setWindowTitle("WP3 Designer")
    new_or_load_message_box.setText("Do you want to create a new project or load an existing one?")
    new_or_load_message_box.setIcon(QMessageBox.Question)
    new_btn = new_or_load_message_box.addButton("New", QMessageBox.YesRole)
    load_btn = new_or_load_message_box.addButton("Load", QMessageBox.NoRole)
    new_or_load_message_box.addButton("Cancel", QMessageBox.RejectRole)

    # Wait for user's response, then take an action.
    new_or_load_message_box.exec()
    if new_or_load_message_box.clickedButton() == new_btn:
        # Retrieve the default configuration file. Note that PyInstaller creates
        # a temporary folder with the resources inside it, and stores its path
        # in _MEIPASS, which is why the following code is necessary.
        try:
            cfg_path = sys._MEIPASS
        except Exception:
            cfg_path = "."

        settings = load_settings(pathlib.Path(cfg_path).joinpath("config.yaml"))

        new_project_dialog = QDialog()
        main_layout = QVBoxLayout()
        new_project_dialog.setLayout(main_layout)
        new_project_dialog.setWindowTitle("Project settings")

        # Let the user create a new project.
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

        def accept_if_directory_is_empty(dir_name, dialog):
            if dir_name == "":
                QMessageBox.critical(None, "Error", "Empty project name")
                return
            dir = pathlib.Path("projects").joinpath(dir_name)
            if dir.exists():
                if dir.is_file():
                    QMessageBox.critical(None, "Error", "Project name exists as a file")
                    return
                elif any(dir.iterdir()):
                    QMessageBox.critical(None, "Error", "Project directory is not empty")
                    return
            dialog.accept()

        buttonBox.accepted.connect(lambda: accept_if_directory_is_empty(project_name.text(), new_project_dialog))
        buttonBox.rejected.connect(new_project_dialog.reject)

        main_layout.addLayout(form)
        main_layout.addWidget(buttonBox)

        if not new_project_dialog.exec():
            sys.exit()

        project_dir = pathlib.Path("projects").joinpath(project_name.text())
        project_dir.mkdir(parents=True, exist_ok=True)

        settings.read_only = False
        settings["panels"]["type"] = tile_type.text()
        settings["panels"]["side_length"] = float(side_length.text())
        settings["panels"]["spacing"] = float(spacing.text())
        settings["panels"]["rows"] = int(rows.text())
        settings["panels"]["columns"] = int(columns.text())
        settings.read_only = True

        with open(project_dir.joinpath("config.yaml"), "w") as f:
            yaml.dump(settings.data, f)

        return project_dir, settings
    elif new_or_load_message_box.clickedButton() == load_btn:
        # Load an existing project.
        file_name, _ = QFileDialog.getOpenFileName(None, "Open project",
                                                   ".", "YAML (*.yaml *.yml)")
        # If no selection was made, quit.
        if file_name == "":
            sys.exit()

        # Return project location and settings.
        return pathlib.Path(file_name).parent, load_settings(file_name)
    else:
        sys.exit()


def load_settings(filename):
    """Load configuration parameters from a YAML file.

    Args:
        filename: name of a YAML file containing configuration parameters.
    Returns:
        settings: a dictionary containing the parameters.
    """
    # Parse the content of the provided YAML file.
    with open(filename) as f:
        settings = yaml.load(f, Loader=yaml.loader.SafeLoader)


    if settings.get("materials", {}).get("sheets") is not None:
        for k in settings["materials"]["sheets"]:
            settings["materials"]["sheets"][k]["size"] = list(map(float, settings["materials"]["sheets"][k]["size"]))

    # Return the processed settings.
    return SettingsDict(settings)


def load_materials(settings):
    try:
        with urllib.request.urlopen("https://raw.githubusercontent.com/francofusco/wp3/main/materials.yaml") as f:
            materials = yaml.load(f, Loader=yaml.loader.SafeLoader)
    except urllib.error.HTTPError:
        with open("materials.yaml", "r") as f:
            materials = yaml.load(f, Loader=yaml.loader.SafeLoader)

    print(materials)

    if settings.has("materials", "leds"):
        for k, v in settings["materials"].extract("leds").items():
            materials["leds"][k] = v

    if settings.has("materials", "sheets"):
        for k, v in settings["materials"].extract("sheets").items():
            materials["sheets"][k] = v

    # Make sure that panel sizes are parsed as arrays of floats. By default,
    # they are read as arrays of strings. This also allows to use inf as a
    # value for panels whose cost is dependent on the size.
    for k in materials["sheets"]:
        materials["sheets"][k]["size"] = list(map(float, materials["sheets"][k]["size"]))

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
        self.use_exceptions = False

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
