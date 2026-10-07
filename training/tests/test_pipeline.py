from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import torch
from PIL import Image

from training.export_weights import export_checkpoint
from training.model import TinyFaceDetector, count_macs
from training.train import detection_loss
from training.widerface_dataset import WiderFaceGridDataset


class TrainingPipelineTest(unittest.TestCase):
    def test_widerface_zero_face_placeholder(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary_directory:
            root = Path(temporary_directory)
            image_root = root / "images"
            image_root.mkdir()
            Image.new("RGB", (160, 120)).save(image_root / "empty.jpg")
            Image.new("RGB", (160, 120)).save(image_root / "face.jpg")
            annotation = root / "annotations.txt"
            annotation.write_text(
                "empty.jpg\n0\n0 0 0 0 0 0 0 0 0 0\n"
                "face.jpg\n1\n40 30 40 60 0 0 0 0 0 0\n",
                encoding="utf-8",
            )

            dataset = WiderFaceGridDataset(image_root, annotation)
            self.assertEqual(len(dataset), 2)
            self.assertEqual(float(dataset[0][1][0].sum()), 0.0)
            self.assertEqual(float(dataset[1][1][0].sum()), 1.0)

    def test_model_shape_and_export_counts(self) -> None:
        torch.manual_seed(7021)
        model = TinyFaceDetector().eval()
        output = model(torch.zeros((2, 1, 120, 160), dtype=torch.float32))
        self.assertEqual(tuple(output.shape), (2, 5, 15, 20))
        self.assertEqual(count_macs(), 2_800_800)

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary_directory:
            root = Path(temporary_directory)
            checkpoint_path = root / "untrained_test_only.pt"
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "trained_epochs": 0,
                },
                checkpoint_path,
            )
            export_checkpoint(checkpoint_path, root / "rom")
            manifest = json.loads((root / "rom" / "manifest.json").read_text(encoding="utf-8"))
            counts = [layer["weight_count"] for layer in manifest["layers"]]
            self.assertEqual(counts, [72, 1152, 3456, 120])
            self.assertEqual(sum(counts), 4800)
            for layer in manifest["layers"]:
                mem_lines = (root / "rom" / layer["mem_file"]).read_text().splitlines()
                self.assertEqual(len(mem_lines), layer["weight_count"])

    def test_widerface_target_and_training_step(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary_directory:
            root = Path(temporary_directory)
            image_root = root / "images"
            image_root.mkdir()
            Image.new("RGB", (320, 240), (64, 96, 128)).save(image_root / "sample.jpg")
            annotation = root / "annotations.txt"
            annotation.write_text(
                "sample.jpg\n1\n80 60 80 120 0 0 0 0 0 0\n", encoding="utf-8"
            )
            dataset = WiderFaceGridDataset(image_root, annotation)
            image, target = dataset[0]
            self.assertEqual(tuple(image.shape), (1, 120, 160))
            self.assertEqual(float(target[0].sum()), 1.0)
            self.assertAlmostEqual(float(target[1, 7, 7]), 0.5)
            self.assertAlmostEqual(float(target[2, 7, 7]), 0.5)
            self.assertAlmostEqual(float(target[3, 7, 7]), 0.25)
            self.assertAlmostEqual(float(target[4, 7, 7]), 0.5)

            model = TinyFaceDetector()
            optimizer = torch.optim.SGD(model.parameters(), lr=1e-3)
            prediction = model(image.unsqueeze(0))
            total, objectness, box = detection_loss(prediction, target.unsqueeze(0))
            self.assertTrue(torch.isfinite(total))
            self.assertGreater(float(objectness.detach()), 0.0)
            self.assertGreaterEqual(float(box.detach()), 0.0)
            optimizer.zero_grad(set_to_none=True)
            total.backward()
            optimizer.step()


if __name__ == "__main__":
    unittest.main()
