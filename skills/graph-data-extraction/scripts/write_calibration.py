#!/usr/bin/env python3
"""
write_calibration.py - emit a calibration.json that captures the plot
geometry: image size, the rectangle enclosing the axes and plot (pixel
bounding box of the visible plot region), the data tick range and its
corresponding pixel box, and the linear axis calibration. Run after Phase 2
(or invoke programmatically from your extraction script).

The plot frame box is bounded by the DETECTED y-axis column (left) and
x-axis row (bottom), plus the data extent (top, right). For charts with
no explicit right/top frame line — most matplotlib L-shaped axes — this is
the right answer: the plot extends left to the y-axis line (which may be
to the left of the leftmost data tick, e.g. grouped bar charts) but the
top/right are wherever the data range ends.

Usage as a script:
    python3 write_calibration.py IMAGE.png OUT.json \\
        --x-axis-cal m b --y-axis-cal m b \\
        --x-data-range XMIN XMAX --y-data-range YMIN YMAX

Or as a module:
    from write_calibration import write_calibration
    write_calibration(image_path, out_path,
                      x_axis=(mx, bx), y_axis=(my, by),
                      x_data_range=(xmin, xmax), y_data_range=(ymin, ymax))
"""
import argparse
import json
import sys
import numpy as np
import cv2


def _longest_run_per_col(dark):
    H, W = dark.shape
    out = np.zeros(W, dtype=np.int32)
    for c in range(W):
        col = dark[:, c]
        run = best = 0
        for v in col:
            if v: run += 1; best = max(best, run)
            else: run = 0
        out[c] = best
    return out


def _longest_run_per_row(dark):
    H, W = dark.shape
    out = np.zeros(H, dtype=np.int32)
    for r in range(H):
        row = dark[r, :]
        run = best = 0
        for v in row:
            if v: run += 1; best = max(best, run)
            else: run = 0
        out[r] = best
    return out


def _group(idx, gap=8):
    if len(idx) == 0:
        return []
    g, c = [], [idx[0]]
    for x in idx[1:]:
        if x - c[-1] <= gap:
            c.append(x)
        else:
            g.append(int(np.mean(c))); c = [x]
    g.append(int(np.mean(c)))
    return g


def detect_axes(img, border_margin=15, dark_thr=180, line_density=0.50):
    """Detect plot-frame axis lines by longest-contiguous-run analysis.

    Returns (v_groups, h_groups): grouped column / row positions of long
    dark vertical / horizontal lines in the image interior (image borders
    within border_margin px excluded). The leftmost v_group is the y-axis;
    the bottommost h_group nearest to the calibration-derived y=0 row is
    the x-axis.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    H, W = gray.shape
    dark = (gray < dark_thr).astype(np.uint8)
    cr = _longest_run_per_col(dark)
    rr = _longest_run_per_row(dark)
    v = [int(c) for c in np.where(cr > line_density * H)[0]
         if border_margin <= c <= W - border_margin]
    h = [int(r) for r in np.where(rr > line_density * W)[0]
         if border_margin <= r <= H - border_margin]
    return _group(v), _group(h)


def write_calibration(image_path, out_path, x_axis, y_axis,
                      x_data_range, y_data_range):
    """Emit calibration.json next to an extraction's data.csv."""
    mx, bx = x_axis
    my, by = y_axis
    xmin, xmax = x_data_range
    ymin, ymax = y_data_range

    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(image_path)
    H, W = img.shape[:2]
    v_groups, h_groups = detect_axes(img)

    px_xmin = (xmin - bx) / mx
    px_xmax = (xmax - bx) / mx
    px_ymin = (ymin - by) / my
    px_ymax = (ymax - by) / my
    d_left  = int(round(min(px_xmin, px_xmax)))
    d_right = int(round(max(px_xmin, px_xmax)))
    d_top   = int(round(min(px_ymin, px_ymax)))
    d_bot   = int(round(max(px_ymin, px_ymax)))

    y_axis_col = v_groups[0] if v_groups else d_left
    x_axis_row = (min(h_groups, key=lambda r: abs(r - d_bot))
                  if h_groups else d_bot)

    plot_left  = y_axis_col
    plot_bot   = x_axis_row
    plot_top   = d_top
    plot_right = d_right

    cal = {
        "image": image_path.rsplit('/', 1)[-1],
        "image_size": {"width": W, "height": H},
        "plot_frame_box": {
            "left":   plot_left,
            "right":  plot_right,
            "top":    plot_top,
            "bottom": plot_bot,
            "width":  plot_right - plot_left + 1,
            "height": plot_bot - plot_top + 1,
            "offset_from_image_origin": {"x": plot_left, "y": plot_top},
            "description": ("Pixel bounding box of the rectangle enclosing the axes and plot. "
                            "Origin (0,0) is the top-left of the image; y grows downward. "
                            "Left edge = detected y-axis line column; bottom edge = detected x-axis "
                            "line row. Top and right edges = where data_y_max and data_x_max land "
                            "in pixel space (no explicit top/right frame line assumed)."),
            "definitions": {
                "left":   "column of the y-axis line",
                "right":  "column where x = x_max (rightmost tick) lands",
                "top":    "row where y = y_max (topmost tick) lands",
                "bottom": "row of the x-axis line",
            },
        },
        "data_extent_box": {
            "left":   d_left,
            "right":  d_right,
            "top":    d_top,
            "bottom": d_bot,
            "width":  d_right - d_left + 1,
            "height": d_bot - d_top + 1,
            "description": (f"Pixel bounding box of just the data tick range "
                            f"(x={xmin}..{xmax}, y={ymin}..{ymax}). For inset layouts (grouped "
                            "bar charts, matplotlib defaults) this is smaller than plot_frame_box."),
        },
        "data_range": {"x_min": xmin, "x_max": xmax, "y_min": ymin, "y_max": ymax},
        "axis_calibration": {
            "x_axis": {"formula": f"value = {mx} * col + {bx}", "m": mx, "b": bx,
                       "inverse": f"col = (value - {bx}) / {mx}"},
            "y_axis": {"formula": f"value = {my} * row + {by}", "m": my, "b": by,
                       "inverse": f"row = (value - {by}) / {my}"},
        },
        "detection_internals": {
            "y_axis_col_detected": v_groups[0] if v_groups else None,
            "x_axis_row_detected": (min(h_groups, key=lambda r: abs(r - d_bot))
                                    if h_groups else None),
            "all_interior_v_lines": v_groups,
            "all_interior_h_lines": h_groups,
            "rule": "Long-run detection: longest contiguous run of pixels with gray<180 "
                   "exceeding 50% of image height/width. Outer image-border lines "
                   "(within 15 px of edge) excluded.",
        },
    }
    with open(out_path, "w") as f:
        json.dump(cal, f, indent=2)
    return cal


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("out")
    ap.add_argument("--x-axis-cal", type=float, nargs=2, metavar=("m", "b"), required=True)
    ap.add_argument("--y-axis-cal", type=float, nargs=2, metavar=("m", "b"), required=True)
    ap.add_argument("--x-data-range", type=float, nargs=2, metavar=("XMIN", "XMAX"), required=True)
    ap.add_argument("--y-data-range", type=float, nargs=2, metavar=("YMIN", "YMAX"), required=True)
    args = ap.parse_args()
    cal = write_calibration(args.image, args.out,
                            tuple(args.x_axis_cal), tuple(args.y_axis_cal),
                            tuple(args.x_data_range), tuple(args.y_data_range))
    p = cal["plot_frame_box"]
    print(f"wrote {args.out}")
    print(f"  image: {cal['image_size']['width']}x{cal['image_size']['height']}")
    print(f"  plot_frame_box: left={p['left']} top={p['top']} right={p['right']} bottom={p['bottom']} "
          f"({p['width']}x{p['height']})")


if __name__ == "__main__":
    main()
