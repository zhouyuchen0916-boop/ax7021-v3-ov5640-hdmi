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
#define BBOX_X_MIN 320U
#define BBOX_X_MAX 960U
#define BBOX_Y_MIN 180U
#define BBOX_Y_MAX 540U
#define BBOX_ENABLE_MASK 0x80000000U
#define BBOX_PACK(minimum, maximum) \
	((((u32)(maximum) & 0x0FFFU) << 16) | ((u32)(minimum) & 0x0FFFU))


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
	XGpio_DiscreteWrite(&bbox_ctrl, 1,
		BBOX_ENABLE_MASK | BBOX_PACK(BBOX_X_MIN, BBOX_X_MAX));
	XGpio_DiscreteWrite(&bbox_ctrl, 2, BBOX_PACK(BBOX_Y_MIN, BBOX_Y_MAX));
	g_diag_stage = 0x50U;
	xil_printf("BBOX overlay: (%d,%d)-(%d,%d)\r\n",
		BBOX_X_MIN, BBOX_Y_MIN, BBOX_X_MAX, BBOX_Y_MAX);

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
	Status = vdma_write_init(XPAR_AXIVDMA_1_DEVICE_ID,1280 * 3,720,1280 * 3,
			(unsigned int)dispCtrl.framePtr[dispCtrl.curFrame]);
	if (Status != XST_SUCCESS) {
		g_diag_status = Status;
		g_diag_stage = 0xE00DU;
		diag_flush();
		xil_printf("ERROR: camera write VDMA failed (%d)\r\n", Status);
		return XST_FAILURE;
	}

	g_diag_stage = 0x900U;
	diag_flush();
	xil_printf("VIDEO RUNNING: camera -> DDR -> HDMI, 1280x720\r\n");
	u32 detector_iterations = 0U;
	int detector_error_reported = 0;
	while (1) {
		TinyFaceBox detected_box;
		int detector_status = tiny_face_infer(dispCtrl.framePtr[dispCtrl.curFrame],
				1280U, 720U, DEMO_STRIDE, &detected_box);
		++detector_iterations;
		if (detector_status > 0 && detected_box.valid) {
			XGpio_DiscreteWrite(&bbox_ctrl, 1,
				BBOX_ENABLE_MASK | BBOX_PACK(detected_box.x_min, detected_box.x_max));
			XGpio_DiscreteWrite(&bbox_ctrl, 2,
				BBOX_PACK(detected_box.y_min, detected_box.y_max));
			if ((detector_iterations % 20U) == 0U) {
				u32 score_milli = (u32)(detected_box.score * 1000.0f);
				xil_printf("FACE: (%d,%d)-(%d,%d), score=%d/1000\r\n",
					detected_box.x_min, detected_box.y_min,
					detected_box.x_max, detected_box.y_max, score_milli);
			}
		} else if (detector_status == 0) {
			XGpio_DiscreteWrite(&bbox_ctrl, 1, 0U);
			XGpio_DiscreteWrite(&bbox_ctrl, 2, 0U);
			if ((detector_iterations % 20U) == 0U) {
				xil_printf("FACE: none\r\n");
			}
		} else {
			XGpio_DiscreteWrite(&bbox_ctrl, 1, 0U);
			XGpio_DiscreteWrite(&bbox_ctrl, 2, 0U);
			if (!detector_error_reported) {
				xil_printf("ERROR: tiny_face inference failed (%d)\r\n",
					detector_status);
				detector_error_reported = 1;
			}
		}
		/* The HLS core takes about 42 ms at 100 MHz; this cadence leaves a
		 * small margin while keeping the detector close to real time. */
		usleep(50000);
	}

	return 0;
}


