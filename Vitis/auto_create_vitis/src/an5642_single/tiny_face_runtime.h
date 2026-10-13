#ifndef TINY_FACE_RUNTIME_H_
#define TINY_FACE_RUNTIME_H_

#include "xil_types.h"

typedef struct {
	int valid;
	u32 x_min;
	u32 y_min;
	u32 x_max;
	u32 y_max;
	float score;
} TinyFaceBox;

/* Return the number of decoded faces, 0 when no face is above the threshold,
 * and a negative value on an accelerator/runtime error. Detections are sorted
 * by confidence and filtered with NMS before they are returned. */
int tiny_face_infer(const u8 *frame, u32 width, u32 height, u32 stride,
			   TinyFaceBox *boxes, u32 max_boxes);

#endif /* TINY_FACE_RUNTIME_H_ */
