from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import torch
from PIL import Image

from training.export_weights import export_checkpoint
from training.model import TinyFaceDetector, count_macs, non_max_suppression
from training.train import detection_loss
from training.widerface_dataset import WiderFaceGridDataset, parse_widerface_annotations
from training.yolo_face_dataset import YoloFaceGridDataset


class TrainingPipelineTest(unittest.TestCase):
    def test_yolo_dataset_filter_and_target(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary_directory:
            root = Path(temporary_directory)
            images = root / "images"
            labels = root / "labels"
            images.mkdir()
            labels.mkdir()
            Image.new("RGB", (640, 480), (80, 100, 120)).save(images / "one.jpg")
            Image.new("RGB", (640, 480)).save(images / "crowd.jpg")
            (labels / "one.txt").write_text("0 0.5 0.5 0.25 0.5\n", encoding="utf-8")
            (labels / "crowd.txt").write_text(
                "0 0.2 0.2 0.1 0.1\n0 0.5 0.5 0.1 0.1\n0 0.8 0.8 0.1 0.1\n",
                encoding="utf-8",
            )
            dataset = YoloFaceGridDataset(
                images,
                labels,
                min_face_pixels=16,
                min_faces_per_image=1,
                max_faces_per_image=2,
                require_all_faces_detectable=True,
            )
            self.assertEqual(len(dataset), 1)
            image, target = dataset[0]
            self.assertEqual(tuple(image.shape), (1, 120, 160))
            self.assertEqual(float(target[0].sum()), 1.0)
            self.assertAlmostEqual(float(target[3, 7, 10]), 0.25)
            self.assertAlmostEqual(float(target[4, 7, 10]), 0.5)

    def test_non_max_suppression(self) -> None:
        boxes = [
            (0.1, 0.1, 0.5, 0.5, 0.9),
            (0.12, 0.12, 0.52, 0.52, 0.8),
            (0.6, 0.6, 0.9, 0.9, 0.7),
        ]
        selected = non_max_suppression(boxes, iou_threshold=0.35)
        self.assertEqual(len(selected), 2)
        self.assertEqual(selected[0], boxes[0])
        self.assertEqual(selected[1], boxes[2])

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
        self.assertEqual(count_macs(), 3_276_000)

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
            self.assertEqual(counts, [72, 1152, 3456, 216, 576, 216, 576, 120])
            self.assertEqual(sum(counts), 6384)
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

    def test_minimum_face_size_filter(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary_directory:
            root = Path(temporary_directory)
            image_root = root / "images"
            image_root.mkdir()
            Image.new("RGB", (320, 240)).save(image_root / "sample.jpg")
            annotation = root / "annotations.txt"
            annotation.write_text(
                "sample.jpg\n2\n10 10 8 8 0 0 0 0 0 0\n"
                "80 60 80 120 0 0 0 0 0 0\n",
                encoding="utf-8",
            )
            dataset = WiderFaceGridDataset(
                image_root, annotation, min_face_pixels=8.0
            )
            _, target = dataset[0]
            self.assertEqual(float(target[0].sum()), 1.0)

    def test_crowded_image_filter(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary_directory:
            root = Path(temporary_directory)
            image_root = root / "images"
            image_root.mkdir()
            Image.new("RGB", (160, 120)).save(image_root / "single.jpg")
            Image.new("RGB", (160, 120)).save(image_root / "crowd.jpg")
            annotation = root / "annotations.txt"
            annotation.write_text(
                "single.jpg\n1\n20 20 40 40 0 0 0 0 0 0\n"
                "crowd.jpg\n3\n10 10 20 20 0 0 0 0 0 0\n"
                "50 10 20 20 0 0 0 0 0 0\n90 10 20 20 0 0 0 0 0 0\n",
                encoding="utf-8",
            )
            dataset = WiderFaceGridDataset(
                image_root, annotation, max_faces_per_image=1
            )
            self.assertEqual(len(dataset), 1)
            self.assertEqual(dataset.samples[0].relative_path, "single.jpg")

    def test_clear_full_face_filter_uses_wider_flags(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary_directory:
            root = Path(temporary_directory)
            image_root = root / "images"
            image_root.mkdir()
            for name in ("clear.jpg", "blurred.jpg", "occluded.jpg", "posed.jpg"):
                Image.new("RGB", (160, 120)).save(image_root / name)
            annotation = root / "annotations.txt"
            annotation.write_text(
                "clear.jpg\n1\n20 20 40 40 0 0 0 0 0 0\n"
                "blurred.jpg\n1\n20 20 40 40 1 0 0 0 0 0\n"
                "occluded.jpg\n1\n20 20 40 40 0 0 0 0 1 0\n"
                "posed.jpg\n1\n20 20 40 40 0 0 0 0 0 1\n",
                encoding="utf-8",
            )
            samples = parse_widerface_annotations(annotation)
            self.assertTrue(samples[0].annotations[0].is_clear_full_face)
            self.assertFalse(samples[1].annotations[0].is_clear_full_face)
            dataset = WiderFaceGridDataset(
                image_root,
                annotation,
                min_faces_per_image=1,
                max_faces_per_image=3,
                clean_full_faces_only=True,
            )
            self.assertEqual(len(dataset), 1)
            self.assertEqual(dataset.samples[0].relative_path, "clear.jpg")

    def test_all_faces_must_be_detectable(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary_directory:
            root = Path(temporary_directory)
            image_root = root / "images"
            image_root.mkdir()
            Image.new("RGB", (320, 240)).save(image_root / "mixed.jpg")
            Image.new("RGB", (320, 240)).save(image_root / "large.jpg")
            annotation = root / "annotations.txt"
            annotation.write_text(
                "mixed.jpg\n2\n10 10 8 8 0 0 0 0 0 0\n"
                "80 60 80 120 0 0 0 0 0 0\n"
                "large.jpg\n1\n40 30 80 80 0 0 0 0 0 0\n",
                encoding="utf-8",
            )
            dataset = WiderFaceGridDataset(
                image_root,
                annotation,
                min_face_pixels=16.0,
                require_all_faces_detectable=True,
            )
            self.assertEqual(len(dataset), 1)
            self.assertEqual(dataset.samples[0].relative_path, "large.jpg")

    def test_require_detectable_face(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary_directory:
            root = Path(temporary_directory)
            image_root = root / "images"
            image_root.mkdir()
            Image.new("RGB", (320, 240)).save(image_root / "tiny.jpg")
            Image.new("RGB", (320, 240)).save(image_root / "large.jpg")
            annotation = root / "annotations.txt"
            annotation.write_text(
                "tiny.jpg\n1\n10 10 4 4 0 0 0 0 0 0\n"
                "large.jpg\n1\n40 30 80 80 0 0 0 0 0 0\n",
                encoding="utf-8",
            )
            dataset = WiderFaceGridDataset(
                image_root,
                annotation,
                min_face_pixels=16.0,
                require_detectable_face=True,
            )
            self.assertEqual(len(dataset), 1)
            self.assertEqual(dataset.samples[0].relative_path, "large.jpg")

    def test_include_empty_images_keeps_hard_negatives(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary_directory:
            root = Path(temporary_directory)
            image_root = root / "images"
            image_root.mkdir()
            Image.new("RGB", (320, 240)).save(image_root / "negative.jpg")
            Image.new("RGB", (320, 240)).save(image_root / "positive.jpg")
            annotation = root / "annotations.txt"
            annotation.write_text(
                "negative.jpg\n0\n"
                "positive.jpg\n1\n40 30 80 80 0 0 0 0 0 0\n",
                encoding="utf-8",
            )
            dataset = WiderFaceGridDataset(
                image_root,
                annotation,
                min_face_pixels=16.0,
                min_faces_per_image=1,
                require_detectable_face=True,
                clean_full_faces_only=True,
                include_empty_images=True,
            )
            self.assertEqual(
                [sample.relative_path for sample in dataset.samples],
                ["negative.jpg", "positive.jpg"],
            )
            _, negative_target = dataset[0]
            self.assertEqual(float(negative_target[0].sum()), 0.0)


if __name__ == "__main__":
    unittest.main()
