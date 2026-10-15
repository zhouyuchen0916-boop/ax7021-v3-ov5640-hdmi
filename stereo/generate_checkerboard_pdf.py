from pathlib import Path

def main() -> None:
    output = Path("output/pdf/an5642_checkerboard_9x6_25mm_a4_landscape.pdf")
    output.parent.mkdir(parents=True, exist_ok=True)
    points_per_mm = 72.0 / 25.4
    page_width = 297.0 * points_per_mm
    page_height = 210.0 * points_per_mm
    square = 25.0 * points_per_mm
    columns, rows = 10, 7
    board_width = columns * square
    board_height = rows * square
    origin_x = (page_width - board_width) / 2
    origin_y = (page_height - board_height) / 2

    drawing = ["1 1 1 rg", f"0 0 {page_width:.4f} {page_height:.4f} re f"]
    for row in range(rows):
        for column in range(columns):
            if (row + column) % 2 == 0:
                x = origin_x + column * square
                y = origin_y + (rows - 1 - row) * square
                drawing.extend(
                    ["0 0 0 rg", f"{x:.4f} {y:.4f} {square:.4f} {square:.4f} re f"]
                )
    drawing.extend(
        [
            "0 0 0 RG",
            f"{0.2 * points_per_mm:.4f} w",
            f"{origin_x:.4f} {origin_y:.4f} {board_width:.4f} {board_height:.4f} re S",
        ]
    )
    content = ("\n".join(drawing) + "\n").encode("ascii")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width:.4f} "
            f"{page_height:.4f}] /Contents 4 0 R /Resources << >> >>"
        ).encode("ascii"),
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n"
        + content
        + b"endstream",
    ]
    document = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(document))
        document.extend(f"{number} 0 obj\n".encode("ascii"))
        document.extend(body)
        document.extend(b"\nendobj\n")
    xref_offset = len(document)
    document.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    document.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    document.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    output.write_bytes(document)

    print(output.resolve())
    print(f"page_mm={page_width / points_per_mm:.3f}x{page_height / points_per_mm:.3f}")
    print(
        f"board_mm={board_width / points_per_mm:.3f}x"
        f"{board_height / points_per_mm:.3f}"
    )


if __name__ == "__main__":
    main()
