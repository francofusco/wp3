import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib import colormaps
import numpy as np
import pathlib
from PyQt5.QtWidgets import QApplication, QFileDialog, QProgressBar
import sys
import time
import yaml


# Remove interaction buttons to prevent the user change the canvas accidentally.
mpl.rcParams['toolbar'] = 'None'


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
    return settings


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


class Struct(object):
    """Simple class with user-supplied fields.

    This class works like a C-structure, with the advantage that fields are
    created dynamically upon construction.
    """
    def __init__(self, **kwargs):
        """Create a new structure with the given fields.

        Args:
            kwargs: list of keyword arguments. The keywords are added as fields
                of the structure, with the supplied initial value. As an
                example, one might write:
                ```
                clock = Struct(hours=16, minutes=47, seconds=22)
                print("The current time is:", f"{clock.hours}:{clock.minutes}:{clock.seconnds}")
                ```
                Which would print: `The current time is: 16:47:22`.
        """
        for k, v in kwargs.items():
            setattr(self, k, v)


class BillItem(object):
    """Simple structure that represents items to purchase."""

    @staticmethod
    def dump_to_markdown(items, file_name):
        """Write a list of items (sorted by category) into a markdown table.

        Args:
            items: list containing BillItem instances.
            file_name: path of the csv file to be created.
        """
        with open(file_name, "w") as f:
            print("| Name | Quantity | Price | Category | Notes |", file=f)
            print("| --- | --- | --- | --- | --- |", file=f)
            total_cost = 0
            for item in sorted(items, key = lambda it: it.quantity):
                total_cost += item.quantity * item.cost
                print(f"| {item.name} | {item.quantity} | {np.round(item.cost, 2)} | {item.category} | {item.notes} |", file=f)
            print(f"| Total |  | {np.round(total_cost, 2)} |  |  |", file=f)

    def __init__(self, name=None, quantity=1, cost=0, category="", notes=""):
        if name is None:
            raise ValueError("BillItem's name must be specified.")
        if "|" in name or "|" in category or "|" in notes:
            raise ValueError("Commas cannot be specified in any of the filelds of .")
        self.name = name
        self.quantity = quantity
        self.cost = cost
        self.category = category
        self.notes = notes




def wait_for_exit(figure):
    """Stall in a loop while waiting for the given figure to be closed.

    The function create a new connection listening to `'close_event'`. It waits
    for such event inside a loop that keeps calling `matplotlib.pyplot.pause`.

    Args:
        figure: a (currently open) matplotlib.pyplot.Figure innstance.
    """
    # Create a structure with the field 'keep_running' set to True, then add
    # a callback that changes it to False when the target figure is closed.
    exit_helper = Struct(keep_running = True)
    figure.canvas.mpl_connect('close_event', lambda event: setattr(exit_helper, "keep_running", False))

    # Stall in a loop until the figure is closed. Call 'pause' to ensure that
    # figures are updated regularly.
    while exit_helper.keep_running:
        plt.pause(0.001)


class Hexagon(object):
    """Class that represents Hexagons in a grid layout.

    This class groups some utility functions related to tiling, plotting, etc.
    """

    @staticmethod
    def grid2xy(row, col, vertical_stacking, spacing, side_length):
        """Calculate the coordinates of a hexagon in a grid.

        This function converts grid coordinates in the form (row, colum) to a
        point (x, y) in the Cartesian space, so that hexagons with a given
        geometry can tile the plane. The conventions used here correspond to
        those named "odd-q" and "odd-r" in
        `this webpage <https://www.redblobgames.com/grids/hexagons/#coordinates>`_ .
        The only difference being that rows indices grow from the bottom towards
        the top.

        Args:
            row: vertical grid coordinate of the hexagon.
            col: horizontal grid coordinate of the hexagon.
            vertical_stacking: if True, the top of the hexagon is flat.
                Otherwise, a vertex is located on the top and the right and left
                sides are flat.
            spacing: margin between adjacent hexagons.
            side_length: size of a side of the hexagon. It is also the distance
                between the center and the vertices.
        Returns:
            x, y: Cartesian coordinates of the center of the hexagon.
        """
        # The code below is designed for a vertical stacking layout. However, we
        # can swap the gird coordinates, do the calculations, and swap the
        # result in order to deal with horizontal stacking as well.
        if not vertical_stacking:
            row, col = col, row

        # Coordinates of the center, so that the pair (0, 0) is mapped into the
        # origin of the catesian plane.
        x = col * (3 * side_length + np.sqrt(3) * spacing) / 2
        y = (row if col%2==0 else (row+0.5)) * (np.sqrt(3) * side_length + spacing)

        # Shift the coordinates so that the hexagon with grid coordinates (0, 0)
        # touches the x and y axes. This is useful for filling rectangles, which
        # is one of the goals here.
        x += side_length + spacing * 2 / np.sqrt(3)
        y += side_length * np.sqrt(3) / 2 + spacing

        # Swap the resulting coordinates if the layout uses horizontal stacking.
        if not vertical_stacking:
            x, y = y, x

        # Return the result as a tuple.
        return x, y

    @staticmethod
    def fit_in_sheet(num_hexagons, vertical_stacking, spacing, side_length, sheet_width, sheet_height):
        """Fit as many hexagons as possible inside a rectangular domain.

        This function tries to fit a certain number of hexagons (at most) in a
        rectangular domain of given size. The algorithm works by placing an
        hexagon in the bottom-left corner, then trying to place one on its
        right, then another one, etc., until the row is full. The algorithm then
        starts once again, but trying to place the hexagons on a new row. This
        operation continues until either all hexagons have been placed or until
        the domain is full, ie, there is no space for additional hexagons.
        Once the procedure is completed, the function returns a list containing
        the hexagons that could be placed within the domain.

        The parameters `num_hexagons`, `sheet_width` and `sheet_height` can be
        set to `inf` (infinity) to signify "as much as needed" (see their
        documentation). However, note that if both `num_hexagons` and either of
        `sheet_width` or `sheet_height` are set to `inf`, the function will loop
        forever since it will try to fit an infinite amount of hexagons in an
        infinitely large space.

        Args:
            num_hexagons: maximum number of hexagons to be placed. If there is
                enough room to accomodate all of them, the result will be a
                tiling that partially fills the given area. To completely fill
                a rectangle of finite dimensions, `num_hexagons` can be set to
                `inf`.
            vertical_stacking: desired hexagon orientation. If True, the top of
                the hexagon is flat. Otherwise, a vertex is located on the top
                and the right and left sides are flat.
            spacing: margin between adjacent hexagons.
            side_length: size of a side of the hexagon. It is also the distance
                between the center and the vertices.
            sheet_width: width of the rectangular domain. You can set it to
                `inf` if you want to arrange a certain number of hexagons in a
                single row.
            sheet_height: height of the rectangular domain. You can set it to
                `inf` if you want to arrange a certain number of hexagons in
                multiple rows (as many as needed) of fixed size.
        Returns:
            hexagons: a list of Hexagon instances, all compactly fitting inside
                the specified domain.
        """
        # Prepare working variables.
        hexagons = []
        row = 0
        col = 0

        # Keep looping until all hexagons have been placed.
        while len(hexagons) < num_hexagons:
            # Create a hexagon that should fit in the current grid coordinates.
            hexagon = Hexagon(row, col, vertical_stacking, spacing, side_length)

            if hexagon.within((0, sheet_width), (0, sheet_height)):
                # If the hexagon does fit, "place it" and then go to the
                # second-next column. We advance by two due to the vertical
                # offsets that are present in odd columns when using vertical
                # stacking. We fill the current row by placing the cells that
                # are in even columns first and then those that are in odd ones.
                hexagons.append(hexagon)
                col += 2
            elif col == 0:
                # If the hexagon does not fit and it was to be placed in column
                # 0, it means that we finished the allotted space - since
                # further hexagons would be placed at the same height or above.
                break
            elif col % 2 == 0:
                # If the hexagon does not fit and the current column index is
                # not 0, it means that we ran out of space horizontally.
                # Furthermore, if the column index is even, it means that we
                # still have to place hexagons in odd columns. We therefore stay
                # in the same row, but starting now at column 1.
                col = 1
            else:
                # Finally, if none of the above criteria are met, it means that
                # we completely filled the current row and have to move to a new
                # one: set the column index back to zero and increment the row.
                col = 0
                row += 1

        # Exit by returning the list of hexagons that could be fit in the
        # domain.
        return hexagons

    def __init__(self, row, col, vertical_stacking, spacing, side_length):
        """Constructor for an hexagonal tile.

        Args:
            row: vertical grid coordinate of the hexagon.
            col: horizontal grid coordinate of the hexagon.
            vertical_stacking: if True, the top of the hexagon is flat.
                Otherwise, a vertex is located on the top and the right and left
                sides are flat.
            spacing: margin between adjacent hexagons.
            side_length: size of a side of the hexagon. It is also the distance
                between the center and the vertices.
        """
        # Store grid and Cartesian coordinates.
        self.row = row
        self.col = col
        self.x, self.y = Hexagon.grid2xy(row, col, vertical_stacking, spacing, side_length)

        # Store other geometric parameters.
        self.side_length = side_length
        self.spacing = spacing
        self.vertical_stacking = vertical_stacking

        # Create patches for visualization in matplotlib.
        self.patch = patches.RegularPolygon((self.x, self.y), 6, radius=side_length, orientation=np.pi/6 if vertical_stacking else 0)
        self.outer_patch = patches.RegularPolygon((self.x, self.y), 6, radius=side_length+spacing*2/np.sqrt(3), orientation=np.pi/6 if vertical_stacking else 0)
        self.outer_patch.set_facecolor("k")

    def make_copy(self):
        """Create a copy of this Hexagon by calling the constructor.

        This method is useful in case the same hexagon has to be placecd in
        multiple plots - matplotlib allows a patch to be placed in on axis only.

        Returns:
            hexagon: a copy of self, created by calling the constructor. This
                does not copy the visibility or the color of the hexagon.
        """
        return Hexagon(self.row, self.col, self.vertical_stacking, self.spacing, self.side_length)

    def add_to_axis(self, ax):
        """Add the hexagon and its border to a plot.

        Args:
            ax: matplotlib.axes.Axes instance where the patch should be placed.
        """
        ax.add_patch(self.outer_patch)
        ax.add_patch(self.patch)

    def vertices(self, border=1.0):
        """List of vertices, as a NumPy array.

        Args:
            border: fraction of the border to include. Use 0 to get the vertices
                of the hexagon without considering the border at all. Use 1 if
                you want the vertices plus the outer patch. Note that the outer
                patches of adjacent hexagons overlap (this is useful for visual
                purposes). If you want the vertices that are equidistant from
                the hexagon and its neighbour's centers as well, use 0.5.
        Returns:
            verts: a NumPy array with shape (6, 2).
        """
        # Calculate the radius (distance between the center and the vertices).
        radius = self.side_length + border * self.spacing * 2 / np.sqrt(3)

        # Equispaced angles of the size vertices.
        angles = np.pi/3 * np.arange(6)
        if not self.vertical_stacking:
            angles += np.pi/6

        # Convert polar coordinates to Cartesian ones, and shift by the center
        # of the hexagon.
        return np.stack((self.x + radius * np.cos(angles), self.y + radius * np.sin(angles))).T

    def within(self, x_range, y_range, include_border=True):
        """Tells if this hexagon fits the given rectangular domain.

        Args:
            x_range: tuple in the form (xmin, xmax), defining the width of the
                rectangular domain.
            y_range: tuple in the form (ymin, ymax), defining height of the
                rectangular domain.
            include_border: if True, then the hexagon and its margin must both
                fully fit the domain. Otherwise, only the hexagon has to.
        Returns:
            fits: True if the hexagon (and eventually its outer margin) fits
                within the given rectangular domain.
        """
        # Make the problem simpler by shrinking the domain in all directions and
        # checking only if the center belongs to the shrinked domain. To do so,
        # half of the width and height of the hexagon is subtracted from the
        # boundaries.
        half_width = self.side_length
        half_height = self.side_length * np.sqrt(3) / 2

        # If margins are included, half of them are subtracted as well.
        if include_border:
            half_width += self.spacing / np.sqrt(3)
            half_height += self.spacing

        # If hexagons are horizontally stacked, the width and height are
        # swapped.
        if not self.vertical_stacking:
            half_width, half_height = half_height, half_width

        # Check if the center of the hexagon is inside the shrinked domain.
        xmin, xmax = x_range
        ymin, ymax = y_range
        return xmin + half_width <= self.x <= xmax - half_width and ymin + half_height <= self.y <= ymax - half_height

    def contains(self, x, y):
        """Check if a point lies within this hexagon.

        Args:
            x, y: Cartesian coordinates of the point.
        Returns:
            contained: True if the point is within the hexagon. The border is
                not considered for this check.
        """
        # Distance between the point and the center of the hexagon. The absolute
        # value is taken since the hexagon is symmetric with respect to the x
        # and y axis: if a point fits in the hexagon, so will its
        # reflection in the first quadrant. We check only if this reflection is
        # inside the hexagon since it requires just two inequalities.
        dx = np.abs(self.x - x)
        dy = np.abs(self.y - y)

        # Swap the coordinates if the hexagons are stacked horizontally.
        if not self.vertical_stacking:
            dx, dy = dy, dx

        # Check if the reflection is inside the hexagon. This requires just two
        # inequalities.
        return dy <= self.side_length * np.sqrt(3) / 2 and np.sqrt(3) * dx + dy <= np.sqrt(3) * self.side_length

    def adjacent(self, other):
        """Check if this hexagon is adjacent to another.

        The check is very simplified: we simply verify that the centers are at
        the expected distance.

        Args:
            other: a Hexagon instance.
        Returns:
            True if the hexagons are adjacent, False otherwise.
        """
        distance = np.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)
        return np.allclose(distance, np.sqrt(3) * self.side_length + self.spacing)

    def set_visible(self, visible):
        """Change visibility of this hexagon.

        This method allows to hide or show the patches associated to this
        hexagon. It is useful for animations with matplotlib.

        Args:
            visible: boolean specifying the visibility of the patches.
        """
        self.patch.set_visible(visible)
        self.outer_patch.set_visible(visible)

    def toggle_visible(self):
        """Change visibility of this hexagon.

        This method allows to hide or show the patches associated to this
        hexagon. It is useful for animations with matplotlib. The hexagon
        becomes hidden if it was visible, and viceversa.
        """
        self.set_visible(not self.patch.get_visible())

    def is_visible(self):
        """Return the visibility of the hexagon."""
        return self.patch.get_visible()


def unique_vertices(hexagons):
    """Return the coordinates of unique vertices in a set of hexagons.

    Given a set of hexagons, loop through all their vertices and create a list
    of all vertices, with no repetitions.

    Args:
        hexagons: a list of Hexagon instances.
    Returns:
        A NumPy array with shape (n_vertices, 2), containing the coordinates of
        all unique vertices in the group of hexagons.
    """
    vertices = hexagons[0].vertices(border=0.5)
    for hexagon in hexagons[1:]:
        for v in hexagon.vertices(border=0.5):
            vector_distances = vertices - v
            if not np.isclose(np.einsum("ij,ij->i", vector_distances, vector_distances).min(), 0):
                vertices = np.vstack((vertices, v))
    return vertices


def get_bounding_box(hexagons):
    """Calculate the coordinates of a rectangle containing all given hexagons.

    Args:
        hexagons: list of Hexagon instances.
    Returns:
        (xmin, ymin), (xmax, ymax): coordinates of the bottom-left and top-right
            corners of the bounding box.
    """
    vertices = np.vstack([h.vertices() for h in hexagons])
    return vertices.min(axis=0), vertices.max(axis=0)


def get_bounding_box_size(hexagons):
    """Calculate the sizes of a rectangle containing all given hexagons.

    Args:
        hexagons: list of Hexagon instances.
    Returns:
        width, height: dimensions of the bounding box.
    """
    (xmin, ymin), (xmax, ymax) = get_bounding_box(hexagons)
    return (xmax - xmin), (ymax - ymin)


def get_bounding_box_area(hexagons):
    """Calculate the area of a rectangle containing all given hexagons.

    Args:
        hexagons: list of Hexagon instances.
    Returns:
        area: surface area of the bounding box.
    """
    width, height = get_bounding_box_size(hexagons)
    return width * height


def toggle_hexagon_if_clicked(mouse_event, hexagon, axis):
    """Mouse callback to toggle visibility of a hexagon.

    This function is meant to be used as callback for matplotlib events, to
    allow showing/hiding a hexagon when clicked.

    Args:
        mouse_event: instance of matplotlib.backend_bases.MouseEvent. It should
            be generated by matplotlib itself when firing the event.
        hexagon: the hexagon that should be shown/hidden.
        axis: the matplotlib.axes.Axes instance that contains the hexagonal
            patches. It is needed to update the figure.
    """
    # Ignore events fired when the mouse is outside the drawing area.
    if mouse_event.xdata is None or mouse_event.ydata is None:
        return

    # Toggle the hexagon if the mouse is inside it.
    if hexagon.contains(mouse_event.xdata, mouse_event.ydata):
        hexagon.toggle_visible()
        axis.figure.canvas.draw()

def toggle_all_hexagons(keyboard_event, hexagons, axis):
    """Keyboard callback to toggle visibility of many hexagons.

    This function is meant to be used as callback for matplotlib events, to
    allow showing/hiding a set of hexagons when some keys are pressed.

    Controls:
    - Space bar: toggle each hexagon;
    - A: make all hexagons visible;
    - CTRL+A: make all hexagons invisible.

    Args:
        keyboard_event: instance of matplotlib.backend_bases.KeyEvent. It should
            be generated by matplotlib itself when firing the event.
        hexagons: list of hexagons that should be shown/hidden.
        axis: the matplotlib.axes.Axes instance that contains the hexagonal
            patches. It is needed to update the figure.
    """
    # Give a name to the commands and exit if the corresponding keys were not
    # pressed.
    TOGGLE = " "
    HIDE = "a"
    SHOW = "ctrl+a"
    if keyboard_event.key not in [TOGGLE, SHOW, HIDE]:
        return

    # Change visibility of each hexagon depending on the given command.
    for hexagon in hexagons:
        if keyboard_event.key == TOGGLE:
            hexagon.toggle_visible()
        elif keyboard_event.key == SHOW:
            hexagon.set_visible(True)
        elif keyboard_event.key == HIDE:
            hexagon.set_visible(False)
        else:
            print(f"WARNING: unrecognised (and unhandled) key '{keyboard_event.key}'")
            break

    # Update the plot.
    axis.figure.canvas.draw()


class RoutingData:
    """Class that allows to model the routing problem.

    It contains two fields: `vertices` and `hexagons`. The former is a
    NumPy array with shape `(n_vertices, 2)`, such that `vertices[i]` gives
    the Cartesian coordinates of the i-th unique vertex, across all hexagons.
    The latter is a list with 6-dimensional integer-valued arrays, corresponding
    to the indices of the vertices that belong to that hexagon. In practice,
    `vertices[hexagon[j,k]]` provides the Cartesian coordinates of the the k-th
    vertex of the j-th hexagon.
    """

    def __init__(self, hexagons):
        """Create data to be used to find an optimal cable routing.

        Args:
            hexagons: a list of Hexagon instances.
        """
        self.vertices = unique_vertices(hexagons)
        hexagons_indices = []

        for hexagon in hexagons:
            # This is a fast (maybe convoluted) way to create a matrix of squared
            # distances, such that vector_distances[i,j] provides the displacement
            # between the vertex vertices[i] and the j-th vertex of the hexagon.
            vector_distances = self.vertices.reshape(-1, 1, 2) - hexagon.vertices(border=0.5).reshape(1, 6, 2)

            # Using Einstein's summation, convert displacement vectors into scalars.
            # The result is a matrix D whose elements D[i,j] are the squared
            # distances between vertices[i] and the j-th vertex of the hexagon. By
            # taking argmin along the first axis, we are left with six values: they
            # represent the indices of each vertex of the hexagon.
            hexagons_indices.append(np.einsum("ijk,ijk->ij", vector_distances, vector_distances).argmin(axis=0))

        # Convert into an array.
        self.hexagons = np.array(hexagons_indices)

        self.n_vertices = len(self.vertices)
        self.n_hexagons = len(self.hexagons)

    def create_sample(self):
        """Create a routing sample.

        Returns:
            A list containing tuples (i,j), representing a routing candidate.
            The list (i1,j1), (i2,j2), ... means that we start by visiting the
            hexagon i1, passing through its vertex j1. The choices are
            completely randomized. The actual ouput is a NumPy array with shape
            (2, n_hexagons).
        """
        return np.stack((np.random.permutation(self.n_hexagons), np.random.choice(6, size=self.n_hexagons)))

    def evaluate_cost(self, sample, repetition_penalty=100):
        # Get the sequence of vertex indices from the sample.
        index_sequence = self.hexagons[sample[0], sample[1]]

        # Calculate the length of the routing path.
        d = np.diff(self.vertices[index_sequence], axis=0)
        path_length = np.sum(np.sqrt(np.einsum("ij,ij->i", d, d)))

        # Count how many times vertices are repeated. Ideally, we would like
        # each vertex to be visited at most once. We thus have to penalize any
        # further appearances. As an example, if the list is
        #   [1, 2, 1, 3, 4, 4, 4]
        # then both 1 and 4 appear more than once. The code would evaluate that
        # the number 1 has one repetition, while number 4 has two, for a total
        # of 3 repetitions.
        appearances = np.zeros(self.n_vertices)
        for i in index_sequence:
            appearances[i] += 1
        repetitions = np.sum(appearances[appearances > 1])

        # Return the cost as the sum of the total length plus a heavy penalty
        # on the number of repetitions.
        return path_length + repetition_penalty * repetitions

    def mutate_order(self, sample, hexagon_index, distance=1):
        next_hexagon_index = (hexagon_index + distance) % self.n_hexagons
        sample[:, [hexagon_index, next_hexagon_index]] = sample[:, [next_hexagon_index, hexagon_index]]
        return sample

    def mutate_vertex(self, sample, hexagon_index, vertex_index):
        sample[1, hexagon_index] = vertex_index
        return sample

    def improve(self, sample, cost, attempts):
        h = np.random.randint(self.n_hexagons)
        if np.random.randint(2) == 0:
            mutations = [self.mutate_order(sample.copy(), h, distance=i) for i in range(10)]
        else:
            mutations = [self.mutate_vertex(sample.copy(), h, i) for i in range(6)]

        costs = [self.evaluate_cost(mutation) for mutation in mutations]
        idx = np.argmin(costs)

        if costs[idx] < cost:
            return self.improve(mutations[idx], costs[idx], attempts)
        elif attempts > 0:
            return self.improve(sample, cost, attempts-1)
        else:
            return sample, cost

    def optimize(self, best_sample=None, max_attempts=500, improvement_steps=100, progressbar_length=30):
        if best_sample is None:
            best_sample = self.create_sample()
        best_cost = self.evaluate_cost(best_sample)
        initial_sample = best_sample.copy()

        print("Routing in progress (CTRL+C to interrupt).")
        try:
            for iter in range(max_attempts):
                progress = np.round(progressbar_length * (iter+1) / max_attempts).astype(int)
                print(f"\r[{'~'*progress}{' '*(progressbar_length-progress)}] {iter+1} of {max_attempts}", end="", flush=True)

                sample = best_sample.copy() if np.random.randint(50) == 0 else self.create_sample()
                cost = self.evaluate_cost(sample)
                sample, cost = self.improve(sample, cost, improvement_steps)

                if cost < best_cost:
                    best_sample = sample.copy()
                    best_cost = cost
        except KeyboardInterrupt:
            pass
        print()
        return best_sample

    def plot_routing(self, sample, hexagons, ax, alpha=0.2, color="black"):
        vertex_sequence = self.vertices[self.hexagons[sample[0], sample[1]]]

        for i in range(self.n_hexagons):
            hexagon = hexagons[sample[0,i]]
            p = (1-alpha) * vertex_sequence[i] + alpha * np.array([hexagon.x, hexagon.y])
            ax.plot(*p, "o", color=color)
            if i > 0:
                d = p - prev_p
                ax.arrow(*prev_p, *d, color=color, linewidth=0.5, head_width=0.01, length_includes_head=True)
            prev_p = p

        for i, hexagon in enumerate(hexagons):
            ax.text(hexagon.x, hexagon.y, "$H_{" + str(i) + "}$", color="red", horizontalalignment="center")


def tree_search(choices, target, sequence=None, current_value=0, current_cost=0):
    """Optimization algorithm to evaluate best combination of elements.

    Problem statement: a set of items are available, each with an associated
    value and cost. One can choose any combination of the available items (with
    repetitions) with the only constraint that removing any of the elements will
    make the total value drop below a given target. The goal is to find the
    valid combination whose total cost is minimal. If multiple solutions exist,
    then the one that also maximizes the difference between the total value and
    the target is prioritized. If this still leads to multiple solutions, the
    one that has the list amount of elements is selected.

    The algorithm is quite generic. It can be used, as an example, to evaluate
    how many LED strips to purchase. In this case, one could use the length of
    the strip as value and its cost as, well, cost. The target would be the
    total length needed. As an example, if one could choose between a 1m strip
    sold at 10$ and a 5m one worth 15$, and needs a total of 11m of strips, the
    algorithm would find that the best solution would be to buy two strips that
    are 5m long and one that is 1m long, for a total of 40$. If 13m were needed,
    the algorithm would instead suggest to buy 3 strips of 5m each, for a total
    of 15m and a cost of 45$. This is better than any other combination, such as
    buying 2 5m strips and 3 1m strips, which would result in 13m of length at
    a cost of 60$.

    Args:
        choices: a list of objects, each of which must have the fields "value"
            and "cost".
        target: the total value that a sequence must reach to be valid.
        sequence: if given, it represents a partial solution of already selected
            items. The parameter is mainly intended for internal use.
        current_value: if given, it represents the value of the partial
            solution. The parameter is mainly intended for internal use.
        current_cost: if given, it represents the cost of the partial solution.
            The parameter is mainly intended for internal use.
    Returns:
        best_sequence: sequence of items to select. It is sorted with the same
            orded of items in `choices`. Items can appear multiple times.
        best_cost: cost of the sequence.
        best_value: total value of the sequence.
    """
    # Prepare working variables.
    if sequence is None:
        sequence = []
    best_sequence = []
    best_cost = np.inf
    best_value = -np.inf

    for i, elem in enumerate(choices):
        # Add value and cost
        new_value = current_value + elem.value
        new_cost = current_cost + elem.cost
        new_sequence = sequence + [elem]

        # If we did not reach a terminal state, get it using recursion.
        if new_value < target:
            new_sequence, new_cost, new_value = \
                tree_search(choices[i:], target, sequence=new_sequence,
                            current_value=new_value, current_cost=new_cost)

        # Check the current solution. If it is the best found so far, store it.
        if new_cost < best_cost or (new_cost == best_cost and (new_value > best_value or (new_value == best_value and len(new_sequence) < len(best_sequence)))):
            best_cost = new_cost
            best_value = new_value
            best_sequence = new_sequence

    # Return the optimal result, with its cost and value as well.
    return best_sequence, best_cost, best_value


def named_tree_search(named_choices, target):
    """Optimization algorithm to evaluate best combination of elements.

    This is a variant of `tree_search`. It assumes that the choices have an
    additional "name" field, that can be used to distinguish between choices.
    Using this field, the original solution is modified to be a list of pairs
    (item, amount), telling how many units of each item are to be used.

    Args:
        choices: a list of objects, each of which must have the fields "value",
            "cost" and "name". Note that if multiple items share the same name,
            the solution might be wrong, especially if these items have
            different values and/or costs.
        target: the total value that a combination must reach to be valid.
    Returns:
        best_sequence: sequence of tuples (item, amount), representing the items
            to select and their quantity.
        best_cost: cost of the sequence.
        best_value: total value of the sequence.
    """
    # Solve the problem using the vanilla tree_search.
    best_sequence, best_cost, best_value = tree_search(named_choices, target)

    # Handle empty solutions (even though they should not be possible).
    if len(best_sequence) == 0:
        return []

    # Prepare a list of unique items and their frequency.
    unique_elements = [best_sequence[0]]
    frequency = [1]

    # Scan all items in the solution (except the first one, which has been
    # processed already).
    for elem in best_sequence[1:]:
        # If the current element has been found already, increment its
        # frequency. Otherwise, add it and set its frequency to one.
        if elem.name == unique_elements[-1]:
            frequency[-1] += 1
        else:
            unique_elements.append(elem)
            frequency.append(1)

    # Return the solution as a list of (item, amount) tuples.
    return [(elem, freq) for elem, freq in zip(unique_elements, frequency)], best_cost, best_value


def main():
    # Get configuration file and working directory.
    config_file = pathlib.Path(retrieve_settings_file())
    output_dir = config_file.parent.joinpath("design_info")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load settings from a YAML file.
    settings = load_settings(config_file)

    # Load a design from the settings, if this is available.
    initial_tiling = settings["panels"].get("initial_tiling")

    # Fill the available design space with hexagons.
    hexagons = []
    for row in range(settings["panels"]["rows"]):
        for col in range(settings["panels"]["columns"]):
            hexagon = Hexagon(row, col, settings["panels"]["vertical_stacking"],
                              settings["panels"]["spacing"],
                              settings["panels"]["side_length"])
            hexagons.append(hexagon)
            # If an initial design is provided and this hexagon is not part of it,
            # make sure to hide it.
            if initial_tiling is not None and [row, col] not in initial_tiling:
                hexagon.set_visible(False)

    # Calculate the dimensions of the canvas.
    canvas_width, canvas_height = get_bounding_box_size(hexagons)

    # Create a figure to plot the hexagons.
    fig, ax = plt.subplots()
    ax.set_aspect("equal")
    ax.set_xlim(0, canvas_width)
    ax.set_ylim(0, canvas_height)
    ax.tick_params(which="both", bottom=False, top=False, right=False,
                   left=False, labelbottom=False, labelleft=False)
    ax.set_axisbelow(True)
    fig.tight_layout()

    # Place the hexagon patches in the plot.
    for hexagon in hexagons:
        # Add the current hexagon to the canvas, and create an event connection
        # that toggles its visibility if one clicks inside its patch.
        hexagon.add_to_axis(ax)
        fig.canvas.mpl_connect('button_press_event', lambda event, hexagon=hexagon: toggle_hexagon_if_clicked(event, hexagon, ax))

    # Create a connection to hide, show or toggle all hexagon visibilities at
    # once using the keyboard.
    fig.canvas.mpl_connect('key_press_event', lambda event: toggle_all_hexagons(event, hexagons, ax))

    # Detect when a figure is closed using an event connection.
    exit_helper = Struct(keep_running = True)
    fig.canvas.mpl_connect('close_event', lambda event: setattr(exit_helper, "keep_running", False))

    # Period and shift factor to color all hexagons using a HSV wave.
    period = 4.0
    velocity = 0.005

    # Loop that changes the color of each hexagon and then updates the plot.
    # The loop will stop once the figure is closed.
    while exit_helper.keep_running:
        for i, hexagon in enumerate(hexagons):
            hexagon.patch.set_color(colormaps["hsv"](((time.time() / period - i * velocity) % 1)))
        plt.pause(0.001)

    # Collect all hexagons (and their coordinates) in the chosen design.
    visible_hexagons = []
    tiling_coordinates = []
    for hexagon in hexagons:
        if hexagon.is_visible():
            visible_hexagons.append(hexagon)
            tiling_coordinates.append([hexagon.row, hexagon.col])
    with open(output_dir.joinpath("initial_tiling.yaml"), "w") as f:
        print("initial_tiling:", tiling_coordinates, file=f)

    routing_data = RoutingData(visible_hexagons)
    best_routing = routing_data.create_sample()
    if "cache" in settings["routing"]:
        cache = np.array(settings["routing"]["cache"])
        if cache.shape == best_routing.shape:
            best_routing = cache


    while True:
        # Create a figure to plot the hexagons.
        fig, ax = plt.subplots()
        ax.set_aspect("equal")
        (xmin, ymin), (xmax, ymax) = get_bounding_box(visible_hexagons)
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.tick_params(which="both", bottom=False, top=False, right=False,
                       left=False, labelbottom=False, labelleft=False)
        ax.set_axisbelow(True)
        fig.tight_layout()

        hexagons_copy = [h.make_copy() for h in visible_hexagons]
        for hexagon in hexagons_copy:
            hexagon.add_to_axis(ax)
            hexagon.patch.set_color("white")
            hexagon.outer_patch.set_color("lightgray")

        fig.savefig(output_dir.joinpath("wp3_design.pdf"), bbox_inches='tight')

        routing_data.plot_routing(best_routing, visible_hexagons, ax)

        exit_helper = Struct(keep_running=True, reroute=False)
        fig.canvas.mpl_connect('key_press_event', lambda event: setattr(exit_helper, "reroute", event.key == " "))
        fig.canvas.mpl_connect('close_event', lambda event: setattr(exit_helper, "keep_running", False))

        # Loop that waits for the figure to be closed or for the space bar to be pressed.
        while exit_helper.keep_running and not exit_helper.reroute:
            plt.pause(0.001)

        # Save the current routing into a figure, to make sure that it is safely stored somewhere.
        fig.savefig(output_dir.joinpath("wp3_routing.pdf"), bbox_inches='tight')
        plt.close("all")

        if exit_helper.reroute:
            routing_cost_before = routing_data.evaluate_cost(best_routing)
            routing_kwargs = settings["routing"].copy()
            if "cache" in routing_kwargs:
                routing_kwargs.pop("cache")
            best_routing = routing_data.optimize(best_sample=best_routing, **routing_kwargs)
            routing_cost_after = routing_data.evaluate_cost(best_routing)
            print("Cost decreased by", np.round(100 * (routing_cost_before-routing_cost_after) / routing_cost_before, 3))
        else:
            break

    with open(output_dir.joinpath("routing_cache.yaml"), "a") as f:
        print("cache:", best_routing.tolist(), file=f)

    # List of items to be purchased/manufactured.
    bill_of_materials = []

    # Count how many "walls" are needed. If all hexagons were separated, we
    # would have a total of six outer walls per hexagon. However, whenever two
    # hexagons share a side, the corresponding two outer walls should be
    # replaced by a single inner wall.
    outer_walls = len(visible_hexagons) * 6
    inner_walls = 0
    # Look for all pairs of hexagons, with no repetitions.
    for i, hexagon in enumerate(visible_hexagons):
        for other in visible_hexagons[i+1:]:
            # If the other hexagon is adjacent, then remove one shared wall.
            if hexagon.adjacent(other):
                outer_walls -= 2
                inner_walls += 1
    walls_notes = f"Side Length: {np.round(1000*settings['panels']['side_length'], 2)}mm. Spacing: {np.round(1000*settings['panels']['spacing'], 2)}mm. Remember to update the CAD accordingly and export the STL meshes to print them."
    bill_of_materials.append(BillItem(name="outer wall", quantity=outer_walls, category="3D printed", notes=walls_notes))
    bill_of_materials.append(BillItem(name="inner wall", quantity=inner_walls, category="3D printed", notes=walls_notes))

    # Process panel materials. The goal is, for each panel type, to evaluate how
    # many hexagons can be inserted, or how much it costs to fill them (in case
    # the cost depends on the size).
    # TODO: it would be ideal to allow, for variable size materials, to let
    # the designer try with different sizes as well.
    panel_material_data = {}

    for i, (layer_name, layer) in enumerate(settings["materials"]["sheets"].items()):
        fig, ax = plt.subplots()
        width, height = layer["size"]
        hexagons_vs = Hexagon.fit_in_sheet(len(visible_hexagons), True, 0,
                                           settings["panels"]["side_length"],
                                           width, height)
        hexagons_hs = Hexagon.fit_in_sheet(len(visible_hexagons), False, 0,
                                           settings["panels"]["side_length"],
                                           width, height)
        if height == np.inf:
            _, height_vs = get_bounding_box_size(hexagons_vs)
            _, height_hs = get_bounding_box_size(hexagons_hs)
            if height_vs < height_hs:
                bb_height = height_vs
                hexagons_layer = hexagons_vs
            else:
                bb_height = height_hs
                hexagons_layer = hexagons_hs
            layer_cost = layer.get("cost", 0) * height_vs
        else:
            area_vs = get_bounding_box_area(hexagons_vs)
            area_hs = get_bounding_box_area(hexagons_vs)
            hexagons_layer = hexagons_vs if area_vs < area_hs else hexagons_hs
            layer_cost = layer.get("cost", 0)
            bb_height = height

        panel_material_data[layer_name] = Struct(name=layer_name,
                                                 value=len(hexagons_layer),
                                                 cost=layer_cost,
                                                 variable_size=height==np.inf,
                                                 height=bb_height,
                                                 unit_cost=layer.get("cost", 0))

        ax.set_aspect("equal")
        ax.set_xlim(0, width)
        ax.set_ylim(0, bb_height)
        ax.set_title(layer_name)

        for hexagon in hexagons_layer:
            hexagon.add_to_axis(ax)

        fig.tight_layout()
        fig.savefig(output_dir.joinpath(f"{layer_name}.pdf"), bbox_inches='tight')
        plt.close("all")

    for i, materials in enumerate(settings["assembly"]["sheets"]):
        components, cost, value = named_tree_search([panel_material_data[m] for m in materials], len(visible_hexagons))
        for component, quantity in components:
            url = settings["materials"]["sheets"][component.name].get("url")
            url_md = f"[url link]({url})" if url is not None else ""
            if component.variable_size:
                quantity = np.round(component.height, 3)
            bill_of_materials.append(BillItem(name=component.name, quantity=quantity, cost=component.unit_cost, category=f"sheets-{i}", notes=url_md))

    leds_material_data = {}
    for i, (strip_name, strip) in enumerate(settings["materials"]["leds"].items()):
        strip_length = strip["number_of_leds"] / strip["leds_per_meter"]
        leds_material_data[strip_name] = Struct(name=strip_name,
                                                value=strip_length,
                                                cost=strip.get("cost", 0))

    required_led_length = len(visible_hexagons) * 6 * settings["panels"]["side_length"]
    for i, materials in enumerate(settings["assembly"]["leds"]):
        components, cost, value = named_tree_search([leds_material_data[m] for m in materials], required_led_length)
        for component, quantity in components:
            url = settings["materials"]["leds"][component.name].get("url")
            url_md = f"[url link]({url})" if url is not None else ""
            bill_of_materials.append(BillItem(name=component.name, quantity=quantity, cost=component.cost, category=f"leds-{i}", notes=url_md))
        watts = sum(n*settings["materials"]["leds"][c.name].get("watts", np.nan) for c, n in components)
        if watts != np.nan:
            bill_of_materials.append(BillItem(name=f"{watts}W Power Supply Unit", category=f"leds-{i}", notes="The power has been estimated. You might need a lower wattage."))

    bill_of_materials.append(BillItem(name="3 pin connectors", quantity=len(visible_hexagons), category="wiring", notes="The quantity refers to male/female pairs."))
    bill_of_materials.append(BillItem(name="Three-way electrical wire", quantity=np.round(routing_data.evaluate_cost(best_routing, repetition_penalty=0), 3), category="wiring", notes="This is likely an overestimation, since the length of the connectors is not taken into account."))

    BillItem.dump_to_markdown(bill_of_materials, output_dir.joinpath("bill_of_materials.md"))

if __name__ == '__main__':
    main()
