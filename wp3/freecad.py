from .pyinstaller import fix_pyinstaller_path
import logging
import numpy as np
import sys

logger = logging.getLogger(__name__)


def load_freecad(path=None):
    """Try to load the FreeCAD python module.

    Args:
        path: path to a directory that contains the FreeCAD python module. If
            None is given, a default path is used.
    Returns:
        The FreeCAD module (if found) or None.
    """
    # The default path is currently valid only on windows. Inform users that
    # other setups will likely fail...
    if path is None and sys.platform != "win32":
        logger.warning(
            f"You are running under the platform '{sys.platform}', which has"
            " not been tested with FreeCAD. The default path points to a"
            " default Windows location, which means that the FreeCAD module"
            " will most likely not be found."
        )

    # Make sure that the search path is initialized with a default if the user
    # does not provide it explicitly.
    search_path = path or "C:/Program Files/FreeCAD 0.20/bin/"

    # Add the path to the environment if it is not there already.
    if search_path not in sys.path:
        logger.debug(
            f"Adding path '{search_path}' to PATH to look for FreeCAD."
        )
        sys.path.append(search_path)

    # Try importing the module. If something goes wrong, simply catch and ignore
    # the ImportError.
    FreeCAD = None
    try:
        import FreeCAD

        logger.debug("FreeCAD imported successfully.")
    except ImportError:
        logger.debug("FreeCAD could not be found.")

    # Return the module, or None if it was not found.
    return FreeCAD


def gradual_update(document, spreadsheet, cad_values, steps=10):
    """Update a set of parameters incrementally.

    This function tries to update several parameters gradually, from current
    values to target ones. This is performed in multiple steps to guarantee that
    the geometric solver do not break and find alternative solutions.

    Args:
        document: FreeCAD document to be updated.
        spreadsheet: the spreadsheet containing the parameters to be modified.
        cad_values: a dictionary whose keys are parameter names and the values
            corresponding to what the parameters should be set to.
        steps: number of iterations to be performed before reaching the target
            values.
    """
    # Create a dictionary in the form {parameter: (target value, initial value)}
    # to perform gradual updates.
    params_vals = {
        param: (target, spreadsheet.get(param))
        for param, target in cad_values.items()
    }

    # Gradually update all parameters.
    for rho in np.linspace(0, 1, steps + 1)[1:]:
        logger.debug(f"Updating CAD parameters, {rho=}.")
        for param, (target, start) in params_vals.items():
            spreadsheet.set(param, str(rho * target + (1 - rho) * start))
            logger.debug(f"- {param} set to {spreadsheet.get(param)}.")
        document.recompute()


def wp3_export_default(save_path, freecad_path=None, **cad_values):
    """Export STL files for the default designs (hexagon, square, triangle).

    Args:
        save_path: destination directory where STLs should be saved into.
        freecad_path: path to FreeCAD's binaries. This directory should contain
            the FreeCAD.pyd module.
        cad_values: CAD parameters that can be changed. They should correspond
            to aliases to values stored in the 'params' spreadsheet.
    Returns:
        True if the CAD files were exported, False otherwise.
    """
    # Try to load the FreeCAD module.
    FreeCAD = load_freecad(path=freecad_path)
    if FreeCAD is None:
        logger.debug(
            "Could not find the FreeCAD module, no STL will be exported."
        )
        return False

    # Open the CAD file containing all the parts to be exported.
    doc = FreeCAD.open(str(fix_pyinstaller_path("cad/wp3-walls-v2.FCStd")))

    # Get the parameters spreadsheet.
    (params,) = doc.getObjectsByLabel("params")

    # Change the CAD parameters according to what is specified by the user and
    # apply the changes to the components. This is done in multiple steps
    # because the solvers can have troubles when multiple solutions exist.
    # Doing a smooth transition from the old to the new values seems better.
    params.joint_num_walls = 2
    gradual_update(doc, params, cad_values)

    # Export the outer walls STL.
    outer_file_name = save_path.joinpath("wp3-wall-outer.stl")
    logger.debug(f"Exporting CAD to '{outer_file_name}'.")
    (wall_outer,) = doc.getObjectsByLabel("wall-outer")
    wall_outer.Shape.exportStl(str(outer_file_name))

    # Export the inner walls STL.
    inner_file_name = save_path.joinpath("wp3-wall-inner.stl")
    logger.debug(f"Exporting CAD to '{inner_file_name}'.")
    (wall_inner,) = doc.getObjectsByLabel("wall-inner")
    wall_inner.Shape.exportStl(str(inner_file_name))

    # Export joints for all wall combinations.
    for i in range(2, 1 + params.get("joint_max_walls")):
        # Update the CAD.
        params.joint_num_walls = i
        doc.recompute()

        # Export the joint STL.
        joint_file_name = save_path.joinpath(f"wp3-joint-{i}.stl")
        logger.debug(f"Exporting CAD to '{joint_file_name}'.")
        (joint,) = doc.getObjectsByLabel("joint")
        joint.Shape.exportStl(str(joint_file_name))

    return True
