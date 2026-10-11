
#ifndef VDMA_H_
#define VDMA_H_

#include "xaxivdma.h"


int vdma_read_init(short DeviceID,short HoriSizeInput,short VertSizeInput,short Stride,unsigned int FrameStoreStartAddr);
int vdma_write_init(short DeviceID, short HoriSizeInput, short VertSizeInput,
		short Stride, u8 *FrameStoreStartAddr[], u32 FrameStoreCount);
u32 vdma_write_current_frame(void);
u32 vdma_write_errors(void);
int vdma_write_clear_errors(u32 ErrorMask);
u32 vdma_version();

#endif /* VDMA_H_ */
