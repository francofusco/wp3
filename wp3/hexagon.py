import numpy as np
from matplotlib.patches import RegularPolygon
from .tile import Tile


class Hexagon(Tile):
    @classmethod
    def get_variants(cls):
        # There are two variants:
        # - Hexagons from variant 0 have horizontal edges on their top and
        #   bottom, while they have vertices on their left and right.
        # - Hexagons from variant 1 have vertical edges on their left and right,
        #   while they have vertices on their top and bottom.
        return [0, 1]

    def calculate_center(self):
        # The code below is designed for hexagons of variant 0. However, we
        # can swap the grid coordinates, do the calculations, and swap the
        # result in order to deal with the other variant as well.
        row, col = (self.col, self.row) if self.variant else (self.row, self.col)

        # Coordinates of the center, so that the pair (0,0) is mapped into the
        # origin of the catesian plane.
        x = col * (3 * self.side_length + np.sqrt(3) * self.spacing) / 2
        y = (row if col%2==0 else (row+0.5)) * (np.sqrt(3) * self.side_length + self.spacing)

        # Shift the coordinates so that the hexagon with grid coordinates (0,0)
        # touches the x and y axes. This is useful for filling rectangles, which
        # is one of the goals here.
        x += self.side_length + self.spacing * 2 / np.sqrt(3)
        y += self.side_length * np.sqrt(3) / 2 + self.spacing

        # Swap the resulting coordinates if the layout uses the variant 1.
        if self.variant:
            x, y = y, x

        # Return the result as a tuple.
        return x, y

    def create_patches(self):
        # Return two hexagons with different sizes.
        inner = RegularPolygon((self.x, self.y), 6, radius=self.side_length, orientation=(1-self.variant) * np.pi/6)
        outer = RegularPolygon((self.x, self.y), 6, radius=self.side_length+self.spacing*2/np.sqrt(3), orientation=(1-self.variant) * np.pi/6)
        return inner, outer

    def vertices(self, border=1.0):
        # Calculate the radius (distance between the center and the vertices).
        radius = self.side_length + border * self.spacing * 2 / np.sqrt(3)

        # Since this is a regular polygon, vertices are found at uniformely
        # spaced angular coordinates.
        angles = np.pi/3 * np.arange(6)
        if self.variant:
            angles += np.pi/6

        # Convert polar coordinates to Cartesian ones, and shift by the center
        # of the hexagon.
        return np.stack((self.x + radius * np.cos(angles), self.y + radius * np.sin(angles))).T

    def contains(self, x, y):
        # Distance between the point and the center of the hexagon. The absolute
        # value is taken since the hexagon is symmetric with respect to the x
        # and y axis: if a point fits in the hexagon, so will its
        # reflection in the first quadrant. We check only if this reflection is
        # inside the hexagon since it requires just two inequalities.
        dx = np.abs(self.x - x)
        dy = np.abs(self.y - y)

        # Swap the coordinates if the hexagons are stacked horizontally.
        if self.variant:
            dx, dy = dy, dx

        # Check if the reflection is inside the hexagon. This requires just two
        # inequalities.
        return dy <= self.side_length * np.sqrt(3) / 2 and np.sqrt(3) * dx + dy <= np.sqrt(3) * self.side_length

    def adjacent(self, other):
        # Assuming that self and other have been generated using the same
        # geometric parameters (side length, spacing and variant), we can do a
        # lazy check: just verify that the distance between their centers is the
        # one expected between two neighbours.
        distance = np.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)
        return np.allclose(distance, np.sqrt(3) * self.side_length + self.spacing)
