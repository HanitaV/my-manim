"""Private drawing helpers for :class:`~manim.renderer.cairo.CairoRenderer`."""

from __future__ import annotations

import itertools as it
import math
import operator as op
from collections.abc import Callable, Iterable
from functools import lru_cache, reduce
from typing import TYPE_CHECKING, Any

import cairo
import numpy as np
from PIL import Image, ImageFilter

from manim.cinema.cuda import cuda_available, cuda_process_glass_roi
from manim.constants import CapStyleType, LineJointType
from manim.mobject.mobject import Mobject
from manim.mobject.types.image_mobject import (
    AbstractImageMobject,
    ImageMobjectFromCamera,
)
from manim.mobject.types.point_cloud_mobject import PMobject
from manim.mobject.types.vectorized_mobject import VMobject
from manim.utils.space_ops import cross2d

from .target import _CairoRenderTarget

if TYPE_CHECKING:
    from manim.mobject.glass import GlassStyle
    from manim.typing import (
        FloatRGBA_Array,
        FloatRGBALike_Array,
        Point3D_Array,
        RGBAPixelArray,
    )

    from .camera import Camera

_LINE_JOIN_MAP = {
    LineJointType.AUTO: cairo.LineJoin.MITER,  # cairo default; TODO: this could be improved
    LineJointType.ROUND: cairo.LineJoin.ROUND,
    LineJointType.BEVEL: cairo.LineJoin.BEVEL,
    LineJointType.MITER: cairo.LineJoin.MITER,
}

_CAP_STYLE_MAP = {
    CapStyleType.AUTO: cairo.LineCap.BUTT,  # cairo default; TODO: this could be improved
    CapStyleType.ROUND: cairo.LineCap.ROUND,
    CapStyleType.BUTT: cairo.LineCap.BUTT,
    CapStyleType.SQUARE: cairo.LineCap.SQUARE,
}

_ImageResolver = Callable[[ImageMobjectFromCamera], np.ndarray | None]


@lru_cache(maxsize=2)
def _frost_noise_tile(size: int = 128) -> np.ndarray:
    """Deterministic micro-frost noise tile in ``[-1, 1]``."""
    yy = np.arange(size, dtype=np.float32)[:, None]
    xx = np.arange(size, dtype=np.float32)[None, :]
    hashed = np.sin(xx * 12.9898 + yy * 78.233) * 43758.5453
    return ((hashed - np.floor(hashed)) - 0.5) * 2.0


class _CairoDrawingContext:
    """Draw mobjects into one renderer-owned target using one semantic camera."""

    def __init__(
        self,
        *,
        camera: Camera,
        target: _CairoRenderTarget,
        image_resolver: _ImageResolver,
    ) -> None:
        self.camera = camera
        self.target = target
        self.image_resolver = image_resolver

    def draw(
        self,
        mobjects: Iterable[Mobject],
        *,
        include_submobjects: bool = True,
        excluded_mobjects: list[Mobject] | None = None,
    ) -> None:
        self.target._ensure_open()
        display_funcs: dict[type[Mobject], Callable[[list[Any]], None]] = {
            VMobject: self._display_vectorized_mobjects,
            PMobject: self._display_point_cloud_mobjects,
            ImageMobjectFromCamera: self._display_image_mobjects,
            AbstractImageMobject: self._display_image_mobjects,
            Mobject: lambda batch: None,
        }

        def type_or_raise(mobject: Mobject) -> type[Mobject]:
            for mobject_type in display_funcs:
                if isinstance(mobject, mobject_type):
                    return mobject_type
            raise TypeError(
                f"Displaying an object of class {type(mobject).__name__} is not supported",
            )

        with self.camera._drawing():
            to_display = self.camera.get_mobjects_to_display(
                mobjects,
                include_submobjects=include_submobjects,
                excluded_mobjects=excluded_mobjects,
            )
            for group_type, group in it.groupby(to_display, type_or_raise):
                display_funcs[group_type](list(group))

    def _display_vectorized_mobjects(self, vmobjects: list[VMobject]) -> None:
        if not vmobjects:
            return
        for image, batch in it.groupby(
            vmobjects,
            lambda vmobject: vmobject.get_background_image(),
        ):
            if image:
                self._display_background_colored_vmobjects(image, list(batch))
            else:
                self._display_non_background_colored_vmobjects(batch)

    def _display_non_background_colored_vmobjects(
        self,
        vmobjects: Iterable[VMobject],
    ) -> None:
        context = self.target.get_context(self.camera)
        for vmobject in vmobjects:
            glass_style = getattr(vmobject, "_glass_style", None)
            if glass_style is not None:
                self._display_glass_vmobject(vmobject, context, glass_style)
            else:
                self._display_vectorized(vmobject, context)

    def _display_glass_vmobject(
        self,
        vmobject: VMobject,
        context: cairo.Context,
        glass_style: GlassStyle,
    ) -> None:
        if vmobject.get_num_points() == 0:
            return
        fill_alpha = float(np.max(vmobject.get_fill_opacities()))
        stroke_alpha = float(np.max(vmobject.get_stroke_opacities()))
        ratios = []
        if glass_style.tint_opacity > 1e-4:
            ratios.append(fill_alpha / glass_style.tint_opacity)
        if glass_style.rim_opacity > 1e-4:
            ratios.append(stroke_alpha / glass_style.rim_opacity)
        alpha_scale = min(1.0, max(ratios)) if ratios else 1.0
        if alpha_scale <= 1e-3:
            return

        subpixel = self._points_to_subpixel_coords(vmobject, vmobject.points)
        if len(subpixel) == 0:
            return

        settings = self.target.settings
        px_scale = settings.pixel_height / 1080.0
        sigma = max(0.0, glass_style.blur_radius * px_scale)

        pad = int(math.ceil(3.0 * sigma + 6))
        x0 = max(0, int(math.floor(float(np.min(subpixel[:, 0])))) - pad)
        x1 = min(settings.pixel_width, int(math.ceil(float(np.max(subpixel[:, 0])))) + pad)
        y0 = max(0, int(math.floor(float(np.min(subpixel[:, 1])))) - pad)
        y1 = min(settings.pixel_height, int(math.ceil(float(np.max(subpixel[:, 1])))) + pad)
        if x1 <= x0 or y1 <= y0:
            return

        # Flush pending Cairo draws so target.pixels contains the live backdrop.
        context.get_target().flush()

        # Rasterize anti-aliased shape silhouette into scratch ROI.
        scratch = self.target.get_scratch_target()
        scratch.pixels[y0:y1, x0:x1] = 0
        scratch_ctx = scratch.get_context(self.camera)
        scratch_ctx.get_target().mark_dirty()
        self._set_cairo_context_path(scratch_ctx, vmobject)
        scratch_ctx.set_source_rgba(1.0, 1.0, 1.0, 1.0)
        scratch_ctx.fill()
        scratch_ctx.get_target().flush()
        mask = scratch.pixels[y0:y1, x0:x1, 3].astype(np.float32) / 255.0
        if float(np.max(mask)) <= 1e-3:
            return

        backdrop_u8 = self.target.pixels[y0:y1, x0:x1, :3].copy()
        roi_h, roi_w = mask.shape
        tint_rgb = vmobject.get_fill_color().to_rgb().astype(np.float32)
        tint_op = float(
            np.clip(fill_alpha / max(alpha_scale, 1e-4), 0.0, 1.0)
            if glass_style.tint_opacity > 0.0
            else 0.0
        )

        if cuda_available() and roi_h * roi_w >= 4096:
            self.target.pixels[y0:y1, x0:x1] = cuda_process_glass_roi(
                backdrop_u8,
                self.target.pixels[y0:y1, x0:x1],
                scratch.pixels[y0:y1, x0:x1, 3],
                sigma=sigma,
                refraction=glass_style.refraction,
                px_scale=px_scale,
                saturation=glass_style.saturation,
                brightness=glass_style.brightness,
                tint_rgb=tint_rgb,
                tint_op=tint_op,
                sheen_opacity=glass_style.sheen_opacity,
                frost_noise=glass_style.frost_noise,
                alpha_scale=alpha_scale,
                x0=x0,
                y0=y0,
            )
            context.get_target().mark_dirty()
        else:
            # 1. Optical backdrop blur via C-accelerated Pillow GaussianBlur
            if sigma > 8.0 and roi_h >= 32 and roi_w >= 32:
                ds_w, ds_h = max(1, roi_w // 2), max(1, roi_h // 2)
                blurred_pil = (
                    Image.fromarray(backdrop_u8, mode="RGB")
                    .resize((ds_w, ds_h), resample=Image.Resampling.BILINEAR)
                    .filter(ImageFilter.GaussianBlur(radius=sigma * 0.5))
                    .resize((roi_w, roi_h), resample=Image.Resampling.BILINEAR)
                )
                blurred = np.asarray(blurred_pil, dtype=np.float32) * (1.0 / 255.0)
            elif sigma > 0.1:
                blurred_pil = Image.fromarray(backdrop_u8, mode="RGB").filter(
                    ImageFilter.GaussianBlur(radius=sigma)
                )
                blurred = np.asarray(blurred_pil, dtype=np.float32) * (1.0 / 255.0)
            else:
                blurred = backdrop_u8.astype(np.float32) * (1.0 / 255.0)

            # 2. Optional bevel edge refraction (vectorized 2D bilinear warp)
            if glass_style.refraction > 0.0 and roi_h >= 8 and roi_w >= 8:
                bevel_pil = Image.fromarray(scratch.pixels[y0:y1, x0:x1, 3], mode="L").filter(
                    ImageFilter.GaussianBlur(radius=max(1.5, 6.0 * px_scale))
                )
                bevel = np.asarray(bevel_pil, dtype=np.float32) * (1.0 / 255.0)
                gy, gx = np.gradient(bevel)
                disp = glass_style.refraction * 180.0 * px_scale
                yy = np.arange(roi_h, dtype=np.float32)[:, None] - gy * disp
                xx = np.arange(roi_w, dtype=np.float32)[None, :] - gx * disp
                np.clip(yy, 0.0, roi_h - 1.001, out=yy)
                np.clip(xx, 0.0, roi_w - 1.001, out=xx)
                iy0 = yy.astype(np.intp)
                ix0 = xx.astype(np.intp)
                fy = (yy - iy0)[..., None]
                fx = (xx - ix0)[..., None]
                c00 = blurred[iy0, ix0]
                c01 = blurred[iy0, ix0 + 1]
                c10 = blurred[iy0 + 1, ix0]
                c11 = blurred[iy0 + 1, ix0 + 1]
                blurred = (c00 * (1.0 - fx) + c01 * fx) * (1.0 - fy) + (
                    c10 * (1.0 - fx) + c11 * fx
                ) * fy

            # 3. Chroma boost + brightness
            luma = (
                0.2126 * blurred[..., 0]
                + 0.7152 * blurred[..., 1]
                + 0.0722 * blurred[..., 2]
            )[..., None]
            glass_rgb = np.clip(
                (luma + (blurred - luma) * glass_style.saturation) * glass_style.brightness,
                0.0,
                1.0,
            )

            # 4. Dark glass tint + optional sheen/frost
            glass_rgb = glass_rgb * (1.0 - tint_op) + tint_rgb * tint_op

            if glass_style.sheen_opacity > 0.0:
                v_loc = np.linspace(0.0, 1.0, roi_h, dtype=np.float32)[:, None]
                sheen = (1.0 - v_loc) * glass_style.sheen_opacity
                glass_rgb = np.clip(glass_rgb + sheen[..., None], 0.0, 1.0)

            if glass_style.frost_noise > 0.0:
                tile = _frost_noise_tile(128)
                frost = tile[
                    (np.arange(y0, y1) & 127)[:, None],
                    (np.arange(x0, x1) & 127)[None, :],
                ] * glass_style.frost_noise
                glass_rgb = np.clip(glass_rgb + frost[..., None], 0.0, 1.0)

            # 5. Composite glass over target ROI
            blend = (mask * alpha_scale)[..., None]
            dst_roi = self.target.pixels[y0:y1, x0:x1].astype(np.float32) / 255.0
            out_rgb = dst_roi[..., :3] * (1.0 - blend) + glass_rgb * blend
            out_a = dst_roi[..., 3:4] + blend * (1.0 - dst_roi[..., 3:4])
            self.target.pixels[y0:y1, x0:x1, :3] = np.clip(
                out_rgb * 255.0 + 0.5, 0.0, 255.0
            ).astype(np.uint8)
            self.target.pixels[y0:y1, x0:x1, 3:4] = np.clip(
                out_a * 255.0 + 0.5, 0.0, 255.0
            ).astype(np.uint8)
            context.get_target().mark_dirty()

        # 7. Background stroke (if any) + 3-stop directional specular rim stroke
        self._set_cairo_context_path(context, vmobject)
        self._apply_stroke(context, vmobject, background=True)

        rim_width = float(vmobject.get_stroke_width())
        if rim_width > 0.0 and stroke_alpha > 1e-3:
            rim_rgb = vmobject.get_stroke_color().to_rgb()
            center_pt = vmobject.get_center()
            half_w = float(vmobject.width) * 0.22
            top_pt = vmobject.get_top()
            bot_pt = vmobject.get_bottom()
            start_pt = np.array([center_pt[0] - half_w, top_pt[1], center_pt[2]])
            end_pt = np.array([center_pt[0] + half_w, bot_pt[1], center_pt[2]])
            grad_pts = self.camera.transform_points_pre_display(
                vmobject, np.vstack([start_pt, end_pt])
            )
            pattern = cairo.LinearGradient(
                float(grad_pts[0, 0]),
                float(grad_pts[0, 1]),
                float(grad_pts[1, 0]),
                float(grad_pts[1, 1]),
            )
            # Cairo FORMAT_ARGB32 uses BGRA byte order on little-endian hosts.
            b, g, r = float(rim_rgb[2]), float(rim_rgb[1]), float(rim_rgb[0])
            pattern.add_color_stop_rgba(0.00, b, g, r, stroke_alpha)
            pattern.add_color_stop_rgba(0.32, b * 0.65, g * 0.65, r * 0.65, stroke_alpha * 0.42)
            pattern.add_color_stop_rgba(0.74, b * 0.08, g * 0.08, r * 0.08, stroke_alpha * 0.50)
            pattern.add_color_stop_rgba(1.00, b * 0.55, g * 0.55, r * 0.55, stroke_alpha * 0.26)
            context.set_source(pattern)
            context.set_line_width(
                rim_width * settings.cairo_line_width_multiple
            )
            context.set_line_join(_LINE_JOIN_MAP[vmobject.joint_type])
            context.set_line_cap(_CAP_STYLE_MAP[vmobject.cap_style])
            context.stroke_preserve()

    def _display_vectorized(
        self,
        vmobject: VMobject,
        context: cairo.Context,
    ) -> None:
        self._set_cairo_context_path(context, vmobject)
        self._apply_stroke(context, vmobject, background=True)
        self._apply_fill(context, vmobject)
        self._apply_stroke(context, vmobject)

    def _set_cairo_context_path(
        self,
        context: cairo.Context,
        vmobject: VMobject,
    ) -> None:
        # Clear the previous path first: fills and strokes use the *_preserve
        # variants, so an early return must not leave another mobject's path
        # behind to be painted in this mobject's style.
        context.new_path()
        points = self.camera.transform_points_pre_display(vmobject, vmobject.points)
        if len(points) == 0:
            return

        nppcc = vmobject.n_points_per_cubic_curve
        split_indices = vmobject.get_subpath_split_indices_from_points(points, n_dims=2)
        if len(split_indices) == 0:
            return

        points_xy = points[:, :2].ravel()
        move_to = context.move_to
        curve_to = context.curve_to
        new_sub_path = context.new_sub_path
        close_path = context.close_path

        for start_index, end_index in split_indices:
            start_index = int(start_index)
            end_index = int(end_index)
            if end_index - start_index < nppcc:
                continue

            new_sub_path()
            base = start_index * 2
            move_to(points_xy[base], points_xy[base + 1])
            for index in range(
                start_index,
                end_index - nppcc + 1,
                nppcc,
            ):
                handle = (index + 1) * 2
                curve_to(
                    points_xy[handle],
                    points_xy[handle + 1],
                    points_xy[handle + 2],
                    points_xy[handle + 3],
                    points_xy[handle + 4],
                    points_xy[handle + 5],
                )
            if vmobject.consider_points_equals_2d(
                points[start_index],
                points[end_index - 1],
            ):
                close_path()

    def _set_cairo_context_color(
        self,
        context: cairo.Context,
        rgbas: FloatRGBALike_Array,
        vmobject: VMobject,
    ) -> None:
        if len(rgbas) == 1:
            context.set_source_rgba(*rgbas[0][2::-1], rgbas[0][3])
            return

        points = vmobject.get_gradient_start_and_end_points()
        points = self.camera.transform_points_pre_display(vmobject, points)
        pattern = cairo.LinearGradient(
            *it.chain(*(point[:2] for point in points)),
        )
        for rgba, offset in zip(
            rgbas,
            np.linspace(0, 1, len(rgbas)),
            strict=True,
        ):
            pattern.add_color_stop_rgba(offset, *rgba[2::-1], rgba[3])
        context.set_source(pattern)

    def _apply_fill(self, context: cairo.Context, vmobject: VMobject) -> None:
        self._set_cairo_context_color(
            context,
            self.camera.get_fill_rgbas(vmobject),
            vmobject,
        )
        context.fill_preserve()

    def _apply_stroke(
        self,
        context: cairo.Context,
        vmobject: VMobject,
        background: bool = False,
    ) -> None:
        width = vmobject.get_stroke_width(background)
        if width == 0:
            return
        self._set_cairo_context_color(
            context,
            self.camera.get_stroke_rgbas(vmobject, background=background),
            vmobject,
        )
        context.set_line_width(
            width * self.target.settings.cairo_line_width_multiple,
        )
        context.set_line_join(_LINE_JOIN_MAP[vmobject.joint_type])
        context.set_line_cap(_CAP_STYLE_MAP[vmobject.cap_style])
        context.stroke_preserve()

    def _display_background_colored_vmobjects(
        self,
        image: Image.Image | str,
        vmobjects: list[VMobject],
    ) -> None:
        """Draw vmobjects that share one background image as a mask over it."""
        scratch = self.target.get_scratch_target()
        scratch.clear()
        scratch_context = _CairoDrawingContext(
            camera=self.camera,
            target=scratch,
            image_resolver=self.image_resolver,
        )
        scratch_context._display_non_background_colored_vmobjects(vmobjects)
        background = self.target.get_background_image(image)
        colored = np.asarray(
            background * scratch.pixels.astype(float) / 255,
            dtype=np.uint8,
        )
        self._overlay_rgba_array(self.target.pixels, colored)

    def _display_point_cloud_mobjects(self, pmobjects: list[PMobject]) -> None:
        for pmobject in pmobjects:
            self._display_point_cloud(
                pmobject,
                pmobject.points,
                pmobject.rgbas,
                self._adjusted_thickness(pmobject.stroke_width),
            )

    def _display_point_cloud(
        self,
        pmobject: PMobject,
        points: Point3D_Array,
        rgbas: FloatRGBA_Array,
        thickness: float,
    ) -> None:
        if len(points) == 0:
            return
        pixel_coords = self._points_to_pixel_coords(pmobject, points)
        pixel_coords = self._thickened_coordinates(pixel_coords, thickness)
        pixel_array = self.target.pixels
        rgba_len = pixel_array.shape[2]

        int_rgbas = (255 * rgbas).astype(np.uint8)
        target_len = len(pixel_coords)
        factor = target_len // len(int_rgbas)
        int_rgbas = np.array([int_rgbas] * factor).reshape((target_len, rgba_len))

        on_screen_indices = self._on_screen_pixels(pixel_coords)
        pixel_coords = pixel_coords[on_screen_indices]
        int_rgbas = int_rgbas[on_screen_indices]

        height = self.target.settings.pixel_height
        width = self.target.settings.pixel_width
        flattener = np.array([1, width], dtype="int").reshape((2, 1))
        indices = np.dot(pixel_coords, flattener)[:, 0].astype("int")
        flattened = pixel_array.reshape((height * width, rgba_len))
        flattened[indices] = int_rgbas
        pixel_array[:, :] = flattened.reshape((height, width, rgba_len))

    def _display_image_mobjects(
        self,
        image_mobjects: list[AbstractImageMobject | ImageMobjectFromCamera],
    ) -> None:
        for image_mobject in image_mobjects:
            self._display_image_mobject(image_mobject)

    def _display_image_mobject(
        self,
        image_mobject: AbstractImageMobject | ImageMobjectFromCamera,
    ) -> None:
        source_pixels = (
            self.image_resolver(image_mobject)
            if isinstance(image_mobject, ImageMobjectFromCamera)
            else image_mobject.get_pixel_array()
        )
        if source_pixels is None:
            return
        sub_image = Image.fromarray(source_pixels, mode="RGBA")
        original_coords = np.array(
            [
                [0, 0],
                [sub_image.width, 0],
                [0, sub_image.height],
                [sub_image.width, sub_image.height],
            ],
        )
        target_coords = self._points_to_subpixel_coords(
            image_mobject,
            image_mobject.points,
        )
        int_target_coords = target_coords.astype(np.int64)
        settings = self.target.settings
        # Only rasterize the part of the image that lies inside the frame: the
        # cost of the perspective transform below grows with the size of its
        # output, which can exceed the frame by orders of magnitude when the
        # camera is zoomed in on the image.
        shift_vector = np.maximum(int_target_coords.min(axis=0), 0)
        upper_bounds = np.minimum(
            int_target_coords.max(axis=0),
            (settings.pixel_width, settings.pixel_height),
        )
        target_size = (
            int(upper_bounds[0] - shift_vector[0]),
            int(upper_bounds[1] - shift_vector[1]),
        )
        if min(target_size) <= 0:
            return
        target_coords -= shift_vector

        ordered_vertices = [target_coords[index] for index in (0, 1, 3, 2)]
        sides = [
            ordered_vertices[(index + 1) % 4] - ordered_vertices[index]
            for index in range(4)
        ]
        side_lengths = np.linalg.norm(sides, axis=1)
        longest_index = int(np.argmax(side_lengths))
        longest_side = sides[longest_index]
        longest_length = side_lengths[longest_index]
        if longest_length == 0:
            return
        previous_side = sides[(longest_index - 1) % 4]
        next_side = sides[(longest_index + 1) % 4]
        height_1 = abs(cross2d(longest_side, previous_side)) / longest_length
        height_2 = abs(cross2d(longest_side, next_side)) / longest_length
        if max(height_1, height_2) < 0.5:
            return

        homography_matrix = []
        for (x, y), (target_x, target_y) in zip(
            target_coords,
            original_coords,
            strict=True,
        ):
            homography_matrix.append(
                [x, y, 1, 0, 0, 0, -target_x * x, -target_x * y],
            )
            homography_matrix.append(
                [0, 0, 0, x, y, 1, -target_y * x, -target_y * y],
            )
        matrix = np.array(homography_matrix, dtype=np.float64)
        target = original_coords.reshape(8).astype(np.float64)
        try:
            coefficients = np.linalg.solve(matrix, target)
        except np.linalg.LinAlgError:
            return

        sub_image = sub_image.transform(
            size=target_size,
            method=Image.Transform.PERSPECTIVE,
            data=coefficients,
            resample=image_mobject.resampling_algorithm,
        )
        full_image = Image.new(
            "RGBA",
            (settings.pixel_width, settings.pixel_height),
            (0, 0, 0, 0),
        )
        full_image.paste(
            sub_image,
            box=(
                int(shift_vector[0]),
                int(shift_vector[1]),
                int(shift_vector[0] + target_size[0]),
                int(shift_vector[1] + target_size[1]),
            ),
        )
        self._overlay_pil_image(self.target.pixels, full_image)

    def _overlay_rgba_array(
        self,
        pixel_array: RGBAPixelArray,
        new_array: RGBAPixelArray,
    ) -> None:
        self._overlay_pil_image(pixel_array, Image.fromarray(new_array))

    @staticmethod
    def _overlay_pil_image(
        pixel_array: RGBAPixelArray,
        image: Image.Image,
    ) -> None:
        pixel_array[:, :] = np.asarray(
            Image.alpha_composite(Image.fromarray(pixel_array), image),
            dtype=np.uint8,
        )

    def _points_to_subpixel_coords(
        self,
        mobject: Mobject,
        points: Point3D_Array,
    ) -> np.ndarray:
        points = self.camera.transform_points_pre_display(mobject, points)
        # Use the same view center as the Cairo context transform, so that
        # pixel-placed images and point clouds line up with vectorized mobjects
        # (ThreeDCamera.project_points() has already removed frame_center).
        shifted_points = points - self.camera.get_view_transform_center()
        settings = self.target.settings
        result = np.zeros((len(points), 2))
        result[:, 0] = (
            shifted_points[:, 0] * settings.pixel_width / self.camera.frame_width
            + settings.pixel_width / 2
        )
        result[:, 1] = (
            -shifted_points[:, 1] * settings.pixel_height / self.camera.frame_height
            + settings.pixel_height / 2
        )
        return result

    def _points_to_pixel_coords(
        self,
        mobject: Mobject,
        points: Point3D_Array,
    ) -> np.ndarray:
        return self._points_to_subpixel_coords(mobject, points).astype(np.int64)

    def _on_screen_pixels(self, pixel_coords: np.ndarray) -> np.ndarray:
        settings = self.target.settings
        return reduce(
            op.and_,
            [
                pixel_coords[:, 0] >= 0,
                pixel_coords[:, 0] < settings.pixel_width,
                pixel_coords[:, 1] >= 0,
                pixel_coords[:, 1] < settings.pixel_height,
            ],
        )

    def _adjusted_thickness(self, thickness: float) -> float:
        settings = self.target.settings
        base_sum = settings.base_pixel_height + settings.base_pixel_width
        target_sum = settings.pixel_height + settings.pixel_width
        return 1 + (thickness - 1) * base_sum / target_sum

    @staticmethod
    def _thickened_coordinates(
        pixel_coords: np.ndarray,
        thickness: float,
    ) -> np.ndarray:
        thickness = int(thickness)
        coordinate_range = list(
            range(-thickness // 2 + 1, thickness // 2 + 1),
        )
        nudges = np.array(list(it.product(coordinate_range, coordinate_range)))
        thickened = np.array([pixel_coords + nudge for nudge in nudges])
        return thickened.reshape((thickened.size // 2, 2))
