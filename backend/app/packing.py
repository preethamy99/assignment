from __future__ import annotations

from dataclasses import dataclass, field
from itertools import permutations
from typing import Literal


@dataclass(frozen=True)
class BoxType:
    name: Literal["A", "B", "C"]
    width: float
    height: float
    length: float
    max_weight: float

    @property
    def dimensions(self) -> tuple[float, float, float]:
        return (self.width, self.height, self.length)

    @property
    def volume(self) -> float:
        return self.width * self.height * self.length


BOX_TYPES = (
    BoxType("A", 150, 150, 150, 1000),
    BoxType("B", 100, 200, 100, 1000),
    BoxType("C", 300, 400, 300, 3000),
)

# Box C is at least as large and has at least as much capacity as every other
# available box, so using it cannot increase the box count.
PACKING_BOX = max(BOX_TYPES, key=lambda box: box.volume)


@dataclass(frozen=True)
class Package:
    id: int
    width: float
    height: float
    length: float
    weight: float

    @property
    def dimensions(self) -> tuple[float, float, float]:
        return (self.width, self.height, self.length)

    @property
    def volume(self) -> float:
        return self.width * self.height * self.length


@dataclass(frozen=True)
class PackedBox:
    box_number: int
    box_type: BoxType
    packages: tuple[Package, ...]

    @property
    def total_weight(self) -> float:
        return sum(package.weight for package in self.packages)


class UnpackablePackageError(ValueError):
    def __init__(self, package_id: int) -> None:
        self.package_id = package_id
        super().__init__(f"Package {package_id} does not fit in any available box.")


@dataclass
class _OpenBox:
    box_type: BoxType
    remaining_weight: float
    free_spaces: list[tuple[float, float, float]] = field(default_factory=list)
    packages: list[Package] = field(default_factory=list)

    @classmethod
    def create(cls, box_type: BoxType) -> _OpenBox:
        return cls(
            box_type=box_type,
            remaining_weight=box_type.max_weight,
            free_spaces=[box_type.dimensions],
        )


@dataclass(frozen=True)
class _Placement:
    space_index: int
    dimensions: tuple[float, float, float]
    score: tuple[float, float, float]


def _find_placement(
    package: Package, spaces: list[tuple[float, float, float]]
) -> _Placement | None:
    candidates: list[_Placement] = []
    orientations = sorted(set(permutations(package.dimensions)))

    for space_index, space in enumerate(spaces):
        for oriented in orientations:
            if all(item_dim <= space_dim for item_dim, space_dim in zip(oriented, space)):
                leftover = tuple(
                    sorted(space_dim - item_dim for item_dim, space_dim in zip(oriented, space))
                )
                candidates.append(_Placement(space_index, oriented, leftover))

    return min(candidates, key=lambda candidate: candidate.score) if candidates else None


def _place(box: _OpenBox, package: Package, placement: _Placement) -> None:
    space_width, space_height, space_length = box.free_spaces.pop(placement.space_index)
    item_width, item_height, item_length = placement.dimensions

    # These three non-overlapping regions partition the unused portion of the
    # selected free space after placing the package at its lower corner.
    remaining_spaces = (
        (space_width - item_width, space_height, space_length),
        (item_width, space_height - item_height, space_length),
        (item_width, item_height, space_length - item_length),
    )
    box.free_spaces.extend(
        space for space in remaining_spaces if all(dimension > 0 for dimension in space)
    )
    box.remaining_weight -= package.weight
    box.packages.append(package)


def _fits_in_box_type(packages: list[Package], box_type: BoxType) -> bool:
    if sum(package.weight for package in packages) > box_type.max_weight:
        return False

    box = _OpenBox.create(box_type)
    ordered_packages = sorted(
        packages,
        key=lambda package: (-package.volume, -package.weight, package.id),
    )
    for package in ordered_packages:
        placement = _find_placement(package, box.free_spaces)
        if placement is None:
            return False
        _place(box, package, placement)
    return True


def _smallest_fitting_box_type(packages: list[Package]) -> BoxType:
    for box_type in sorted(BOX_TYPES, key=lambda candidate: candidate.volume):
        if box_type.name == PACKING_BOX.name:
            continue
        if _fits_in_box_type(packages, box_type):
            return box_type
    return PACKING_BOX


def pack_packages(packages: list[Package]) -> list[PackedBox]:
    """Pack into the fewest heuristic bins, then downsize bins when possible."""
    open_boxes: list[_OpenBox] = []
    ordered_packages = sorted(
        packages,
        key=lambda package: (-package.volume, -package.weight, package.id),
    )

    for package in ordered_packages:
        if package.weight > PACKING_BOX.max_weight or _find_placement(
            package, [PACKING_BOX.dimensions]
        ) is None:
            raise UnpackablePackageError(package.id)

        candidates: list[tuple[tuple[float, float, float], int, _Placement]] = []
        for box_index, box in enumerate(open_boxes):
            if package.weight <= box.remaining_weight:
                placement = _find_placement(package, box.free_spaces)
                if placement is not None:
                    candidates.append((placement.score, box_index, placement))

        if candidates:
            _, box_index, placement = min(candidates, key=lambda candidate: candidate[:2])
            _place(open_boxes[box_index], package, placement)
        else:
            box = _OpenBox.create(PACKING_BOX)
            placement = _find_placement(package, box.free_spaces)
            if placement is None:
                raise UnpackablePackageError(package.id)
            _place(box, package, placement)
            open_boxes.append(box)

    packed_boxes = []
    for index, box in enumerate(open_boxes, start=1):
        packages_in_box = tuple(sorted(box.packages, key=lambda package: package.id))
        packed_boxes.append(
            PackedBox(
                box_number=index,
                box_type=_smallest_fitting_box_type(list(packages_in_box)),
                packages=packages_in_box,
            )
        )
    return packed_boxes
