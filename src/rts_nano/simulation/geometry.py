"""Small deterministic geometry primitives used by the simulation."""

from __future__ import annotations

from dataclasses import dataclass

type Point = tuple[float, float]
type ClippedLine = tuple[Point, Point]


@dataclass(frozen=True, slots=True)
class Rect:
    """Axis-aligned rectangle with the subset of operations required by terrain."""

    x: int
    y: int
    width: int
    height: int

    @property
    def left(self) -> int:
        """Return the inclusive left edge."""
        return self.x

    @property
    def right(self) -> int:
        """Return the exclusive right edge."""
        return self.x + self.width

    @property
    def top(self) -> int:
        """Return the inclusive top edge."""
        return self.y

    @property
    def bottom(self) -> int:
        """Return the exclusive bottom edge."""
        return self.y + self.height

    def __len__(self) -> int:
        """Return the four conventional rectangle components."""
        return 4

    def __getitem__(self, index: int) -> int:
        """Expose the conventional x/y/width/height rectangle sequence."""
        return (self.x, self.y, self.width, self.height)[index]

    def collidepoint(self, point: Point | float, y: float | None = None) -> bool:
        """Return whether a point is inside, excluding right and bottom edges."""
        px, py = point if isinstance(point, tuple) else (point, y)
        if py is None:
            raise TypeError("y coordinate is required")
        return self.left <= px < self.right and self.top <= py < self.bottom

    def inflate(self, width: float, height: float) -> Rect:
        """Return a rectangle grown equally around its center."""
        delta_width = int(width)
        delta_height = int(height)
        return Rect(
            self.x - delta_width // 2,
            self.y - delta_height // 2,
            self.width + delta_width,
            self.height + delta_height,
        )

    def move(self, x: float, y: float) -> Rect:
        """Return a translated rectangle."""
        return Rect(self.x + int(x), self.y + int(y), self.width, self.height)

    def clipline(self, start: Point, end: Point) -> ClippedLine | None:
        """Clip a line with integer Cohen-Sutherland semantics like SDL Rect."""
        x0, y0 = int(start[0]), int(start[1])
        x1, y1 = int(end[0]), int(end[1])
        right = self.right - 1
        bottom = self.bottom - 1

        def outcode(x: int, y: int) -> int:
            code = 0
            if y < self.top:
                code |= 1
            elif y > bottom:
                code |= 2
            if x < self.left:
                code |= 4
            elif x > right:
                code |= 8
            return code

        while True:
            code0 = outcode(x0, y0)
            code1 = outcode(x1, y1)
            if not (code0 | code1):
                return ((float(x0), float(y0)), (float(x1), float(y1)))
            if code0 & code1:
                return None

            code = code0 or code1
            dx = x1 - x0
            dy = y1 - y0
            if code & 1:
                clipped_x = x0 + int(dx * (self.top - y0) / dy)
                clipped_y = self.top
            elif code & 2:
                clipped_x = x0 + int(dx * (bottom - y0) / dy)
                clipped_y = bottom
            elif code & 4:
                clipped_y = y0 + int(dy * (self.left - x0) / dx)
                clipped_x = self.left
            else:
                clipped_y = y0 + int(dy * (right - x0) / dx)
                clipped_x = right

            if code == code0:
                x0, y0 = clipped_x, clipped_y
            else:
                x1, y1 = clipped_x, clipped_y
