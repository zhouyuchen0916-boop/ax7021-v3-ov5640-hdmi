#pragma once

#include <stdint.h>

static const int TINY_FACE_INPUT_SIZE = 120 * 160;
static const int TINY_FACE_OUTPUT_SIZE = 5 * 15 * 20;

extern "C" void tiny_face_accel(const uint8_t input[TINY_FACE_INPUT_SIZE],
                                int32_t output[TINY_FACE_OUTPUT_SIZE]);
