import unittest

from app.packing import (
    Package,
    UnpackablePackageError,
    pack_packages,
    plan_packages,
)


def package(
    package_id: int,
    width: float = 10,
    height: float = 10,
    length: float = 10,
    weight: float = 5,
    fragile: bool = False,
) -> Package:
    return Package(package_id, width, height, length, weight, fragile)


class PackingTests(unittest.TestCase):
    def test_empty_input_needs_no_boxes(self) -> None:
        self.assertEqual(pack_packages([]), [])

    def test_example_packages_share_a_box(self) -> None:
        packages = [package(123, 10, 10, 10), package(125, 5, 5, 10, 10)]
        boxes = pack_packages(packages)
        self.assertEqual(len(boxes), 1)
        self.assertEqual([item.id for item in boxes[0].packages], [123, 125])

    def test_package_can_be_rotated(self) -> None:
        self.assertEqual(len(pack_packages([package(1, 400, 200, 300)])), 1)

    def test_weight_capacity_requires_another_box(self) -> None:
        packages = [package(index, weight=2000) for index in range(4)]
        self.assertEqual(len(pack_packages(packages)), 4)

    def test_every_package_is_assigned_exactly_once(self) -> None:
        packages = [package(index, weight=2000) for index in range(1, 5)]
        boxes = pack_packages(packages)
        assigned_ids = [item.id for box in boxes for item in box.packages]
        self.assertEqual(sorted(assigned_ids), [1, 2, 3, 4])
        self.assertEqual(len(assigned_ids), len(set(assigned_ids)))

    def test_selects_smallest_box_type_that_fits_package_group(self) -> None:
        boxes = pack_packages([package(1, 100, 100, 100, 1000)])
        self.assertEqual(boxes[0].box_type.name, "B")

    def test_uses_box_a_when_box_b_cannot_fit(self) -> None:
        boxes = pack_packages([package(1, 150, 150, 150)])
        self.assertEqual(boxes[0].box_type.name, "A")

    def test_keeps_box_c_for_package_that_only_fits_box_c(self) -> None:
        boxes = pack_packages([package(1, 300, 400, 300, 3000)])
        self.assertEqual(boxes[0].box_type.name, "C")

    def test_fragile_package_is_routed_to_special_handling(self) -> None:
        plan = plan_packages([package(1, fragile=True)])
        self.assertEqual(plan.boxes, ())
        self.assertEqual(plan.special_items[0].package.id, 1)
        self.assertEqual(plan.special_items[0].reasons, ("fragile",))

    def test_oversized_package_is_routed_to_special_handling(self) -> None:
        plan = plan_packages([package(7, 401, 1, 1)])
        self.assertEqual(plan.boxes, ())
        self.assertEqual(plan.special_items[0].reasons, ("oversized",))

    def test_overweight_package_is_routed_to_special_handling(self) -> None:
        plan = plan_packages([package(8, weight=3001)])
        self.assertEqual(plan.boxes, ())
        self.assertEqual(plan.special_items[0].reasons, ("overweight",))

    def test_packable_items_remain_in_plan_with_special_items(self) -> None:
        plan = plan_packages(
            [package(1), package(2, 401, 1, 1), package(3, fragile=True)]
        )
        self.assertEqual(
            [item.id for box in plan.boxes for item in box.packages],
            [1],
        )
        self.assertEqual(
            [item.package.id for item in plan.special_items],
            [2, 3],
        )

    def test_package_that_exceeds_box_dimensions_is_rejected(self) -> None:
        with self.assertRaises(UnpackablePackageError):
            pack_packages([package(7, 401, 1, 1)])

    def test_package_that_exceeds_box_weight_is_rejected(self) -> None:
        with self.assertRaises(UnpackablePackageError):
            pack_packages([package(8, weight=3001)])


if __name__ == "__main__":
    unittest.main()
