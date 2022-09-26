from collections import UserDict
from copy import deepcopy
import pathlib
from PyQt5.QtWidgets import QApplication, QFileDialog
import sys
import yaml


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

    # Make sure that panel sizes (in the matierial/panels section) are parsed
    # as arrays of floats. By default, they are read as arrays of strings. This
    # also allows to use inf as a value for panels whose cost is dependent on
    # the size.
    for k in settings["materials"]["sheets"]:
        settings["materials"]["sheets"][k]["size"] = list(map(float, settings["materials"]["sheets"][k]["size"]))

    # Return the processed settings.
    return SettingsDict(settings)


def retrieve_settings_file():
    """Get the name of the YAML configuration file.

    The function is used to retrieve the name of the YAML configuration file
    containing the settings for the designer. The function checks if the default
    name `config.yaml` corresponds to a file in the current directory. If so,
    it returns it. Otherwise, it asks the user to select one using a file
    chooser. If the user aborts the operation, then the program quuits.

    Returns:
        Name of the YAML file that should be opened to retrieve settings.
    """
    # Check of the default file exists. If so, hust return it.
    default_filename = "config.yaml"
    if pathlib.Path(default_filename).is_file():
        return default_filename

    # Ask the user to select a file using a graphical file chooser.
    app = QApplication([])
    file_name, _ = QFileDialog.getOpenFileName(None, "Open Config File", ".",
                                            "YAML (*.yaml *.yml)")
    # If no selection was made, quit.
    if file_name == "":
        sys.exit()

    # Return the chosen file.
    return file_name


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

    def __init__(self, *args, **kwargs):
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
        self.read_only = True

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
            value = SettingsDict(value)
            value.ns = key if self.ns is None else f"{self.ns}/{key}"

        # Return the retrieved value.
        return value

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
