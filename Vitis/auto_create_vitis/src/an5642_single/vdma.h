
#ifndef VDMA_H_
#define VDMA_H_

#include "xaxivdma.h"


int vdma_read_init(short DeviceID,short HoriSizeInput,short VertSizeInput,short Stride,unsigned int FrameStoreStartAddr);
int vdma_write_init(u32 Channel, short DeviceID, short HoriSizeInput, short VertSizeInput,
		short Stride, u8 *FrameStoreStartAddr[], u32 FrameStoreCount);
u32 vdma_write_current_frame(u32 Channel);
u32 vdma_write_errors(u32 Channel);
int vdma_write_clear_errors(u32 Channel, u32 ErrorMask);
u32 vdma_version();

#endif /* VDMA_H_ */
