import numpy as np
from matplotlib.patches import RegularPolygon
from .tile import Tile


class Rectangle(Tile):
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
