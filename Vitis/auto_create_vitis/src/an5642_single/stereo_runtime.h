#ifndef STEREO_RUNTIME_H_
#define STEREO_RUNTIME_H_

#include "tiny_face_runtime.h"
#include "xil_types.h"

typedef struct {
	float disparity_px;
	float vertical_error_px;
	u32 distance_dm;
} StereoFaceDistance;

/* Camera1 is the first calibration image and Camera2 is the second. */
int stereo_face_distance(const TinyFaceBox *camera1_box,
	const TinyFaceBox *camera2_box, StereoFaceDistance *result);

#endif /* STEREO_RUNTIME_H_ */
