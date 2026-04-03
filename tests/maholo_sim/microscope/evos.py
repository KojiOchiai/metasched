from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


def make_image(times: int, array: np.ndarray):
    size = array.shape

    def draw(image, row, col):
        r = row * times
        c = col * times
        image[r + 1 : r + times - 1, c + 1 : c + times - 1, :] = 1

    image = np.ones([s * times for s in size] + [3]) * 0.01
    for r in range(size[0]):
        for c in range(size[1]):
            if array[r, c] == 1:
                draw(image, r, c)
    return (image * 255).astype(np.uint8)


class DummyCellImage:
    def __init__(self, image_size: int, cell_size: int):
        self.image_size = image_size
        self.cell_size = cell_size
        self.unit = int(np.floor(self.image_size / self.cell_size))

    def draw(self, density: float, ring_edge: int) -> np.ndarray:
        array = np.zeros([self.unit, self.unit])
        index_size = self.unit * self.unit
        index = np.random.choice(
            range(index_size), int(density * index_size), replace=False
        )
        cell_index = np.unravel_index(index, array.shape)
        array[cell_index[0], cell_index[1]] = 1
        image = make_image(int(self.image_size / self.unit), array)

        image_center = [int(c / 2) for c in image.shape[:2]]
        mask = np.zeros_like(image)
        mask = cv2.circle(
            mask, image_center, image_center[0] - 5 * ring_edge, [100, 100, 100], -1
        )
        ring = np.zeros_like(image)
        ring = cv2.circle(
            ring, image_center, image_center[0] - ring_edge, [200, 200, 200], ring_edge
        )
        cell = cv2.bitwise_and(image, mask)
        return cv2.bitwise_or(cell, ring) + 2


def get_image(density: float, ring_edge: int = 9) -> np.ndarray:
    assert 0 <= density and density <= 1, density
    dummy_image = DummyCellImage(10000, 10)
    return dummy_image.draw(density, ring_edge)


def get_filepath(
    time: datetime, well_row: str, well_col: int, path: Path = Path("evos_save")
) -> Path:
    image_save_path = path
    timestamp = datetime.strftime(time, format="%Y-%m-%d-%H-%M-%S")
    dst_dir = image_save_path / f"scan.{timestamp}"
    dst_path = dst_dir / f"scan_Plate_TR_p00_0_{well_row}{well_col:02d}f00d3.TIFF"
    return dst_path


if __name__ == "__main__":
    # make image
    image = get_image(density=0.1)
    filepath = get_filepath(datetime.now(), "A", 1)
    filepath.parent.mkdir(exist_ok=True)
    cv2.imwrite(str(filepath), image)
