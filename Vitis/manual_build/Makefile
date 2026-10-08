APP := an5642_single
SRC_ROOT := ../auto_create_vitis/src/an5642_single
BSP_ROOT := ../design_1_wrapper/ps7_cortexa9_0/standalone_domain/bsp/ps7_cortexa9_0
INCLUDE_DIR := $(BSP_ROOT)/include
LIB_DIR := $(BSP_ROOT)/lib
BUILD_DIR := build

CC := arm-none-eabi-gcc
SIZE := arm-none-eabi-size

CFLAGS := -O2 -g -Wall -Wextra -ffunction-sections -fdata-sections \
          -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard \
          -I$(INCLUDE_DIR) -I$(SRC_ROOT) -I$(SRC_ROOT)/display_ctrl \
          -I$(SRC_ROOT)/dynclk -I$(SRC_ROOT)/i2c
LDFLAGS := -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard \
           -Wl,-T,lscript.ld -Wl,--gc-sections -L$(LIB_DIR)
LDLIBS := -Wl,--start-group -lxil -lgcc -lc -lm -Wl,--end-group

OBJECTS := \
  $(BUILD_DIR)/display_demo.o \
  $(BUILD_DIR)/tiny_face_runtime.o \
  $(BUILD_DIR)/display_ctrl.o \
  $(BUILD_DIR)/dynclk.o \
  $(BUILD_DIR)/PS_i2c.o \
  $(BUILD_DIR)/ov5640.o \
  $(BUILD_DIR)/vdma.o

.PHONY: all clean

all: $(APP).elf

$(APP).elf: $(OBJECTS) lscript.ld
	$(CC) $(LDFLAGS) -o $@ $(OBJECTS) $(LDLIBS)
	$(SIZE) $@

$(BUILD_DIR):
	mkdir $(BUILD_DIR)

$(BUILD_DIR)/display_demo.o: $(SRC_ROOT)/display_demo.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/tiny_face_runtime.o: $(SRC_ROOT)/tiny_face_runtime.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/display_ctrl.o: $(SRC_ROOT)/display_ctrl/display_ctrl.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/dynclk.o: $(SRC_ROOT)/dynclk/dynclk.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/PS_i2c.o: $(SRC_ROOT)/i2c/PS_i2c.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/ov5640.o: $(SRC_ROOT)/ov5640.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/vdma.o: $(SRC_ROOT)/vdma.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -rf $(BUILD_DIR) $(APP).elf
