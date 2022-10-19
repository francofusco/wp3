from .struct import Struct
from .tile import get_bounding_box
import logging
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


def tight_figure(tiles):
    """Create a figure that have just enough space to contain the given tiles.

    The returned figure/axes are configured so that:
    - The size of the axes corresponds to the bounding box of the list of tiles.
    - No horizontal/vertical ticks are shown.
    - The horizontal and vertical unit of length is the same.

    Args:
        tiles: a list of Tile instances that must fit within the figure.
    Returns:
        fig: a matplotlib.figure.Figure instance.
        ax: a matplotlib.axes.Axes instance.
    """
    fig, ax = plt.subplots()
    ax.set_aspect("equal")
    (xmin, ymin), (xmax, ymax) = get_bounding_box(tiles)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.tick_params(
        which="both",
        bottom=False,
        top=False,
        right=False,
        left=False,
        labelbottom=False,
        labelleft=False,
    )
    ax.set_axisbelow(True)
    fig.tight_layout()
    return fig, ax


def add_tiles_to_axes(
    tiles, ax, copy=False, patch_color=None, border_color=None
):
    """Add al tiles in the list to the given axes."""
    for tile in tiles:
        if copy:
            tile = tile.make_copy()
        tile.add_to_axis(ax)
        if patch_color is not None:
            tile.patch.set_facecolor(patch_color)
        if border_color is not None:
            tile.outer_patch.set_facecolor(border_color)


def toggle_tile_if_clicked(mouse_event, tile, axis):
    """Mouse callback to toggle visibility of a tile.

    This function is meant to be used as callback for matplotlib events, to
    allow showing/hiding a tile when clicked.

    Args:
        mouse_event: instance of matplotlib.backend_bases.MouseEvent. It should
            be generated by matplotlib itself when firing the event.
        tile: the Tile instance that should be shown/hidden.
        axis: the matplotlib.axes.Axes instance that contains the patches of
            this tile. It is needed to update the figure.
    """
    logger.debug(f"New mouse event for tile ({tile.row}, {tile.col}).")

    # Ignore events fired when the mouse is outside the drawing area.
    if mouse_event.xdata is None or mouse_event.ydata is None:
        logger.debug(
            "Event rejected due to empty coordinates: "
            f"{mouse_event.xdata=}, {mouse_event.ydata=}."
        )
        return

    # Toggle the tile if the mouse is inside it.
    if tile.contains(mouse_event.xdata, mouse_event.ydata):
        logger.debug(f"Tile ({tile.row}, {tile.col}) clicked.")
        tile.toggle_visible()
        axis.figure.canvas.draw()


def toggle_all_tiles(keyboard_event, tiles, axis):
    """Keyboard callback to toggle visibility of many tiles at once.

    This function is meant to be used as callback for matplotlib events, to
    allow showing/hiding a set of tiles when some keys are pressed.

    Controls:
    - Space bar: toggle each tile;
    - A: make all tile invisible;
    - CTRL+A: make all tiles visible.

    Args:
        keyboard_event: instance of matplotlib.backend_bases.KeyEvent. It should
            be generated by matplotlib itself when firing the event.
        tiles: list of Tile instances that should be shown/hidden.
        axis: the matplotlib.axes.Axes instance that contains the patches of
            the tiles. It is needed to update the figure.
    """
    logger.debug(f"New keyboard event. {keyboard_event.key=}.")

    # Give a name to the commands and exit if the corresponding keys were not
    # pressed.
    TOGGLE = " "
    HIDE = "a"
    SHOW = "ctrl+a"
    if keyboard_event.key not in [TOGGLE, SHOW, HIDE]:
        logger.debug(
            "The keyboard event was ignored (the key did not match any target"
            " action)."
        )
        return

    # Change visibility of each tile depending on the given command.
    for tile in tiles:
        if keyboard_event.key == TOGGLE:
            tile.toggle_visible()
        elif keyboard_event.key == SHOW:
            tile.set_visible(True)
        elif keyboard_event.key == HIDE:
            tile.set_visible(False)
        else:
            logger.warning(
                f"Unrecognised (and unhandled) key '{keyboard_event.key}'"
            )
            break

    # Update the plot.
    axis.figure.canvas.draw()


def wait_for_exit(figure):
    """Stall in a loop while waiting for the given figure to be closed.

    The function create a new connection listening to `'close_event'`. It waits
    for such event inside a loop that keeps calling `matplotlib.pyplot.pause`.

    Args:
        figure: a (currently open) matplotlib.pyplot.Figure innstance.
    """
    logger.debug(
        "Creating exit_helper to wait until the target figure is closed."
    )

    # Create a structure with the field 'keep_running' set to True, then add
    # a callback that changes it to False when the target figure is closed.
    exit_helper = Struct(keep_running=True)
    figure.canvas.mpl_connect(
        "close_event", lambda event: setattr(exit_helper, "keep_running", False)
    )

    # Stall in a loop until the figure is closed. Call 'pause' to ensure that
    # figures are updated regularly.
    logger.debug("Waiting for the target figure to be closed.")
    while exit_helper.keep_running:
        plt.pause(0.05)
    logger.debug("Target figure was closed.")
