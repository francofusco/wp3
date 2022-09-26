import numpy as np
from matplotlib.patches import Polygon, RegularPolygon
from .tile import Tile


class Triangle(Tile):
    @classmethod
    def get_variants(cls):
        # There are two variants:
        # - Triangles from variant 0 have a horizontal edge either on the bottom
        #   or on the top.
        # - Triangles from variant 1 have a vertical edge either on the left or
        #   on the right.
        return [0, 1]

    def calculate_center(self):
        # The code below is designed for triangles of variant 0. However, we
        # can swap the grid coordinates, do the calculations, and swap the
        # result in order to deal with the other variant as well.
        row, col = (self.col, self.row) if self.variant else (self.row, self.col)

        # Coordinates of the center, so that the pair (0,0) is mapped into the
        # origin of the cartesian plane.
        x = col * (self.side_length + np.sqrt(3) * self.spacing) / 2
        d = self.spacing + self.side_length / np.sqrt(3)
        y = (3 * row + (row + col) % 2) * d / 2

        # Shift the coordinates so that the triangle with grid coordinates
        # (0,0) touches the x and y axes. This is useful for filling rectangles,
        # which is one of the goals here.
        x += self.side_length / 2 + self.spacing * 2 / np.sqrt(3)
        y += self.side_length * np.sqrt(3) / 6 + self.spacing

        # Swap the resulting coordinates if the layout uses the variant 1.
        if self.variant:
            x, y = y, x

        # Return the result as a tuple.
        return x, y

    def create_patches(self):
        # Create the inner patch, which is just a regular triangle. The angular
        # offset determines the orientation of the first vertex. It depends on
        # the variant of the triangle but also on its grid coordinates (some
        # triangles are rotated by 180 degrees).
        offset = self.variant * np.pi / 6 + ((self.col + self.row) % 2) * np.pi
        inner = RegularPolygon((self.x, self.y), 3, radius=self.side_length/np.sqrt(3), orientation=offset, linewidth=0)

        # To define the outer patch, we could just create a larger triangle.
        # However, there would be some "spikes" that while harmless are visually
        # unpleasant (at least in my opinion). We can fix this by "trimminng"
        # the corners of the outer triangle by the appropriate amount. The code
        # below does that via the following actions:
        # - Calculate the local coordinates of the trimmed corner, (x,y) and
        #   (x,-y). They are local in the sense that we assume the first corner
        #   has coordinates (r,0).
        # - Rotate the two points from the local to the global coordinate
        #   system. This corresponds to rotating the point of the same amount as
        #   the triangle itself.
        # - Obtain the remaining points using a clockwise rotation of 120
        #   degrees and then one of 120 degrees counterclockwise.
        # - Finally, create a Polygon from the sequence of these six points.
        x = self.side_length / np.sqrt(3) + 1.5 * self.spacing
        y = self.spacing * np.sqrt(3) / 6
        alpha = - (1-self.variant) * np.pi / 6 + ((self.col + self.row) % 2) * np.pi
        Ra = np.array([[np.cos(alpha), -np.sin(alpha)], [np.sin(alpha), np.cos(alpha)]])
        v1 = Ra.dot(np.array([x, -y]))
        v2 = Ra.dot(np.array([x,  y]))
        R = np.array([[np.cos(2*np.pi/3), -np.sin(2*np.pi/3)], [np.sin(2*np.pi/3), np.cos(2*np.pi/3)]])
        v3 = R.dot(v1)
        v4 = R.dot(v2)
        v5 = R.T.dot(v1)
        v6 = R.T.dot(v2)
        outer = Polygon(np.stack((v1, v2, v3, v4, v5, v6)) + np.array([self.x, self.y]), linewidth=0)

        # Return the inner and outer patches.
        return inner, outer

    def vertices(self, border=1.0):
        # Calculate the radius (distance between the center and the vertices).
        radius = self.side_length / np.sqrt(3) + border * 2 * self.spacing

        # Since this is a regular polygon, vertices are found at uniformely
        # spaced angular coordinates.
        angles = 2*np.pi/3 * np.arange(3) - (1-self.variant) * np.pi / 6 + ((self.col + self.row) % 2) * np.pi

        # Convert polar coordinates to Cartesian ones, and shift by the center
        # of the triangle.
        return np.stack((self.x + radius * np.cos(angles), self.y + radius * np.sin(angles))).T

    @staticmethod
    def _signed_area(x1, y1, x2, y2, x3, y3):
        """Calculate twice the signed area of a triangle.

        Args:
            x1, y1: coordinates of the first vertex.
            x2, y2: coordinates of the seccond vertex.
            x3, y3: coordinates of the third vertex.
        Returns:
            Two times the signed area of the triangle. The value is negative if
            the vertices are in counterclockwise order.
        """
        return (x1 - x3) * (y2 - y3) - (x2 - x3) * (y1 - y3)

    def contains(self, x, y):
        # To see if a point p is contained within a triangle T of vertices v1,
        # v2 and v3, we can form the three triangles T1=(p,v1,v2), T2=(p,v2,v3)
        # and T3=(p,v3,v1). It can be shown that p is within T if all triangles
        # Ti have the same ordering. To get the ordering, we just calculate
        # their signed areas using the cross-product.
        verts = self.vertices(border=0)
        areas = np.array([
            Triangle._signed_area(x, y, verts[0,0], verts[0,1], verts[1,0], verts[1,1]),
            Triangle._signed_area(x, y, verts[1,0], verts[1,1], verts[2,0], verts[2,1]),
            Triangle._signed_area(x, y, verts[2,0], verts[2,1], verts[0,0], verts[0,1])
        ])
        return np.all(areas>=0) or np.all(areas<=0)

    def adjacent(self, other):
        # Assuming that self and other have been generated using the same
        # geometric parameters (side length, spacing and variant), we can do a
        # lazy check: just verify that the distance between their centers is the
        # one expected between two neighbours.
        distance = np.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)
        return np.allclose(distance, self.side_length + self.spacing)
