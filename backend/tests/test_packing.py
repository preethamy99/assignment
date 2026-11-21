import unittest

from app.packing import Package, UnpackablePackageError, pack_packages


def package(
    package_id: int,
    width: float = 10,
    height: float = 10,
    length: float = 10,
    weight: float = 5,
) -> Package:
    return Package(package_id, width, height, length, weight)


class PackingTests(unittest.TestCase):
    def test_empty_input_needs_no_boxes(self) -> None:
        self.assertEqual(pack_packages([]), 0)

    def test_example_packages_share_a_box(self) -> None:
        packages = [package(123, 10, 10, 10), package(125, 5, 5, 10, 10)]
        self.assertEqual(pack_packages(packages), 1)

    def test_package_can_be_rotated(self) -> None:
        self.assertEqual(pack_packages([package(1, 400, 200, 300)]), 1)

    def test_weight_capacity_requires_another_box(self) -> None:
        packages = [package(index, weight=2000) for index in range(4)]
        self.assertEqual(pack_packages(packages), 4)

    def test_package_that_exceeds_box_dimensions_is_rejected(self) -> None:
        with self.assertRaises(UnpackablePackageError):
            pack_packages([package(7, 401, 1, 1)])

    def test_package_that_exceeds_box_weight_is_rejected(self) -> None:
        with self.assertRaises(UnpackablePackageError):
            pack_packages([package(8, weight=3001)])


if __name__ == "__main__":
    unittest.main()
