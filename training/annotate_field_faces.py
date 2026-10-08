from __future__ import annotations

import argparse
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from PIL import Image, ImageTk


class FaceAnnotator:
    def __init__(self, image_dir: Path, output: Path) -> None:
        self.image_dir = image_dir
        self.output = output
        self.images = sorted(
            path for path in image_dir.iterdir() if path.suffix.lower() in {".png", ".jpg", ".jpeg"}
        )
        if not self.images:
            raise ValueError(f"no images found in {image_dir}")

        self.rejected_path = output.with_name("field_rejected.txt")
        self.annotations = self.load_annotations()
        self.rejected = (
            set(self.rejected_path.read_text(encoding="utf-8").splitlines())
            if self.rejected_path.exists()
            else set()
        )
        completed = set(self.annotations) | self.rejected
        self.index = next(
            (index for index, path in enumerate(self.images) if path.name not in completed),
            0,
        )
        self.boxes: list[tuple[int, int, int, int]] = []
        self.drag_start: tuple[float, float] | None = None
        self.preview_rectangle: int | None = None
        self.scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0

        self.root = tk.Tk()
        self.root.title("AX7021现场人脸标注")
        self.canvas = tk.Canvas(self.root, width=1200, height=720, background="black")
        self.canvas.pack()
        self.status = tk.Label(
            self.root,
            text="拖动鼠标框选完整面部；Enter保存下一张，Backspace撤销，Delete舍弃，←返回",
        )
        self.status.pack(fill=tk.X)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Return>", self.save_and_next)
        self.root.bind("<BackSpace>", self.undo_box)
        self.root.bind("<Delete>", self.reject_and_next)
        self.root.bind("<Left>", self.previous)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.show_image()

    def load_annotations(self) -> dict[str, list[tuple[int, int, int, int]]]:
        if not self.output.exists():
            return {}
        lines = self.output.read_text(encoding="utf-8").splitlines()
        annotations: dict[str, list[tuple[int, int, int, int]]] = {}
        index = 0
        while index < len(lines):
            name = lines[index].strip()
            index += 1
            if not name or index >= len(lines):
                break
            count = int(lines[index])
            index += 1
            boxes: list[tuple[int, int, int, int]] = []
            for _ in range(count):
                fields = lines[index].split()
                index += 1
                boxes.append(tuple(int(value) for value in fields[:4]))
            if boxes:
                annotations[name] = boxes
        return annotations

    def show_image(self) -> None:
        path = self.images[self.index]
        with Image.open(path) as source:
            self.image = source.convert("RGB")
        width, height = self.image.size
        self.scale = min(1200 / width, 720 / height)
        display_width = int(width * self.scale)
        display_height = int(height * self.scale)
        self.offset_x = (1200 - display_width) / 2
        self.offset_y = (720 - display_height) / 2
        display = self.image.resize((display_width, display_height), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(display)
        self.canvas.delete("all")
        self.canvas.create_image(self.offset_x, self.offset_y, anchor=tk.NW, image=self.photo)
        self.boxes = list(self.annotations.get(path.name, []))
        self.draw_boxes()
        self.update_status()

    def update_status(self) -> None:
        self.status.config(
            text=(
                f"{self.index + 1}/{len(self.images)}  {self.images[self.index].name}  "
                f"人脸框={len(self.boxes)}（限1～3个；帽子/墨镜/口罩照片请Delete舍弃）"
            )
        )

    def canvas_to_image(self, x: float, y: float) -> tuple[int, int]:
        image_x = round((x - self.offset_x) / self.scale)
        image_y = round((y - self.offset_y) / self.scale)
        return (
            max(0, min(self.image.width - 1, image_x)),
            max(0, min(self.image.height - 1, image_y)),
        )

    def image_to_canvas(self, x: int, y: int) -> tuple[float, float]:
        return self.offset_x + x * self.scale, self.offset_y + y * self.scale

    def on_press(self, event: tk.Event) -> None:
        if len(self.boxes) >= 3:
            messagebox.showinfo("最多3人", "每张图片最多标注3张人脸。")
            return
        self.drag_start = (event.x, event.y)

    def on_drag(self, event: tk.Event) -> None:
        if self.drag_start is None:
            return
        if self.preview_rectangle is not None:
            self.canvas.delete(self.preview_rectangle)
        self.preview_rectangle = self.canvas.create_rectangle(
            self.drag_start[0], self.drag_start[1], event.x, event.y, outline="yellow", width=2
        )

    def on_release(self, event: tk.Event) -> None:
        if self.drag_start is None:
            return
        x1, y1 = self.canvas_to_image(*self.drag_start)
        x2, y2 = self.canvas_to_image(event.x, event.y)
        left, right = sorted((x1, x2))
        top, bottom = sorted((y1, y2))
        self.drag_start = None
        self.preview_rectangle = None
        if right - left >= 16 and bottom - top >= 16:
            self.boxes.append((left, top, right - left, bottom - top))
        self.canvas.delete("box")
        self.draw_boxes()
        self.update_status()

    def draw_boxes(self) -> None:
        self.canvas.delete("box")
        for left, top, width, height in self.boxes:
            x1, y1 = self.image_to_canvas(left, top)
            x2, y2 = self.image_to_canvas(left + width, top + height)
            self.canvas.create_rectangle(x1, y1, x2, y2, outline="#00ff40", width=3, tags="box")

    def save_current(self) -> bool:
        if not 1 <= len(self.boxes) <= 3:
            messagebox.showwarning("标注数量不正确", "保存图片前必须标注1～3张完整面部。")
            return False
        self.annotations[self.images[self.index].name] = list(self.boxes)
        self.rejected.discard(self.images[self.index].name)
        self.write_annotations()
        return True

    def save_and_next(self, _event: tk.Event | None = None) -> None:
        if self.save_current() and self.index + 1 < len(self.images):
            self.index += 1
            self.show_image()
        elif self.index + 1 == len(self.images):
            messagebox.showinfo("完成", f"全部图片已处理，标注已保存到\n{self.output}")

    def reject_and_next(self, _event: tk.Event | None = None) -> None:
        name = self.images[self.index].name
        self.annotations.pop(name, None)
        self.rejected.add(name)
        self.write_annotations()
        if self.index + 1 < len(self.images):
            self.index += 1
            self.show_image()

    def undo_box(self, _event: tk.Event | None = None) -> None:
        if self.boxes:
            self.boxes.pop()
            self.draw_boxes()
            self.update_status()

    def previous(self, _event: tk.Event | None = None) -> None:
        if self.index > 0:
            self.index -= 1
            self.show_image()

    def write_annotations(self) -> None:
        lines: list[str] = []
        for path in self.images:
            boxes = self.annotations.get(path.name)
            if not boxes:
                continue
            lines.extend([path.name, str(len(boxes))])
            lines.extend(f"{x} {y} {width} {height} 0 0 0 0 0 0" for x, y, width, height in boxes)
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        self.rejected_path.write_text(
            "\n".join(sorted(self.rejected)) + ("\n" if self.rejected else ""),
            encoding="utf-8",
        )

    def close(self) -> None:
        self.write_annotations()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Annotate AX7021 field face frames.")
    parser.add_argument(
        "--images", type=Path, default=Path("training/field_dataset/images")
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("training/field_dataset/field_annotations.txt"),
    )
    args = parser.parse_args()
    FaceAnnotator(args.images, args.output).run()


if __name__ == "__main__":
    main()
