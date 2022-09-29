import numpy as np


class Tile(object):
    """Class that represents tiles in a grid layout.

    This base class groups some utility functions related to tiling, plotting,
    etc. Subclasses implement the logic related to the geometry they use.
    """

    @classmethod
    def get_variants(cls):
        """Valid variants for a tile type.

        This default implementation returns a single variant (0), but it can be
        reimplemented in subclasses that allow to create multiple variants.

        Returns:
            An list of integer values, each representing a valid variant for the
            tile.
        """
        return [0]

    @classmethod
    def fit_in_sheet(cls, num_tiles, spacing, side_length, variant, sheet_width, sheet_height):
        """Fit as many tiles as possible inside a rectangular domain.

        This function tries to fit a certain number of tiles (at most) in a
        rectangular domain of given size. The algorithm works by placing a tile
        in the bottom-left corner, then trying to place one on its right, then
        another one, etc., until the row is full. The algorithm then starts once
        again, but trying to place the tiles on a new row. This operation
        continues until either all tiles have been placed or until the domain is
        full, ie, there is no space for additional tiles. Once the procedure is
        completed, the function returns a list containing the tiles that could
        be placed within the domain.

        The parameters `num_tiles`, `sheet_width` and `sheet_height` can be
        set to `inf` (infinity) to signify "as much as needed" (see their
        documentation). However, note that if both `num_tiles` and either of
        `sheet_width` or `sheet_height` are set to `inf`, the function will loop
        forever since it will try to fit an infinite amount of tiles in an
        infinitely large space.

        Args:
            num_tiles: maximum number of tiles to be placed. If there is enough
                room to accomodate all of them, the result will be a tiling that
                partially fills the given area. To completely fill a rectangle
                of finite dimensions, `num_tiles` can be set to `inf`.
            spacing: margin between adjacent tiles.
            side_length: size of a side of the tiles.
            sheet_width: width of the rectangular domain. You can set it to
                `inf` if you want to arrange a certain number of tiles in a
                single row.
            sheet_height: height of the rectangular domain. You can set it to
                `inf` if you want to arrange a certain number of tiles in
                multiple rows (as many as needed) of fixed size.
            variant: some tiles allow variants for placement in a grid. This
                value can be used to select one such variant.
        Returns:
            A list of Tile instances, all compactly fitting inside the specified
            domain.
        """
        # Prepare working variables.
        tiles = []
        row = 0
        col = 0

        # Keep looping until all tiles have been placed.
        while len(tiles) < num_tiles:
            # Create a tile that should fit in the current grid coordinates.
            tile = cls(row, col, spacing, side_length, variant)

            if tile.within((0, sheet_width), (0, sheet_height), tolerance=1e-10):
                # If the tile does fit, "place it" and then go to the
                # second-next column. We advance by two due to the vertical
                # offsets that are present in odd columns when using some shapes
                # (such as tiles). We fill the current row by placing the
                # cells that are in even columns first and then those that are
                # in odd ones.
                tiles.append(tile)
                col += 2
            elif col == 0:
                # If the tile does not fit and it was to be placed in column 0,
                # it means that we finished the allotted space - since further
                # tiles would be placed at the same height or above.
                break
            elif col % 2 == 0:
                # If the tile does not fit and the current column index is not
                # 0, it means that we ran out of space horizontally.
                # Furthermore, if the column index is even, it means that we
                # still have to place tiles in odd columns. We therefore stay
                # in the same row, but starting now at column 1.
                col = 1
            else:
                # Finally, if none of the above criteria are met, it means that
                # we completely filled the current row and have to move to a new
                # one: set the column index back to zero and increment the row.
                col = 0
                row += 1

        # Exit by returning the list of tiles that could be fit in the domain.
        return tiles

    def __init__(self, row, col, spacing, side_length, variant):
        """Constructor for a tile.

        Args:
            row: vertical grid coordinate of the tile.
            col: horizontal grid coordinate of the tile.
            spacing: margin between adjacent tiles.
            side_length: size of a side of the tile.
            variant: some tiles allow variants for placement in a grid. This
                value can be used to select one such variant.
        """
        if variant not in self.get_variants():
            raise ValueError(f"Invalid variant {variant} for type {type(self).__name__}. Allwed values: {', '.join(map(str, self.get_variants()))}")

        # Store parameters.
        self.row = row
        self.col = col
        self.side_length = side_length
        self.spacing = spacing
        self.variant = variant

        # Calcualte the Cartesian coordinates of the center.
        self.x, self.y = self.calculate_center()

        # Create patches for visualization in matplotlib.
        self.patch, self.outer_patch = self.create_patches()
        self.outer_patch.set_facecolor("k")

    def calculate_center(self):
        """Calculate the coordinates of a tile in a grid.

        Returns:
            x, y: Cartesian coordinates of the center of the tile.
        """
        raise NotImplemented("This method is abstract and must be implemented "
                             "in sub-classes.")

    def create_patches(self):
        """Create patches to be added to a matplotlib figure.

        Returns:
            patch: a matplotlib.patches.Patch instance, representing the tile
                surface with no border.
            outer_patch: a matplotlib.patches.Patch instance, representing the
                border of a tile. This will be placed under its corresponding
                patch and therefore it does not need to have holes.
        """
        raise NotImplemented("This method is abstract and must be implemented "
                             "in sub-classes.")

    def make_copy(self):
        """Create a copy of this Tile by calling its constructor.

        This method is useful in case the same tile has to be placecd in
        multiple plots: matplotlib allows a patch to be placed in one axis only.

        Returns:
            tile: a copy of self, created by calling the constructor. This does
                not copy the visibility or the color of the tile.
        """
        return type(self)(self.row, self.col, self.spacing, self.side_length,
                          self.variant)

    def vertices(self, border=1.0):
        """List of vertices, as a NumPy array.

        Args:
            border: fraction of the border to include. Use 0 to get the vertices
                of the tile without considering the border at all. Use 1 if you
                want the vertices plus the outer patch. Note that the outer
                patches of adjacent tiles overlap (this is useful for visual
                purposes). If you want the vertices that are equidistant from
                the tile and its neighbour's centers as well, use 0.5.
        Returns:
            verts: a NumPy array with shape (n_vertices, 2).
        """
        raise NotImplemented("This method is abstract and must be implemented "
                             "in sub-classes.")

    def perimeter(self, border=0):
        """Calculate the perimeter of the tile.

        Returns:
            The perimeter of the tile, without considering the border.
        """
        verts = self.vertices(border=border)
        d = np.diff(np.vstack((verts, [verts[0]])), axis=0)
        return np.sum(np.sqrt(np.einsum("ij,ij->i", d, d)))

    def sample_perimeter(self, samples, first_corner, border=0):
        """Sample points on the perimeter of a tile.

        Args:
            samples: number of sample to generate.
            first_corner: the first sample in the sequence will be placed along
                the perimeter right after this corner (and proceeding in
                counter-clockwise order).
        Returns:
            A NumPy array with shape (samples, 2), containing the coordinates of
            the samples.
        """
        verts = np.roll(self.vertices(border=border), -first_corner, axis=0)
        verts = np.vstack((verts, [verts[0]]))
        d = np.diff(verts, axis=0)
        t_verts = np.concatenate(([0], np.cumsum(np.sqrt(np.einsum("ij,ij->i", d, d)))))
        t = np.linspace(0, self.perimeter(border=border), samples + 1)[:-1]
        t += t[1] / 2
        x = np.interp(t, t_verts, verts[:, 0])
        y = np.interp(t, t_verts, verts[:, 1])
        return np.stack((x,y)).T

    def within(self, x_range, y_range, include_border=True, tolerance=0.0):
        """Tells if this tile fits the given rectangular domain.

        Args:
            x_range: tuple in the form (xmin, xmax), defining the width of the
                rectangular domain.
            y_range: tuple in the form (ymin, ymax), defining height of the
                rectangular domain.
            include_border: if True, then the tile and its margin must both
                fully fit the domain. Otherwise, only the tile has to.
            tolerance: extend the x and y ranges by this margin, to compensate
                for possible numerical rounding errors.
        Returns:
            fits: True if the tile (and eventually its outer margin) fits
                within the given rectangular domain.
        """
        # Get a list of all vertices.
        verts = self.vertices(border=1.0 if include_border else 0.0)

        # Check if all vertices are within the bounds.
        return np.all(x_range[0] - tolerance <= verts[:,0]) and \
               np.all(verts[:,0] <= x_range[1] + tolerance) and \
               np.all(y_range[0] - tolerance <= verts[:,1]) and \
               np.all(verts[:,1] <= y_range[1] + tolerance)

    def contains(self, x, y):
        """Check if a point lies within this tile.

        Args:
            x, y: Cartesian coordinates of the point.
        Returns:
            contained: True if the point is within the tile. The border is not
                considered for this check.
        """
        raise NotImplemented("This method is abstract and must be implemented "
                             "in sub-classes.")

    def adjacent(self, other):
        """Check if this tile is adjacent to another.

        In the implementation, it is safe to assume that the other tile has the
        same class type as self. It is the user's job to avoid mixing tile
        types.

        Args:
            other: a Tile instance.
        Returns:
            True if the tiles are adjacent, False otherwise.
        """
        raise NotImplemented("This method is abstract and must be implemented "
                             "in sub-classes.")

    def add_to_axis(self, ax):
        """Add the tile and its border to a plot.

        Args:
            ax: matplotlib.axes.Axes instance where patches should be placed.
        """
        if self.spacing > 0:
            ax.add_patch(self.outer_patch)
        ax.add_patch(self.patch)

    def set_visible(self, visible):
        """Change visibility of this tile.

        This method allows to hide or show the patches associated to this
        tile. It is useful for animations with matplotlib.

        Args:
            visible: boolean specifying the visibility of the patches.
        """
        self.patch.set_visible(visible)
        self.outer_patch.set_visible(visible)

    def toggle_visible(self):
        """Change visibility of this tile.

        This method allows to hide or show the patches associated to this
        tile. It is useful for animations with matplotlib. The tile becomes
        hidden if it was visible, and viceversa.
        """
        self.set_visible(not self.patch.get_visible())

    def is_visible(self):
        """Return the visibility of the tile."""
        return self.patch.get_visible()


def unique_vertices(tiles):
    """Return the coordinates of unique vertices in a set of tiles.

    Given a set of tiles, loop through all their vertices and create a list
    of all vertices, with no repetitions.

    Args:
        tiles: a list of Tile instances.
    Returns:
        A NumPy array with shape (n_vertices, 2), containing the coordinates of
        all unique vertices in the group of tiles.
    """
    vertices = tiles[0].vertices(border=0.5)
    for tile in tiles[1:]:
        for v in tile.vertices(border=0.5):
            vector_distances = vertices - v
            if not np.isclose(np.einsum("ij,ij->i", vector_distances, vector_distances).min(), 0):
                vertices = np.vstack((vertices, v))
    return vertices


def get_bounding_box(tiles):
    """Calculate the coordinates of a rectangle containing all given tiles.

    Args:
        tiles: list of Tile instances.
    Returns:
        (xmin, ymin), (xmax, ymax): coordinates of the bottom-left and top-right
            corners of the bounding box.
    """
    vertices = np.vstack([t.vertices() for t in tiles])
    return vertices.min(axis=0), vertices.max(axis=0)


def get_bounding_box_size(tiles):
    """Calculate the sizes of a rectangle containing all given tiles.

    Args:
        tiles: list of Tile instances.
    Returns:
        width, height: dimensions of the bounding box.
    """
    (xmin, ymin), (xmax, ymax) = get_bounding_box(tiles)
    return (xmax - xmin), (ymax - ymin)


def get_bounding_box_area(tiles):
    """Calculate the area of a rectangle containing all given tiles.

    Args:
        tiles: list of Tile instances.
    Returns:
        area: surface area of the bounding box.
    """
    width, height = get_bounding_box_size(tiles)
    return width * height
