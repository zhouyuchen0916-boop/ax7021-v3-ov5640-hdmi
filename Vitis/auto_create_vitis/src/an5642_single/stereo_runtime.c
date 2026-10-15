#include "stereo_runtime.h"

#include <math.h>
#include <stddef.h>

#include "stereo_calibration_params.h"

#define STEREO_MAX_VERTICAL_ERROR_PX 60.0f
#define STEREO_MIN_DISPARITY_PX 4.0f
#define STEREO_MAX_DISPARITY_PX 400.0f

static void rectify_point(float pixel_x, float pixel_y, const float k[9],
	const float d[5], const float r[9], float *rectified_x,
	float *rectified_y)
{
	float distorted_x = (pixel_x - k[2]) / k[0];
	float distorted_y = (pixel_y - k[5]) / k[4];
	float x = distorted_x;
	float y = distorted_y;
	u32 iteration;

	/* Invert OpenCV's five-coefficient radial/tangential model. */
	for (iteration = 0U; iteration < 5U; ++iteration) {
		float x2 = x * x;
		float y2 = y * y;
		float radius2 = x2 + y2;
		float radial = 1.0f + d[0] * radius2 +
			d[1] * radius2 * radius2 + d[4] * radius2 * radius2 * radius2;
		float delta_x = 2.0f * d[2] * x * y + d[3] * (radius2 + 2.0f * x2);
		float delta_y = d[2] * (radius2 + 2.0f * y2) + 2.0f * d[3] * x * y;
		if (fabsf(radial) < 1.0e-6f) break;
		x = (distorted_x - delta_x) / radial;
		y = (distorted_y - delta_y) / radial;
	}

	{
		float rx = r[0] * x + r[1] * y + r[2];
		float ry = r[3] * x + r[4] * y + r[5];
		float rz = r[6] * x + r[7] * y + r[8];
		if (fabsf(rz) < 1.0e-6f) rz = rz < 0.0f ? -1.0e-6f : 1.0e-6f;
		*rectified_x = STEREO_RECTIFIED_FOCAL_PX * (rx / rz) +
			STEREO_RECTIFIED_CX;
		*rectified_y = STEREO_RECTIFIED_FOCAL_PX * (ry / rz) +
			STEREO_RECTIFIED_CY;
	}
}

int stereo_face_distance(const TinyFaceBox *camera1_box,
	const TinyFaceBox *camera2_box, StereoFaceDistance *result)
{
	float camera1_x;
	float camera1_y;
	float camera2_x;
	float camera2_y;
	float rectified1_x;
	float rectified1_y;
	float rectified2_x;
	float rectified2_y;
	float disparity;
	float vertical_error;
	float distance_mm;
	u32 distance_dm;

	if (camera1_box == NULL || camera2_box == NULL || result == NULL ||
		!camera1_box->valid || !camera2_box->valid) {
		return 0;
	}
	camera1_x = 0.5f * (float)(camera1_box->x_min + camera1_box->x_max);
	camera1_y = 0.5f * (float)(camera1_box->y_min + camera1_box->y_max);
	camera2_x = 0.5f * (float)(camera2_box->x_min + camera2_box->x_max);
	camera2_y = 0.5f * (float)(camera2_box->y_min + camera2_box->y_max);

	rectify_point(camera1_x, camera1_y, STEREO_CAMERA1_K,
		STEREO_CAMERA1_D, STEREO_CAMERA1_R, &rectified1_x, &rectified1_y);
	rectify_point(camera2_x, camera2_y, STEREO_CAMERA2_K,
		STEREO_CAMERA2_D, STEREO_CAMERA2_R, &rectified2_x, &rectified2_y);
	disparity = fabsf(rectified1_x - rectified2_x);
	vertical_error = fabsf(rectified1_y - rectified2_y);
	if (disparity < STEREO_MIN_DISPARITY_PX ||
		disparity > STEREO_MAX_DISPARITY_PX ||
		vertical_error > STEREO_MAX_VERTICAL_ERROR_PX) {
		return 0;
	}

	distance_mm = (STEREO_RECTIFIED_FOCAL_PX * STEREO_BASELINE_MM) /
		disparity;
	distance_dm = (u32)(distance_mm / 100.0f + 0.5f);
	if (distance_dm < 3U) distance_dm = 3U;
	if (distance_dm > 99U) distance_dm = 99U;
	result->disparity_px = disparity;
	result->vertical_error_px = vertical_error;
	result->distance_dm = distance_dm;
	return 1;
}
