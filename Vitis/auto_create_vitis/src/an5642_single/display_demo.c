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
/*
 * XPAR redefines
 */
#define DYNCLK_BASEADDR XPAR_AXI_DYNCLK_0_BASEADDR
#define VGA_VDMA_ID XPAR_AXIVDMA_0_DEVICE_ID
#define DISP_VTC_ID XPAR_VTC_0_DEVICE_ID
#define VID_VTC_IRPT_ID XPS_FPGA3_INT_ID
#define VID_GPIO_IRPT_ID XPS_FPGA4_INT_ID
#define SCU_TIMER_ID XPAR_SCUTIMER_DEVICE_ID
#define UART_BASEADDR XPAR_PS7_UART_1_BASEADDR


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
/*
 * Framebuffers for video data
 */
u8 frameBuf[DISPLAY_NUM_FRAMES][DEMO_MAX_FRAME] __attribute__ ((aligned(64)));
u8 *pFrames[DISPLAY_NUM_FRAMES]; //array of pointers to the frame buffers

/* ------------------------------------------------------------ */
/*				Procedure Definitions							*/
/* ------------------------------------------------------------ */



int main(void)
{

	int Status;
	XAxiVdma_Config *vdmaConfig;
	int i;
	u8 chip_id_high;
	u8 chip_id_low;

	xil_printf("\r\nAX7021 OV5640 HDMI demo start\r\n");

	/*
	 * Initialize an array of pointers to the 3 frame buffers
	 */
	for (i = 0; i < DISPLAY_NUM_FRAMES; i++)
	{
		pFrames[i] = frameBuf[i];
		memset(pFrames[i], 0, DEMO_MAX_FRAME);
		Xil_DCacheFlushRange((INTPTR) pFrames[i], DEMO_MAX_FRAME) ;
	}

	Status = i2c_init(&ps_i2c0, XPAR_XIICPS_0_DEVICE_ID,40000);
	if (Status != XST_SUCCESS) {
		xil_printf("ERROR: PS I2C initialization failed (%d)\r\n", Status);
		return XST_FAILURE;
	}
	xil_printf("PS I2C ready at 40 kHz\r\n");

	Status = XGpio_Initialize(&hdmi_rstn, XPAR_HDMI_RST_DEVICE_ID);   //initialize GPIO IP
	if (Status != XST_SUCCESS) {
		xil_printf("ERROR: HDMI reset GPIO initialization failed (%d)\r\n", Status);
		return XST_FAILURE;
	}
	XGpio_SetDataDirection(&hdmi_rstn, 1, 0x0);            //set GPIO as output
	XGpio_DiscreteWrite(&hdmi_rstn, 1, 0x0);               //set GPIO output value to 0

	Status = XGpio_Initialize(&cmos_rstn, XPAR_CMOS_RST_DEVICE_ID);   //initialize GPIO IP
	if (Status != XST_SUCCESS) {
		xil_printf("ERROR: camera reset GPIO initialization failed (%d)\r\n", Status);
		return XST_FAILURE;
	}
	XGpio_SetDataDirection(&cmos_rstn, 1, 0x0);            //set GPIO as output
	XGpio_DiscreteWrite(&cmos_rstn, 1, 0x1);
	usleep(500000);
	XGpio_DiscreteWrite(&cmos_rstn, 1, 0x0);               //set GPIO output value to 0

	usleep(500000);
	XGpio_DiscreteWrite(&hdmi_rstn, 1, 0x1);
	XGpio_DiscreteWrite(&cmos_rstn, 1, 0x1);
	usleep(500000);
	Status = i2c_reg8_write(&ps_i2c0,0x72>>1,0x08,0x35);
	if (Status != XST_SUCCESS) {
		xil_printf("ERROR: HDMI transmitter register write failed (%d)\r\n", Status);
		return XST_FAILURE;
	}
	Status = i2c_reg8_write(&ps_i2c0,0x7a>>1,0x2f,0x00);
	if (Status != XST_SUCCESS) {
		xil_printf("ERROR: HDMI companion register write failed (%d)\r\n", Status);
		return XST_FAILURE;
	}
	/*
	 * Initialize Sensor
	 */
	Status = ov5640_read(&ps_i2c0, 0x300A, &chip_id_high);
	if (Status == XST_SUCCESS) {
		Status = ov5640_read(&ps_i2c0, 0x300B, &chip_id_low);
	}
	if (Status != XST_SUCCESS) {
		xil_printf("ERROR: OV5640 chip ID read failed (%d)\r\n", Status);
		return XST_FAILURE;
	}
	xil_printf("OV5640 chip ID: 0x%x%x\r\n", chip_id_high, chip_id_low);
	if ((chip_id_high != 0x56U) || (chip_id_low != 0x40U)) {
		xil_printf("ERROR: unexpected camera chip ID\r\n");
		return XST_FAILURE;
	}
	Status = sensor_init(&ps_i2c0);
	if (Status != XST_SUCCESS) {
		xil_printf("ERROR: OV5640 register initialization failed (%d)\r\n", Status);
		return XST_FAILURE;
	}
	xil_printf("OV5640 configured for 1280x720 RGB output\r\n");
	/*
	 * Initialize VDMA driver
	 */
	vdmaConfig = XAxiVdma_LookupConfig(VGA_VDMA_ID);
	if (!vdmaConfig)
	{
		xil_printf("No video DMA found for ID %d\r\n", VGA_VDMA_ID);
		return XST_FAILURE;
	}
	Status = XAxiVdma_CfgInitialize(&vdma, vdmaConfig, vdmaConfig->BaseAddress);
	if (Status != XST_SUCCESS)
	{
		xil_printf("VDMA Configuration Initialization failed %d\r\n", Status);
		return XST_FAILURE;
	}

	/*
	 * Initialize the Display controller and start it
	 */
	Status = DisplayInitialize(&dispCtrl, &vdma, DISP_VTC_ID, DYNCLK_BASEADDR,pFrames, DEMO_STRIDE);
	if (Status != XST_SUCCESS)
	{
		xil_printf("Display Ctrl initialization failed during demo initialization%d\r\n", Status);
		return XST_FAILURE;
	}
	Status = DisplayStart(&dispCtrl);
	if (Status != XST_SUCCESS)
	{
		xil_printf("Couldn't start display during demo initialization%d\r\n", Status);
		return XST_FAILURE;
	}
	/* Clear frame buffer */
	memset(dispCtrl.framePtr[dispCtrl.curFrame], 0, 1920 * 1080 * 3);
	/* Start Sensor Vdma */
	Status = vdma_write_init(XPAR_AXIVDMA_1_DEVICE_ID,1280 * 3,720,1280 * 3,
			(unsigned int)dispCtrl.framePtr[dispCtrl.curFrame]);
	if (Status != XST_SUCCESS) {
		xil_printf("ERROR: camera write VDMA failed (%d)\r\n", Status);
		return XST_FAILURE;
	}

	xil_printf("VIDEO RUNNING: camera -> DDR -> HDMI, 1280x720\r\n");
	while (1) {
		usleep(1000000);
	}

	return 0;
}


