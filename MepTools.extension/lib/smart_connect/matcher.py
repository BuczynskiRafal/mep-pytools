"""Pure, testable connector-matching logic. No Revit dependency."""

import math
from dataclasses import dataclass
from enum import Enum


class ConnectorDomain(Enum):
    UNDEFINED = 0
    PIPING = 1
    DUCTING = 2
    ELECTRICAL = 3
    CABLE_TRAY = 4


@dataclass(frozen=True)
class ConnectorInfo:
    """Description of a single connector, with no Revit types.

    source_index lets the Revit layer recover the live Connector afterwards.
    size is the diameter for round connectors, or 0 when irrelevant/unknown.
    """

    source_index: int
    x: float
    y: float
    z: float
    domain: ConnectorDomain
    size: float

    def distance_to(self, other):
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def compatible_with(self, other, size_tolerance):
        if self.domain != other.domain:
            return False
        if (self.domain == ConnectorDomain.PIPING
                and self.size > 0 and other.size > 0
                and abs(self.size - other.size) > size_tolerance):
            return False
        return True


def find_best_pair(set_a, set_b, size_tolerance=1e-9):
    """Return the spatially closest, compatible pair (a, b), or None.

    a is taken from set_a and b from set_b.
    """
    best = None
    min_distance = math.inf

    for a in set_a:
        for b in set_b:
            if not a.compatible_with(b, size_tolerance):
                continue
            distance = a.distance_to(b)
            if distance < min_distance:
                min_distance = distance
                best = (a, b)
    return best
