import numpy as np
from matplotlib.patches import RegularPolygon
from .tile import Tile


class Octagon(Tile):
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
    def get_variants(cls):
        return [0, 1]

    def calculate_center(self):
        if self.variant == 0:
            # Center coordinates can be calculated from those of the
            # sourrounding rectangle.
            tile_size = (1 + np.sqrt(2)) * self.side_length
            x = (
                (tile_size + self.spacing) * self.col
                + self.spacing
                + tile_size / 2
            )
            y = (
                (tile_size + self.spacing) * self.row
                + self.spacing
                + tile_size / 2
            )
        else:
            dist = (
                (1 + np.sqrt(2)) * self.side_length + self.spacing
            ) / np.sqrt(2)
            x = self.col * dist
            y = self.row * 2 * dist
            if self.col % 2 == 0:
                y += dist

        # Return the result as a tuple.
        return x, y

    def create_patches(self):
        # Return two octagons with different sizes.
        r = self.side_length * np.sqrt(1 + 1 / np.sqrt(2))
        R = r * (1 + 2 * self.spacing / ((1 + np.sqrt(2)) * self.side_length))
        inner = RegularPolygon(
            (self.x, self.y), 8, radius=r, orientation=np.pi / 8
        )
        outer = RegularPolygon(
            (self.x, self.y), 8, radius=R, orientation=np.pi / 8
        )
        return inner, outer

    def vertices(self, border=1.0):
        # Return the corners of the octagon in counter-clockwise order.
        r = self.side_length * np.sqrt(1 + 1 / np.sqrt(2))
        dr = r * 2 * self.spacing / ((1 + np.sqrt(2)) * self.side_length)
        radius = r + border * dr
        angles = np.pi * (np.arange(8) / 4 + 1 / 8)
        return np.stack(
            (self.x + radius * np.cos(angles), self.y + radius * np.sin(angles))
        ).T

    def contains(self, x, y):
        # Distance between the point and the center of the octagon, normalized
        # by the side length. The absolute value is taken since the octagon is
        # symmetric with respect to the x and y axis: if a point fits in the
        # octagon, so will its reflection in the first quadrant. We check only
        # if this reflection is inside the octagon since it requires just three
        # inequalities.
        dx = np.abs(x - self.x) / self.side_length
        dy = np.abs(y - self.y) / self.side_length

        # Half of the size of the octagon, normalized by the side length.
        d = (1 + np.sqrt(2)) / 2

        # Check if the reflection of the point in the first quadrant is within
        # the octagon, which requires only three inequalities.
        return dx <= d and dy <= d and dx + dy <= (1 + 1 / np.sqrt(2))

    def adjacent(self, other):
        if self.variant == 0:
            return (
                np.abs(self.row - other.row) + np.abs(self.col - other.col) == 1
            )
        else:
            distance = np.sqrt(
                (self.x - other.x) ** 2 + (self.y - other.y) ** 2
            )
            return np.allclose(
                distance, (1 + np.sqrt(2)) * self.side_length + self.spacing
            )
