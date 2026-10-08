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

/* Return 1 when the generated XSA contains tiny_face_accel_0 and a box was
 * decoded, 0 when no face is above the threshold, and a negative value when
 * the application was built against the old HDMI-only XSA. */
int tiny_face_infer(const u8 *frame, u32 width, u32 height, u32 stride,
			   TinyFaceBox *box);

#endif /* TINY_FACE_RUNTIME_H_ */
