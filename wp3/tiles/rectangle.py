import numpy as np
from matplotlib.patches import RegularPolygon
from wp3.freecad import wp3_export_default
from wp3.tile import Tile, count_cad_parts_in_regular_tiling


class Rectangle(Tile):
    @classmethod
    def configure(cls, side_length=None):
        if side_length is None:
            raise ValueError(
                "The mandatory parameter 'side_length' was not specified."
            )
        cls.side_length = side_length

    @classmethod
    def configurable_parameters(cls):
        return {"side_length": float}

    @classmethod
    def count_cad_parts(cls, tiles):
        return count_cad_parts_in_regular_tiling(tiles, 4)

    def calculate_center(self):
        # Calculate the coordinates. This is straightforward since squares stack
        # naturally inside a grid!
        x = (
            (self.side_length + self.spacing) * self.col
            + self.spacing
            + self.side_length / 2
        )
        y = (
            (self.side_length + self.spacing) * self.row
            + self.spacing
            + self.side_length / 2
        )

        # Return the result as a tuple.
        return x, y

    def create_patches(self):
        # Return two squares with different sizes.
        inner = RegularPolygon(
            (self.x, self.y),
            4,
            radius=self.side_length / np.sqrt(2),
            orientation=np.pi / 4,
        )
        outer = RegularPolygon(
            (self.x, self.y),
            4,
            radius=(self.side_length + 2 * self.spacing) / np.sqrt(2),
            orientation=np.pi / 4,
        )
        return inner, outer

    def vertices(self, border=1.0):
        # Return the corners of the rectangle, in counterclockwise order
        # starting from the top right one.
        d = self.side_length / 2 + border * self.spacing
        return np.array(
            [
                [self.x + d, self.y + d],
                [self.x - d, self.y + d],
                [self.x - d, self.y - d],
                [self.x + d, self.y - d],
            ]
        )

    def contains(self, x, y):
        # Checking if a point is within a square is quite simple!
        return (
            2 * np.abs(x - self.x) <= self.side_length
            and 2 * np.abs(y - self.y) <= self.side_length
        )

    def adjacent(self, other):
        # To check if two squares are adjacent, we can simply verify it their
        # manhattan distance in the grid is equal to 1.
        return np.abs(self.row - other.row) + np.abs(self.col - other.col) == 1

    def export_stl(self, path, **params):
        return wp3_export_default(
            path,
            side_length=self.side_length * 1e3,
            spacing=self.spacing * 1e3,
            junction_angle=45,
            **params
        )
