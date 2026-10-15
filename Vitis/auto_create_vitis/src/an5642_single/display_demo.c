/************************************************************************/
/*																		*/
/*	display_demo.c	--	ALINX AX7010 HDMI Display demonstration 						*/
/*																		*/
/************************************************************************/

/* ------------------------------------------------------------ */
/*				Include File Definitions						*/
/* ------------------------------------------------------------ */

#include "display_demo.h"
#include "display_ctrl/display_ctrl.h"
#include <stdio.h>
#include "math.h"
#include <ctype.h>
#include <stdlib.h>
#include <string.h>
#include "xil_types.h"
#include "xil_cache.h"
#include "xil_io.h"
#include "xparameters.h"
#include "xiicps.h"
#include "vdma.h"
#include "i2c/PS_i2c.h"
#include "xgpio.h"
#include "sleep.h"
#include "ov5640.h"
#include "xil_printf.h"
#include "xuartps_hw.h"
#include "xtime_l.h"
#include "tiny_face_runtime.h"
#include "stereo_runtime.h"
/*
 * XPAR redefines
 */
#define DYNCLK_BASEADDR XPAR_AXI_DYNCLK_0_BASEADDR
#define VGA_VDMA_ID XPAR_AXIVDMA_0_DEVICE_ID
#define CAMERA2_VDMA_ID XPAR_AXIVDMA_1_DEVICE_ID
#define CAMERA1_VDMA_ID XPAR_AXIVDMA_2_DEVICE_ID
#define CAMERA2_WRITE_CHANNEL 0U
#define CAMERA1_WRITE_CHANNEL 1U
#define DISP_VTC_ID XPAR_VTC_0_DEVICE_ID
#define VID_VTC_IRPT_ID XPS_FPGA3_INT_ID
#define VID_GPIO_IRPT_ID XPS_FPGA4_INT_ID
#define SCU_TIMER_ID XPAR_SCUTIMER_DEVICE_ID
#define UART0_BASEADDR XPAR_PS7_UART_0_BASEADDR
#define UART1_BASEADDR XPAR_PS7_UART_1_BASEADDR
#define BBOX_ENABLE_MASK 0x80000000U
#define BBOX_PACK(minimum, maximum) \
	((((u32)(maximum) & 0x0FFFU) << 16) | ((u32)(minimum) & 0x0FFFU))
#define BBOX_PACK_Y(minimum, maximum, distance_dm) \
	(BBOX_PACK((minimum), (maximum)) | \
	 ((((u32)(distance_dm) % 10U) & 0x0FU) << 12) | \
	 (((((u32)(distance_dm) / 10U)) & 0x0FU) << 28))
#define BBOX_CTRL0_BASEADDR 0x41220000U
#define BBOX_CTRL1_BASEADDR 0x41230000U
#define BBOX_CTRL2_BASEADDR 0x41240000U
#define AXI_GPIO_DATA_OFFSET 0x00U
#define AXI_GPIO_TRI_OFFSET 0x04U
#define AXI_GPIO2_DATA_OFFSET 0x08U
#define AXI_GPIO2_TRI_OFFSET 0x0CU
#define MAX_FACE_BOXES 3U
#define FACE_DISTANCE_SCALE_DM_PIXELS 2100U
#define FACE_CONFIRM_FRAMES 4U
#define FACE_CONFIRM_IOU_PERMILLE 450U
#define FACE_TRACK_IOU_PERMILLE 200U
#define FACE_CONFIRM_SCORE_PERMILLE 930U
#define FACE_HOLD_MISSES 5U
#define STEREO_DISTANCE_WINDOW 5U
#define STEREO_CONFIRM_SAMPLES 3U
#define STEREO_HOLD_MISSES 12U

typedef struct {
	TinyFaceBox displayed;
	TinyFaceBox pending;
	u32 pending_count;
	u32 pending_score_sum;
	u32 missed_count;
	u32 stereo_distance_dm;
	u32 stereo_samples_dm[STEREO_DISTANCE_WINDOW];
	u32 stereo_sample_count;
	u32 stereo_sample_index;
	u32 stereo_missed_count;
	int stereo_valid;
	int visible;
} FaceTracker;

static void face_tracker_clear_stereo(FaceTracker *tracker)
{
	tracker->stereo_distance_dm = 0U;
	memset(tracker->stereo_samples_dm, 0,
		sizeof(tracker->stereo_samples_dm));
	tracker->stereo_sample_count = 0U;
	tracker->stereo_sample_index = 0U;
	tracker->stereo_missed_count = 0U;
	tracker->stereo_valid = 0;
}


/* ------------------------------------------------------------ */
/*				Global Variables								*/
/* ------------------------------------------------------------ */

/*
 * Display Driver structs
 */
DisplayCtrl dispCtrl;
XAxiVdma vdma;
XIicPs ps_i2c0;
XIicPs ps_i2c1;
XGpio hdmi_rstn;
XGpio cmos_rstn;
volatile u32 g_diag_magic = 0xA7021D1AU;
volatile u32 g_diag_stage = 0U;
volatile s32 g_diag_status = 0;
volatile u32 g_ov5640_id = 0U;
volatile u32 g_ov5640_camera1_id = 0U;
/*
 * Framebuffers for video data
 */
/* Large video buffers must not be included in the C runtime BSS clear.
 * The standalone Cortex-A9 startup code places its mode stacks below the
 * linker-provided stack symbol; a multi-megabyte BSS would overwrite them
 * before main().  The buffers are explicitly cleared in display_init(). */
u8 frameBuf[DISPLAY_NUM_FRAMES][DEMO_MAX_FRAME]
    __attribute__ ((section(".noinit"), aligned(64)));
u8 *pFrames[DISPLAY_NUM_FRAMES]; //array of pointers to the frame buffers
u8 camera1FrameBuf[DISPLAY_NUM_FRAMES][DEMO_MAX_FRAME]
    __attribute__ ((section(".noinit"), aligned(64)));
u8 *camera1Frames[DISPLAY_NUM_FRAMES];
u8 camera2FrameBuf[DISPLAY_NUM_FRAMES][DEMO_MAX_FRAME]
    __attribute__ ((section(".noinit"), aligned(64)));
u8 *camera2Frames[DISPLAY_NUM_FRAMES];

/* ------------------------------------------------------------ */
/*				Procedure Definitions							*/
/* ------------------------------------------------------------ */

static void diag_flush(void)
{
	Xil_DCacheFlushRange((INTPTR)&g_ov5640_id, 64U);
}

static u32 face_score_permille(float score)
{
	if (score <= 0.0f) {
		return 0U;
	}
	if (score >= 1.0f) {
		return 1000U;
	}
	return (u32)(score * 1000.0f + 0.5f);
}

static int face_box_geometry_valid(const TinyFaceBox *box)
{
	u32 width;
	u32 height;

	if (box == NULL || !box->valid || box->x_max <= box->x_min ||
		box->y_max <= box->y_min || box->x_max > 1280U ||
		box->y_max > 720U) {
		return 0;
	}
	width = box->x_max - box->x_min;
	height = box->y_max - box->y_min;
	/* Reject tiny grid noise and extremely flat/tall regions.  The limits are
	 * deliberately broad so that normal head rotation remains detectable. */
	if (width < 32U || height < 32U || width * 100U < height * 55U ||
		width * 100U > height * 180U) {
		return 0;
	}
	return 1;
}

static u32 face_box_iou_permille(const TinyFaceBox *first,
	const TinyFaceBox *second)
{
	u32 left = first->x_min > second->x_min ? first->x_min : second->x_min;
	u32 top = first->y_min > second->y_min ? first->y_min : second->y_min;
	u32 right = first->x_max < second->x_max ? first->x_max : second->x_max;
	u32 bottom = first->y_max < second->y_max ? first->y_max : second->y_max;
	u64 intersection = 0U;
	u64 first_area;
	u64 second_area;
	u64 union_area;

	if (right > left && bottom > top) {
		intersection = (u64)(right - left) * (u64)(bottom - top);
	}
	first_area = (u64)(first->x_max - first->x_min) *
		(u64)(first->y_max - first->y_min);
	second_area = (u64)(second->x_max - second->x_min) *
		(u64)(second->y_max - second->y_min);
	union_area = first_area + second_area - intersection;
	return union_area == 0U ? 0U : (u32)((intersection * 1000U) / union_area);
}

static void face_box_smooth(TinyFaceBox *filtered, const TinyFaceBox *sample)
{
	/* One-quarter new position suppresses quantized grid jitter while still
	 * following ordinary head motion in a few detector updates. */
	filtered->x_min = (3U * filtered->x_min + sample->x_min + 2U) / 4U;
	filtered->y_min = (3U * filtered->y_min + sample->y_min + 2U) / 4U;
	filtered->x_max = (3U * filtered->x_max + sample->x_max + 2U) / 4U;
	filtered->y_max = (3U * filtered->y_max + sample->y_max + 2U) / 4U;
	filtered->score = sample->score;
	filtered->valid = 1;
}

static int face_tracker_update(FaceTracker *tracker,
	const TinyFaceBox *candidate)
{
	u32 candidate_score;
	int candidate_valid = face_box_geometry_valid(candidate);

	if (!candidate_valid) {
		tracker->pending_count = 0U;
		tracker->pending_score_sum = 0U;
		if (tracker->visible && ++tracker->missed_count <= FACE_HOLD_MISSES) {
			return 1;
		}
		tracker->visible = 0;
		face_tracker_clear_stereo(tracker);
		tracker->missed_count = 0U;
		return 0;
	}

	candidate_score = face_score_permille(candidate->score);
	if (tracker->visible &&
		face_box_iou_permille(&tracker->displayed, candidate) >=
		FACE_TRACK_IOU_PERMILLE) {
		face_box_smooth(&tracker->displayed, candidate);
		tracker->missed_count = 0U;
		tracker->pending_count = 0U;
		tracker->pending_score_sum = 0U;
		return 1;
	}

	if (tracker->pending_count > 0U &&
		face_box_iou_permille(&tracker->pending, candidate) >=
		FACE_CONFIRM_IOU_PERMILLE) {
		face_box_smooth(&tracker->pending, candidate);
		++tracker->pending_count;
		tracker->pending_score_sum += candidate_score;
	} else {
		tracker->pending = *candidate;
		tracker->pending_count = 1U;
		tracker->pending_score_sum = candidate_score;
	}

	if (tracker->pending_count >= FACE_CONFIRM_FRAMES &&
		tracker->pending_score_sum >=
		FACE_CONFIRM_FRAMES * FACE_CONFIRM_SCORE_PERMILLE) {
		face_tracker_clear_stereo(tracker);
		tracker->displayed = tracker->pending;
		tracker->visible = 1;
		tracker->missed_count = 0U;
		tracker->pending_count = 0U;
		tracker->pending_score_sum = 0U;
		return 1;
	}

	if (tracker->visible && ++tracker->missed_count <= FACE_HOLD_MISSES) {
		return 1;
	}
	tracker->visible = 0;
	face_tracker_clear_stereo(tracker);
	tracker->missed_count = 0U;
	return 0;
}

static u32 face_distance_dm(const TinyFaceBox *box)
{
	u32 box_height;
	u32 distance_dm;

	if (!face_box_geometry_valid(box)) {
		return 0U;
	}
	box_height = box->y_max - box->y_min;
	/* Approximate pinhole-camera distance.  The 2100 dm*pixel constant is a
	 * practical starting point for the AN5642 3.6 mm lens at 1280x720 and can
	 * be calibrated later with one measured reference distance. */
	distance_dm = (FACE_DISTANCE_SCALE_DM_PIXELS + box_height / 2U) /
		box_height;
	if (distance_dm < 3U) distance_dm = 3U;
	if (distance_dm > 99U) distance_dm = 99U;
	return distance_dm;
}

static u32 bbox_ctrl_base(u32 slot)
{
	static const u32 bases[MAX_FACE_BOXES] = {
		BBOX_CTRL0_BASEADDR, BBOX_CTRL1_BASEADDR, BBOX_CTRL2_BASEADDR
	};
	return bases[slot < MAX_FACE_BOXES ? slot : 0U];
}

static void bbox_ctrl_initialize(void)
{
	u32 slot;
	for (slot = 0U; slot < MAX_FACE_BOXES; ++slot) {
		u32 base = bbox_ctrl_base(slot);
		Xil_Out32(base + AXI_GPIO_TRI_OFFSET, 0U);
		Xil_Out32(base + AXI_GPIO2_TRI_OFFSET, 0U);
		Xil_Out32(base + AXI_GPIO_DATA_OFFSET, 0U);
		Xil_Out32(base + AXI_GPIO2_DATA_OFFSET, 0U);
	}
}

static void bbox_write_all(const FaceTracker trackers[MAX_FACE_BOXES])
{
	u32 slot;

	/* Disable every slot before changing coordinates so the video-clock
	 * domain can only latch either the previous complete set or the new one. */
	for (slot = 0U; slot < MAX_FACE_BOXES; ++slot) {
		Xil_Out32(bbox_ctrl_base(slot) + AXI_GPIO_DATA_OFFSET, 0U);
	}
	for (slot = 0U; slot < MAX_FACE_BOXES; ++slot) {
		const TinyFaceBox *box = &trackers[slot].displayed;
		u32 base = bbox_ctrl_base(slot);
		if (trackers[slot].visible && face_box_geometry_valid(box)) {
			u32 distance_dm = trackers[slot].stereo_valid ?
				trackers[slot].stereo_distance_dm : face_distance_dm(box);
			u32 box_height = box->y_max - box->y_min;
			u32 expanded_y_max = box->y_max + (box_height + 9U) / 10U;
			u32 display_x_min = 640U + box->x_min / 2U;
			u32 display_x_max = 640U + box->x_max / 2U;
			u32 display_y_min = 180U + box->y_min / 2U;
			if (expanded_y_max > 719U) expanded_y_max = 719U;
			u32 display_y_max = 180U + expanded_y_max / 2U;
			Xil_Out32(base + AXI_GPIO2_DATA_OFFSET,
				BBOX_PACK_Y(display_y_min, display_y_max, distance_dm));
			Xil_Out32(base + AXI_GPIO_DATA_OFFSET,
				BBOX_ENABLE_MASK | BBOX_PACK(display_x_min, display_x_max));
		} else {
			Xil_Out32(base + AXI_GPIO2_DATA_OFFSET, 0U);
		}
	}
}

static void compose_stereo_frame(u8 *destination, const u8 *camera1,
	const u8 *camera2)
{
	u32 y;

	/* Reduce both dimensions by 2:1 so each 16:9 source keeps its aspect
	 * ratio as a 640x360 preview.  The two previews are centered vertically
	 * in the 1280x720 output; the untouched top and bottom bands stay black. */
	Xil_DCacheInvalidateRange((INTPTR)camera1, DEMO_MAX_FRAME);
	Xil_DCacheInvalidateRange((INTPTR)camera2, DEMO_MAX_FRAME);
	for (y = 0U; y < 360U; ++y) {
		const u8 *left_line = camera1 + (y * 2U) * DEMO_STRIDE;
		const u8 *right_line = camera2 + (y * 2U) * DEMO_STRIDE;
		u8 *output_line = destination + (y + 180U) * DEMO_STRIDE;
		u32 x;
		for (x = 0U; x < 640U; ++x) {
			u32 source_offset = (x * 2U) * 3U;
			u32 left_offset = x * 3U;
			u32 right_offset = (x + 640U) * 3U;
			output_line[left_offset] = left_line[source_offset];
			output_line[left_offset + 1U] = left_line[source_offset + 1U];
			output_line[left_offset + 2U] = left_line[source_offset + 2U];
			output_line[right_offset] = right_line[source_offset];
			output_line[right_offset + 1U] = right_line[source_offset + 1U];
			output_line[right_offset + 2U] = right_line[source_offset + 2U];
		}
	}
	Xil_DCacheFlushRange((INTPTR)destination, DEMO_MAX_FRAME);
}

static void face_trackers_update(FaceTracker trackers[MAX_FACE_BOXES],
	const TinyFaceBox detections[MAX_FACE_BOXES], u32 detection_count)
{
	int assignment[MAX_FACE_BOXES] = {-1, -1, -1};
	int used[MAX_FACE_BOXES] = {0, 0, 0};
	u32 tracker_index;
	u32 detection_index;

	/* Keep an already-visible face attached to the closest overlapping
	 * detection even when confidence ordering changes between two people. */
	for (tracker_index = 0U; tracker_index < MAX_FACE_BOXES; ++tracker_index) {
		u32 best_iou = FACE_TRACK_IOU_PERMILLE;
		if (!trackers[tracker_index].visible) continue;
		for (detection_index = 0U; detection_index < detection_count;
			++detection_index) {
			u32 iou;
			if (used[detection_index] ||
				!face_box_geometry_valid(&detections[detection_index])) continue;
			iou = face_box_iou_permille(&trackers[tracker_index].displayed,
				&detections[detection_index]);
			if (iou >= best_iou) {
				best_iou = iou;
				assignment[tracker_index] = (int)detection_index;
			}
		}
		if (assignment[tracker_index] >= 0)
			used[assignment[tracker_index]] = 1;
	}

	/* Continue pending confirmations before opening a new tracker slot. */
	for (tracker_index = 0U; tracker_index < MAX_FACE_BOXES; ++tracker_index) {
		u32 best_iou = FACE_CONFIRM_IOU_PERMILLE;
		if (trackers[tracker_index].visible ||
			trackers[tracker_index].pending_count == 0U) continue;
		for (detection_index = 0U; detection_index < detection_count;
			++detection_index) {
			u32 iou;
			if (used[detection_index] ||
				!face_box_geometry_valid(&detections[detection_index])) continue;
			iou = face_box_iou_permille(&trackers[tracker_index].pending,
				&detections[detection_index]);
			if (iou >= best_iou) {
				best_iou = iou;
				assignment[tracker_index] = (int)detection_index;
			}
		}
		if (assignment[tracker_index] >= 0)
			used[assignment[tracker_index]] = 1;
	}

	for (detection_index = 0U; detection_index < detection_count;
		++detection_index) {
		if (used[detection_index] ||
			!face_box_geometry_valid(&detections[detection_index])) continue;
		for (tracker_index = 0U; tracker_index < MAX_FACE_BOXES;
			++tracker_index) {
			if (!trackers[tracker_index].visible &&
				trackers[tracker_index].pending_count == 0U &&
				assignment[tracker_index] < 0) {
				assignment[tracker_index] = (int)detection_index;
				used[detection_index] = 1;
				break;
			}
		}
	}

	for (tracker_index = 0U; tracker_index < MAX_FACE_BOXES; ++tracker_index) {
		const TinyFaceBox *candidate = assignment[tracker_index] >= 0 ?
			&detections[assignment[tracker_index]] : NULL;
		(void)face_tracker_update(&trackers[tracker_index], candidate);
	}
}

static void face_trackers_update_stereo(
	FaceTracker trackers[MAX_FACE_BOXES],
	const TinyFaceBox camera1_detections[MAX_FACE_BOXES],
	u32 camera1_detection_count)
{
	int camera1_used[MAX_FACE_BOXES] = {0, 0, 0};
	u32 tracker_index;

	/* Face-box centers are quantized by the small detector grid.  A median of
	 * the latest five stereo estimates rejects one-frame center jumps before
	 * they reach the on-screen distance label. */
	#define SORT_SWAP(a, b) do { \
		if ((a) > (b)) { u32 temporary = (a); (a) = (b); (b) = temporary; } \
	} while (0)

	for (tracker_index = 0U; tracker_index < MAX_FACE_BOXES;
		++tracker_index) {
		int best_index = -1;
		float best_cost = 1.0e9f;
		StereoFaceDistance best_result;
		u32 candidate_index;

		if (!trackers[tracker_index].visible) {
			face_tracker_clear_stereo(&trackers[tracker_index]);
			continue;
		}
		for (candidate_index = 0U;
			candidate_index < camera1_detection_count;
			++candidate_index) {
			const TinyFaceBox *camera1_box =
				&camera1_detections[candidate_index];
			const TinyFaceBox *camera2_box =
				&trackers[tracker_index].displayed;
			u32 camera1_height;
			u32 camera2_height;
			u32 height_difference;
			float cost;
			StereoFaceDistance result;

			if (camera1_used[candidate_index] ||
				!face_box_geometry_valid(camera1_box)) continue;
			camera1_height = camera1_box->y_max - camera1_box->y_min;
			camera2_height = camera2_box->y_max - camera2_box->y_min;
			if (camera1_height * 2U < camera2_height ||
				camera2_height * 2U < camera1_height) continue;
			if (!stereo_face_distance(camera1_box, camera2_box, &result))
				continue;
			height_difference = camera1_height > camera2_height ?
				camera1_height - camera2_height :
				camera2_height - camera1_height;
			cost = result.vertical_error_px * 4.0f +
				(float)height_difference;
			if (cost < best_cost) {
				best_cost = cost;
				best_index = (int)candidate_index;
				best_result = result;
			}
		}

		if (best_index >= 0) {
			u32 fallback_distance = face_distance_dm(
				&trackers[tracker_index].displayed);
			u32 sorted[STEREO_DISTANCE_WINDOW];
			u32 sorted_count;
			u32 first;
			u32 second;

			/* Reject a center-disparity result that is grossly inconsistent
			 * with the observed face size.  The size estimate is coarse, but a
			 * 2:1 gate removes false cross-camera pairings and grid outliers. */
			if (best_result.distance_dm * 2U < fallback_distance ||
				best_result.distance_dm > fallback_distance * 2U) {
				best_index = -1;
			} else {
				trackers[tracker_index].stereo_samples_dm[
					trackers[tracker_index].stereo_sample_index] =
					best_result.distance_dm;
				trackers[tracker_index].stereo_sample_index =
					(trackers[tracker_index].stereo_sample_index + 1U) %
					STEREO_DISTANCE_WINDOW;
				if (trackers[tracker_index].stereo_sample_count <
					STEREO_DISTANCE_WINDOW) {
					++trackers[tracker_index].stereo_sample_count;
				}
			}
			if (best_index < 0) {
				if (trackers[tracker_index].stereo_valid &&
					++trackers[tracker_index].stereo_missed_count >
					STEREO_HOLD_MISSES) {
					face_tracker_clear_stereo(&trackers[tracker_index]);
				}
				continue;
			}
			camera1_used[best_index] = 1;
			sorted_count = trackers[tracker_index].stereo_sample_count;
			for (first = 0U; first < sorted_count; ++first) {
				sorted[first] = trackers[tracker_index].stereo_samples_dm[first];
			}
			for (first = 0U; first < sorted_count; ++first) {
				for (second = first + 1U; second < sorted_count; ++second) {
					SORT_SWAP(sorted[first], sorted[second]);
				}
			}
			if (trackers[tracker_index].stereo_valid) {
				u32 median = sorted[sorted_count / 2U];
				trackers[tracker_index].stereo_distance_dm =
					(3U * trackers[tracker_index].stereo_distance_dm +
					 median + 2U) / 4U;
			} else if (sorted_count >= STEREO_CONFIRM_SAMPLES) {
				trackers[tracker_index].stereo_distance_dm =
					sorted[sorted_count / 2U];
				trackers[tracker_index].stereo_valid = 1;
			}
			trackers[tracker_index].stereo_missed_count = 0U;
		} else if (trackers[tracker_index].stereo_valid &&
			++trackers[tracker_index].stereo_missed_count >
			STEREO_HOLD_MISSES) {
			face_tracker_clear_stereo(&trackers[tracker_index]);
		}
	}
	#undef SORT_SWAP
}

/* Wait for a real S2MM frame boundary.  Sampling immediately after the
 * pointer advances guarantees that (current - 1) is the frame that has just
 * completed, leaving two full frame periods before it can be overwritten. */
static int wait_for_write_frame_advance(u32 channel, u32 *writing_frame)
{
	u32 start_frame = vdma_write_current_frame(channel);
	u32 elapsed_us;

	if (writing_frame == NULL || start_frame >= DISPLAY_NUM_FRAMES) {
		return XST_FAILURE;
	}
	for (elapsed_us = 0U; elapsed_us < 200000U; elapsed_us += 500U) {
		u32 errors = vdma_write_errors(channel);
		u32 current_frame;

		if (errors != 0U) {
			vdma_write_clear_errors(channel, errors);
			start_frame = vdma_write_current_frame(channel);
		}
		current_frame = vdma_write_current_frame(channel);
		if (current_frame < DISPLAY_NUM_FRAMES &&
			current_frame != start_frame) {
			*writing_frame = current_frame;
			return XST_SUCCESS;
		}
		usleep(500);
	}
	return XST_FAILURE;
}

/* Mirror xil_printf output to both AX7021 V3.0 USB-UART ports. */
void outbyte(char c)
{
	XUartPs_SendByte(UART0_BASEADDR, (u8)c);
	XUartPs_SendByte(UART1_BASEADDR, (u8)c);
}



int main(void)
{

	int Status;
	XAxiVdma_Config *vdmaConfig;
	int i;
	u8 chip_id_high;
	u8 chip_id_low;

	/* Standalone 2023.1 usleep() uses the SCU global timer.  The bare-JTAG
	 * launch path does not run an FSBL, so enable/reset that counter here. */
	XTime_SetTime(0U);

	g_diag_stage = 0x10U;
	diag_flush();
	xil_printf("\r\nAX7021 AN5642 dual-camera capture demo start\r\n");
	g_diag_stage = 0x11U;

	/*
	 * Initialize an array of pointers to the 3 frame buffers
	 */
	for (i = 0; i < DISPLAY_NUM_FRAMES; i++)
	{
		g_diag_stage = 0x20U + (u32)i;
		pFrames[i] = frameBuf[i];
		camera1Frames[i] = camera1FrameBuf[i];
		camera2Frames[i] = camera2FrameBuf[i];
		memset(pFrames[i], 0, DEMO_MAX_FRAME);
		memset(camera1Frames[i], 0, DEMO_MAX_FRAME);
		memset(camera2Frames[i], 0, DEMO_MAX_FRAME);
		Xil_DCacheFlushRange((INTPTR) pFrames[i], DEMO_MAX_FRAME) ;
		Xil_DCacheFlushRange((INTPTR) camera1Frames[i], DEMO_MAX_FRAME);
		Xil_DCacheFlushRange((INTPTR) camera2Frames[i], DEMO_MAX_FRAME);
		g_diag_stage = 0x30U + (u32)i;
	}
	xil_printf("DISPLAY buffers: 0x%x 0x%x 0x%x\r\n",
		(u32)pFrames[0], (u32)pFrames[1], (u32)pFrames[2]);
	xil_printf("CAMERA1 buffers: 0x%x 0x%x 0x%x\r\n",
		(u32)camera1Frames[0], (u32)camera1Frames[1],
		(u32)camera1Frames[2]);
	xil_printf("CAMERA2 buffers: 0x%x 0x%x 0x%x\r\n",
		(u32)camera2Frames[0], (u32)camera2Frames[1],
		(u32)camera2Frames[2]);

	g_diag_stage = 0x40U;
	Status = i2c_init(&ps_i2c0, XPAR_XIICPS_0_DEVICE_ID,40000);
	if (Status != XST_SUCCESS) {
		g_diag_status = Status;
		g_diag_stage = 0xE001U;
		diag_flush();
		xil_printf("ERROR: PS I2C initialization failed (%d)\r\n", Status);
		return XST_FAILURE;
	}
	g_diag_stage = 0x41U;
	xil_printf("PS I2C0 camera1/HDMI ready at 40 kHz\r\n");

	Status = i2c_init(&ps_i2c1, XPAR_XIICPS_1_DEVICE_ID,40000);
	if (Status != XST_SUCCESS) {
		g_diag_status = Status;
		g_diag_stage = 0xE00BU;
		diag_flush();
		xil_printf("ERROR: PS I2C1 initialization failed (%d)\r\n", Status);
		return XST_FAILURE;
	}
	xil_printf("PS I2C1 camera2 ready at 40 kHz\r\n");

	Status = XGpio_Initialize(&hdmi_rstn, XPAR_HDMI_RST_DEVICE_ID);   //initialize GPIO IP
	if (Status != XST_SUCCESS) {
		g_diag_status = Status;
		g_diag_stage = 0xE002U;
		diag_flush();
		xil_printf("ERROR: HDMI reset GPIO initialization failed (%d)\r\n", Status);
		return XST_FAILURE;
	}
	XGpio_SetDataDirection(&hdmi_rstn, 1, 0x0);            //set GPIO as output
	XGpio_DiscreteWrite(&hdmi_rstn, 1, 0x0);               //set GPIO output value to 0

	Status = XGpio_Initialize(&cmos_rstn, XPAR_CMOS_RST_DEVICE_ID);   //initialize GPIO IP
	if (Status != XST_SUCCESS) {
		g_diag_status = Status;
		g_diag_stage = 0xE003U;
		diag_flush();
		xil_printf("ERROR: camera reset GPIO initialization failed (%d)\r\n", Status);
		return XST_FAILURE;
	}
	XGpio_SetDataDirection(&cmos_rstn, 1, 0x0);            //set GPIO as output

	/* Keep the overlay disabled until a face is confirmed across several
	 * consecutive frames.  The old fixed test box caused a false green box
	 * throughout the camera/VDMA startup delay. */
	bbox_ctrl_initialize();
	g_diag_stage = 0x50U;
	xil_printf("BBOX overlay: 3 faces, calibrated stereo distance labels enabled\r\n");

	XGpio_DiscreteWrite(&cmos_rstn, 1, 0x3);
	usleep(500000);
	XGpio_DiscreteWrite(&cmos_rstn, 1, 0x0);               //set GPIO output value to 0

	usleep(500000);
	XGpio_DiscreteWrite(&hdmi_rstn, 1, 0x1);
	XGpio_DiscreteWrite(&cmos_rstn, 1, 0x3);
	usleep(500000);
	Status = i2c_reg8_write(&ps_i2c0,0x72>>1,0x08,0x35);
	if (Status != XST_SUCCESS) {
		g_diag_status = Status;
		g_diag_stage = 0xE004U;
		diag_flush();
		xil_printf("ERROR: HDMI transmitter register write failed (%d)\r\n", Status);
		return XST_FAILURE;
	}
	Status = i2c_reg8_write(&ps_i2c0,0x7a>>1,0x2f,0x00);
	if (Status != XST_SUCCESS) {
		g_diag_status = Status;
		g_diag_stage = 0xE005U;
		diag_flush();
		xil_printf("ERROR: HDMI companion register write failed (%d)\r\n", Status);
		return XST_FAILURE;
	}
	/* Camera1 is connected to PS I2C0 through the board I2C extender. */
	g_diag_stage = 0x60U;
	Status = ov5640_read(&ps_i2c0, 0x300A, &chip_id_high);
	if (Status == XST_SUCCESS) {
		Status = ov5640_read(&ps_i2c0, 0x300B, &chip_id_low);
	}
	if (Status != XST_SUCCESS) {
		g_diag_status = Status;
		g_diag_stage = 0xE006U;
		diag_flush();
		xil_printf("ERROR: OV5640 camera1 chip ID read failed (%d)\r\n", Status);
		return XST_FAILURE;
	}
	g_ov5640_camera1_id = ((u32)chip_id_high << 8) | (u32)chip_id_low;
	xil_printf("OV5640 camera1 chip ID: 0x%x%x\r\n", chip_id_high, chip_id_low);
	if ((chip_id_high != 0x56U) || (chip_id_low != 0x40U)) {
		xil_printf("ERROR: unexpected camera1 chip ID\r\n");
		return XST_FAILURE;
	}
	Status = sensor_init(&ps_i2c0);
	if (Status != XST_SUCCESS) {
		xil_printf("ERROR: OV5640 camera1 register initialization failed (%d)\r\n",
			Status);
		return XST_FAILURE;
	}
	xil_printf("OV5640 camera1 configured for 1280x720 RGB output\r\n");

	/* Camera2 is connected directly to the independent PS I2C1 bus. */
	g_diag_stage = 0x62U;
	Status = ov5640_read(&ps_i2c1, 0x300A, &chip_id_high);
	if (Status == XST_SUCCESS) {
		Status = ov5640_read(&ps_i2c1, 0x300B, &chip_id_low);
	}
	if (Status != XST_SUCCESS) {
		g_diag_status = Status;
		g_diag_stage = 0xE006U;
		diag_flush();
		xil_printf("ERROR: OV5640 chip ID read failed (%d)\r\n", Status);
		return XST_FAILURE;
	}
	g_ov5640_id = ((u32)chip_id_high << 8) | (u32)chip_id_low;
	g_diag_stage = 0x61U;
	diag_flush();
	xil_printf("OV5640 camera2 chip ID: 0x%x%x\r\n", chip_id_high, chip_id_low);
	if ((chip_id_high != 0x56U) || (chip_id_low != 0x40U)) {
		g_diag_stage = 0xE007U;
		diag_flush();
		xil_printf("ERROR: unexpected camera chip ID\r\n");
		return XST_FAILURE;
	}
	Status = sensor_init(&ps_i2c1);
	if (Status != XST_SUCCESS) {
		g_diag_status = Status;
		g_diag_stage = 0xE008U;
		diag_flush();
		xil_printf("ERROR: OV5640 register initialization failed (%d)\r\n", Status);
		return XST_FAILURE;
	}
	g_diag_stage = 0x70U;
	xil_printf("OV5640 camera2 configured for 1280x720 RGB output\r\n");
	/*
	 * Initialize VDMA driver
	 */
	vdmaConfig = XAxiVdma_LookupConfig(VGA_VDMA_ID);
	if (!vdmaConfig)
	{
		g_diag_stage = 0xE009U;
		diag_flush();
		xil_printf("No video DMA found for ID %d\r\n", VGA_VDMA_ID);
		return XST_FAILURE;
	}
	Status = XAxiVdma_CfgInitialize(&vdma, vdmaConfig, vdmaConfig->BaseAddress);
	if (Status != XST_SUCCESS)
	{
		g_diag_status = Status;
		g_diag_stage = 0xE00AU;
		diag_flush();
		xil_printf("VDMA Configuration Initialization failed %d\r\n", Status);
		return XST_FAILURE;
	}

	/*
	 * Initialize the Display controller and start it
	 */
	Status = DisplayInitialize(&dispCtrl, &vdma, DISP_VTC_ID, DYNCLK_BASEADDR,pFrames, DEMO_STRIDE);
	if (Status != XST_SUCCESS)
	{
		g_diag_status = Status;
		g_diag_stage = 0xE00BU;
		diag_flush();
		xil_printf("Display Ctrl initialization failed during demo initialization%d\r\n", Status);
		return XST_FAILURE;
	}
	/* The preview is produced by software into its own three-frame display
	 * ring, so the read VDMA parks on the completed composition instead of
	 * following Camera2's write-frame pointer through GenLock. */
	dispCtrl.vdmaConfig.EnableSync = 0;
	Status = DisplayStart(&dispCtrl);
	if (Status != XST_SUCCESS)
	{
		g_diag_status = Status;
		g_diag_stage = 0xE00CU;
		diag_flush();
		xil_printf("Couldn't start display during demo initialization%d\r\n", Status);
		return XST_FAILURE;
	}
	/* Clear frame buffer */
	memset(dispCtrl.framePtr[dispCtrl.curFrame], 0, DEMO_MAX_FRAME);
	/* Start Sensor Vdma */
	Status = vdma_write_init(CAMERA2_WRITE_CHANNEL, CAMERA2_VDMA_ID,
		1280 * 3, 720,
		1280 * 3, camera2Frames, DISPLAY_NUM_FRAMES);
	if (Status != XST_SUCCESS) {
		g_diag_status = Status;
		g_diag_stage = 0xE00DU;
		diag_flush();
		xil_printf("ERROR: camera2 write VDMA failed (%d)\r\n", Status);
		return XST_FAILURE;
	}
	Status = vdma_write_init(CAMERA1_WRITE_CHANNEL, CAMERA1_VDMA_ID,
		1280 * 3, 720, 1280 * 3, camera1Frames, DISPLAY_NUM_FRAMES);
	if (Status != XST_SUCCESS) {
		g_diag_status = Status;
		g_diag_stage = 0xE00EU;
		diag_flush();
		xil_printf("ERROR: camera1 write VDMA failed (%d)\r\n", Status);
		return XST_FAILURE;
	}

	g_diag_stage = 0x900U;
	diag_flush();
	/* The camera bridge intentionally holds its FIFO in reset for several
	 * seconds after PCLK starts.  Wait until that hardware delay has elapsed
	 * and all circular buffers can contain a complete frame. */
	usleep(7000000);
	u32 camera2_startup_errors = vdma_write_errors(CAMERA2_WRITE_CHANNEL);
	u32 camera1_startup_errors = vdma_write_errors(CAMERA1_WRITE_CHANNEL);
	if (camera2_startup_errors != 0U) {
		xil_printf("CAMERA2 VDMA startup errors: 0x%x (clearing)\r\n",
			camera2_startup_errors);
		vdma_write_clear_errors(CAMERA2_WRITE_CHANNEL, camera2_startup_errors);
	}
	if (camera1_startup_errors != 0U) {
		xil_printf("CAMERA1 VDMA startup errors: 0x%x (clearing)\r\n",
			camera1_startup_errors);
		vdma_write_clear_errors(CAMERA1_WRITE_CHANNEL, camera1_startup_errors);
	}
	if (camera1_startup_errors != 0U || camera2_startup_errors != 0U) {
		usleep(50000);
		xil_printf("VDMA errors after clear: camera1=0x%x camera2=0x%x\r\n",
			vdma_write_errors(CAMERA1_WRITE_CHANNEL),
			vdma_write_errors(CAMERA2_WRITE_CHANNEL));
	}
	u32 camera1_seen_mask = 0U;
	u32 camera2_seen_mask = 0U;
	for (u32 probe = 0U; probe < 600U &&
		(camera1_seen_mask != 0x7U || camera2_seen_mask != 0x7U); ++probe) {
		u32 camera1_frame = vdma_write_current_frame(CAMERA1_WRITE_CHANNEL);
		u32 camera2_frame = vdma_write_current_frame(CAMERA2_WRITE_CHANNEL);
		if (camera1_frame < DISPLAY_NUM_FRAMES) {
			camera1_seen_mask |= 1U << camera1_frame;
		}
		if (camera2_frame < DISPLAY_NUM_FRAMES) {
			camera2_seen_mask |= 1U << camera2_frame;
		}
		usleep(5000);
	}
	if (camera1_seen_mask != 0x7U || camera2_seen_mask != 0x7U ||
		vdma_write_errors(CAMERA1_WRITE_CHANNEL) != 0U ||
		vdma_write_errors(CAMERA2_WRITE_CHANNEL) != 0U) {
		xil_printf("ERROR: dual VDMA self-test failed (cam1 seen=0x%x err=0x%x cam2 seen=0x%x err=0x%x)\r\n",
			camera1_seen_mask, vdma_write_errors(CAMERA1_WRITE_CHANNEL),
			camera2_seen_mask, vdma_write_errors(CAMERA2_WRITE_CHANNEL));
		return XST_FAILURE;
	}
	xil_printf("CAMERA1_FRAME_SYNC_READY: seen=0x%x current=f%d errors=0x%x\r\n",
		camera1_seen_mask, vdma_write_current_frame(CAMERA1_WRITE_CHANNEL),
		vdma_write_errors(CAMERA1_WRITE_CHANNEL));
	xil_printf("CAMERA2_FRAME_SYNC_READY: seen=0x%x current=f%d errors=0x%x\r\n",
		camera2_seen_mask, vdma_write_current_frame(CAMERA2_WRITE_CHANNEL),
		vdma_write_errors(CAMERA2_WRITE_CHANNEL));
	xil_printf("DUAL CAPTURE RUNNING: camera1 + camera2 -> independent DDR rings\r\n");
	xil_printf("STEREO PREVIEW: camera1 left | camera2 right, 640x360 each, aspect ratio preserved\r\n");
	u32 detector_iterations = 0U;
	u32 display_frame = 1U;
	int detector_error_reported = 0;
	FaceTracker face_trackers[MAX_FACE_BOXES];
	memset(face_trackers, 0, sizeof(face_trackers));
	while (1) {
		TinyFaceBox detected_boxes[MAX_FACE_BOXES];
		TinyFaceBox camera1_detected_boxes[MAX_FACE_BOXES];
		u32 writing_frame;
		u32 completed_frame;
		u32 camera1_writing_frame;
		u32 camera1_completed_frame;
		int detector_status;
		int camera1_detector_status;

		if (wait_for_write_frame_advance(CAMERA2_WRITE_CHANNEL,
			&writing_frame) != XST_SUCCESS) {
			xil_printf("ERROR: camera VDMA frame boundary timeout (err=0x%x)\r\n",
				vdma_write_errors(CAMERA2_WRITE_CHANNEL));
			break;
		}
		/* With three circular buffers, the previous index is fully written and
		 * remains untouched while the camera writes the next two buffers.
		 * Preprocessing copies it into the detector's private 160x120 input. */
		completed_frame = (writing_frame + DISPLAY_NUM_FRAMES - 1U) %
			DISPLAY_NUM_FRAMES;
		camera1_writing_frame = vdma_write_current_frame(CAMERA1_WRITE_CHANNEL);
		if (camera1_writing_frame >= DISPLAY_NUM_FRAMES) {
			xil_printf("ERROR: camera1 frame pointer invalid (f%d)\r\n",
				camera1_writing_frame);
			break;
		}
		camera1_completed_frame = (camera1_writing_frame +
			DISPLAY_NUM_FRAMES - 1U) % DISPLAY_NUM_FRAMES;
		if (detector_iterations < 12U) {
			xil_printf("FRAME_SYNC: cam1=f%d cam2=f%d inference=f%d display=f%d\r\n",
				camera1_writing_frame, writing_frame, completed_frame,
				display_frame);
		}
		compose_stereo_frame(dispCtrl.framePtr[display_frame],
			camera1Frames[camera1_completed_frame],
			camera2Frames[completed_frame]);
		if (DisplayChangeFrame(&dispCtrl, display_frame) != XST_SUCCESS) {
			xil_printf("ERROR: stereo display frame switch failed\r\n");
			break;
		}
		display_frame = (display_frame + 1U) % DISPLAY_NUM_FRAMES;
		detector_status = tiny_face_infer(camera2Frames[completed_frame],
				1280U, 720U, DEMO_STRIDE, detected_boxes, MAX_FACE_BOXES);
		camera1_detector_status = tiny_face_infer(
			camera1Frames[camera1_completed_frame], 1280U, 720U,
			DEMO_STRIDE, camera1_detected_boxes, MAX_FACE_BOXES);
		++detector_iterations;
		if (detector_status >= 0) {
			u32 slot;
			u32 visible_count = 0U;
			face_trackers_update(face_trackers, detected_boxes,
				(u32)detector_status);
			if (camera1_detector_status >= 0) {
				face_trackers_update_stereo(face_trackers,
					camera1_detected_boxes, (u32)camera1_detector_status);
			} else {
				face_trackers_update_stereo(face_trackers,
					camera1_detected_boxes, 0U);
			}
			bbox_write_all(face_trackers);
			if ((detector_iterations % 20U) == 0U) {
				for (slot = 0U; slot < MAX_FACE_BOXES; ++slot) {
					if (face_trackers[slot].visible) {
						const TinyFaceBox *box = &face_trackers[slot].displayed;
						u32 distance_dm = face_trackers[slot].stereo_valid ?
							face_trackers[slot].stereo_distance_dm :
							face_distance_dm(box);
						++visible_count;
						xil_printf("FACE%d[f%d]: (%d,%d)-(%d,%d) score=%d/1000 distance=%d.%dm source=%s\r\n",
							slot, completed_frame, box->x_min, box->y_min,
							box->x_max, box->y_max,
							face_score_permille(box->score),
							distance_dm / 10U, distance_dm % 10U,
							face_trackers[slot].stereo_valid ? "stereo" : "fallback");
					}
				}
				if (visible_count == 0U) {
					xil_printf("FACE[f%d]: none\r\n", completed_frame);
				}
			}
		} else {
			memset(face_trackers, 0, sizeof(face_trackers));
			bbox_write_all(face_trackers);
			if (!detector_error_reported) {
				xil_printf("ERROR: tiny_face inference failed (%d)\r\n",
					detector_status);
				detector_error_reported = 1;
			}
		}
		if (camera1_detector_status < 0 && !detector_error_reported) {
			xil_printf("ERROR: camera1 tiny_face inference failed (%d)\r\n",
				camera1_detector_status);
			detector_error_reported = 1;
		}
	}

	return 0;
}


