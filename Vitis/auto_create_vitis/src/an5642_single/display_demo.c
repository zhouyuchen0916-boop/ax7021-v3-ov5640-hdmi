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
/*
 * XPAR redefines
 */
#define DYNCLK_BASEADDR XPAR_AXI_DYNCLK_0_BASEADDR
#define VGA_VDMA_ID XPAR_AXIVDMA_0_DEVICE_ID
#define DISP_VTC_ID XPAR_VTC_0_DEVICE_ID
#define VID_VTC_IRPT_ID XPS_FPGA3_INT_ID
#define VID_GPIO_IRPT_ID XPS_FPGA4_INT_ID
#define SCU_TIMER_ID XPAR_SCUTIMER_DEVICE_ID
#define UART0_BASEADDR XPAR_PS7_UART_0_BASEADDR
#define UART1_BASEADDR XPAR_PS7_UART_1_BASEADDR
#define BBOX_ENABLE_MASK 0x80000000U
#define BBOX_PACK(minimum, maximum) \
	((((u32)(maximum) & 0x0FFFU) << 16) | ((u32)(minimum) & 0x0FFFU))
#define FACE_CONFIRM_FRAMES 4U
#define FACE_CONFIRM_IOU_PERMILLE 450U
#define FACE_TRACK_IOU_PERMILLE 200U
#define FACE_CONFIRM_SCORE_PERMILLE 930U
#define FACE_HOLD_MISSES 5U

typedef struct {
	TinyFaceBox displayed;
	TinyFaceBox pending;
	u32 pending_count;
	u32 pending_score_sum;
	u32 missed_count;
	int visible;
} FaceTracker;


/* ------------------------------------------------------------ */
/*				Global Variables								*/
/* ------------------------------------------------------------ */

/*
 * Display Driver structs
 */
DisplayCtrl dispCtrl;
XAxiVdma vdma;
XIicPs ps_i2c0;
XGpio hdmi_rstn;
XGpio cmos_rstn;
XGpio bbox_ctrl;
volatile u32 g_diag_magic = 0xA7021D1AU;
volatile u32 g_diag_stage = 0U;
volatile s32 g_diag_status = 0;
volatile u32 g_ov5640_id = 0U;
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
	tracker->missed_count = 0U;
	return 0;
}

static void bbox_write(const TinyFaceBox *box)
{
	if (box != NULL && box->valid) {
		XGpio_DiscreteWrite(&bbox_ctrl, 1,
			BBOX_ENABLE_MASK | BBOX_PACK(box->x_min, box->x_max));
		XGpio_DiscreteWrite(&bbox_ctrl, 2,
			BBOX_PACK(box->y_min, box->y_max));
	} else {
		XGpio_DiscreteWrite(&bbox_ctrl, 1, 0U);
		XGpio_DiscreteWrite(&bbox_ctrl, 2, 0U);
	}
}

/* Wait for a real S2MM frame boundary.  Sampling immediately after the
 * pointer advances guarantees that (current - 1) is the frame that has just
 * completed, leaving two full frame periods before it can be overwritten. */
static int wait_for_write_frame_advance(u32 *writing_frame)
{
	u32 start_frame = vdma_write_current_frame();
	u32 elapsed_us;

	if (writing_frame == NULL || start_frame >= DISPLAY_NUM_FRAMES) {
		return XST_FAILURE;
	}
	for (elapsed_us = 0U; elapsed_us < 200000U; elapsed_us += 500U) {
		u32 errors = vdma_write_errors();
		u32 current_frame;

		if (errors != 0U) {
			vdma_write_clear_errors(errors);
			start_frame = vdma_write_current_frame();
		}
		current_frame = vdma_write_current_frame();
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
	xil_printf("\r\nAX7021 OV5640 HDMI demo start\r\n");
	g_diag_stage = 0x11U;

	/*
	 * Initialize an array of pointers to the 3 frame buffers
	 */
	for (i = 0; i < DISPLAY_NUM_FRAMES; i++)
	{
		g_diag_stage = 0x20U + (u32)i;
		pFrames[i] = frameBuf[i];
		memset(pFrames[i], 0, DEMO_MAX_FRAME);
		Xil_DCacheFlushRange((INTPTR) pFrames[i], DEMO_MAX_FRAME) ;
		g_diag_stage = 0x30U + (u32)i;
	}
	xil_printf("FRAME buffers: 0x%x 0x%x 0x%x\r\n",
		(u32)pFrames[0], (u32)pFrames[1], (u32)pFrames[2]);

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
	xil_printf("PS I2C ready at 40 kHz\r\n");

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

	Status = XGpio_Initialize(&bbox_ctrl, XPAR_BBOX_CTRL_DEVICE_ID);
	if (Status != XST_SUCCESS) {
		g_diag_status = Status;
		g_diag_stage = 0xE00EU;
		diag_flush();
		xil_printf("ERROR: bounding-box GPIO initialization failed (%d)\r\n", Status);
		return XST_FAILURE;
	}
	XGpio_SetDataDirection(&bbox_ctrl, 1, 0x00000000U);
	XGpio_SetDataDirection(&bbox_ctrl, 2, 0x00000000U);
	/* Keep the overlay disabled until a face is confirmed across several
	 * consecutive frames.  The old fixed test box caused a false green box
	 * throughout the camera/VDMA startup delay. */
	bbox_write(NULL);
	g_diag_stage = 0x50U;
	xil_printf("BBOX overlay: waiting for stable face detection\r\n");

	XGpio_DiscreteWrite(&cmos_rstn, 1, 0x1);
	usleep(500000);
	XGpio_DiscreteWrite(&cmos_rstn, 1, 0x0);               //set GPIO output value to 0

	usleep(500000);
	XGpio_DiscreteWrite(&hdmi_rstn, 1, 0x1);
	XGpio_DiscreteWrite(&cmos_rstn, 1, 0x1);
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
	/*
	 * Initialize Sensor
	 */
	g_diag_stage = 0x60U;
	Status = ov5640_read(&ps_i2c0, 0x300A, &chip_id_high);
	if (Status == XST_SUCCESS) {
		Status = ov5640_read(&ps_i2c0, 0x300B, &chip_id_low);
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
	xil_printf("OV5640 chip ID: 0x%x%x\r\n", chip_id_high, chip_id_low);
	if ((chip_id_high != 0x56U) || (chip_id_low != 0x40U)) {
		g_diag_stage = 0xE007U;
		diag_flush();
		xil_printf("ERROR: unexpected camera chip ID\r\n");
		return XST_FAILURE;
	}
	Status = sensor_init(&ps_i2c0);
	if (Status != XST_SUCCESS) {
		g_diag_status = Status;
		g_diag_stage = 0xE008U;
		diag_flush();
		xil_printf("ERROR: OV5640 register initialization failed (%d)\r\n", Status);
		return XST_FAILURE;
	}
	g_diag_stage = 0x70U;
	xil_printf("OV5640 configured for 1280x720 RGB output\r\n");
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
	Status = vdma_write_init(XPAR_AXIVDMA_1_DEVICE_ID, 1280 * 3, 720,
		1280 * 3, dispCtrl.framePtr, DISPLAY_NUM_FRAMES);
	if (Status != XST_SUCCESS) {
		g_diag_status = Status;
		g_diag_stage = 0xE00DU;
		diag_flush();
		xil_printf("ERROR: camera write VDMA failed (%d)\r\n", Status);
		return XST_FAILURE;
	}

	g_diag_stage = 0x900U;
	diag_flush();
	/* The camera bridge intentionally holds its FIFO in reset for several
	 * seconds after PCLK starts.  Wait until that hardware delay has elapsed
	 * and all circular buffers can contain a complete frame. */
	usleep(7000000);
	u32 startup_vdma_errors = vdma_write_errors();
	if (startup_vdma_errors != 0U) {
		xil_printf("VDMA startup errors: 0x%x (clearing latched frame status)\r\n",
			startup_vdma_errors);
		vdma_write_clear_errors(startup_vdma_errors);
		usleep(50000);
		xil_printf("VDMA errors after clear: 0x%x\r\n", vdma_write_errors());
	}
	u32 frame_seen_mask = 0U;
	for (u32 probe = 0U; probe < 300U && frame_seen_mask != 0x7U; ++probe) {
		u32 frame = vdma_write_current_frame();
		if (frame < DISPLAY_NUM_FRAMES) {
			frame_seen_mask |= 1U << frame;
		}
		usleep(5000);
	}
	if (frame_seen_mask != 0x7U || vdma_write_errors() != 0U) {
		xil_printf("ERROR: VDMA three-frame self-test failed (seen=0x%x err=0x%x)\r\n",
			frame_seen_mask, vdma_write_errors());
		return XST_FAILURE;
	}
	xil_printf("FRAME_SYNC_READY: seen=0x%x current=f%d errors=0x%x\r\n",
		frame_seen_mask, vdma_write_current_frame(), vdma_write_errors());
	xil_printf("VIDEO RUNNING: camera -> 3-frame GenLock DDR -> HDMI, 1280x720\r\n");
	u32 detector_iterations = 0U;
	int detector_error_reported = 0;
	FaceTracker face_tracker;
	memset(&face_tracker, 0, sizeof(face_tracker));
	while (1) {
		TinyFaceBox detected_box;
		u32 writing_frame;
		u32 completed_frame;
		int detector_status;

		if (wait_for_write_frame_advance(&writing_frame) != XST_SUCCESS) {
			xil_printf("ERROR: camera VDMA frame boundary timeout (err=0x%x)\r\n",
				vdma_write_errors());
			break;
		}
		/* With three circular buffers, the previous index is fully written and
		 * remains untouched while the camera writes the next two buffers.
		 * Preprocessing copies it into the detector's private 160x120 input. */
		completed_frame = (writing_frame + DISPLAY_NUM_FRAMES - 1U) %
			DISPLAY_NUM_FRAMES;
		if (detector_iterations < 12U) {
			xil_printf("FRAME_SYNC: writing=f%d, inference=f%d\r\n",
				writing_frame, completed_frame);
		}
		detector_status = tiny_face_infer(dispCtrl.framePtr[completed_frame],
				1280U, 720U, DEMO_STRIDE, &detected_box);
		++detector_iterations;
		if (detector_status >= 0) {
			const TinyFaceBox *candidate =
				(detector_status > 0 && detected_box.valid) ? &detected_box : NULL;
			int show_box = face_tracker_update(&face_tracker, candidate);

			bbox_write(show_box ? &face_tracker.displayed : NULL);
			if ((detector_iterations % 20U) == 0U) {
				if (show_box) {
					xil_printf("FACE_STABLE[f%d]: (%d,%d)-(%d,%d), score=%d/1000\r\n",
						completed_frame,
						face_tracker.displayed.x_min,
						face_tracker.displayed.y_min,
						face_tracker.displayed.x_max,
						face_tracker.displayed.y_max,
						face_score_permille(face_tracker.displayed.score));
				} else if (candidate != NULL) {
					xil_printf("FACE_PENDING[f%d]: score=%d/1000 confirm=%d/%d\r\n",
						completed_frame, face_score_permille(candidate->score),
						face_tracker.pending_count, FACE_CONFIRM_FRAMES);
				} else {
					xil_printf("FACE[f%d]: none\r\n", completed_frame);
				}
			}
		} else {
			bbox_write(NULL);
			if (!detector_error_reported) {
				xil_printf("ERROR: tiny_face inference failed (%d)\r\n",
					detector_status);
				detector_error_reported = 1;
			}
		}
	}

	return 0;
}


