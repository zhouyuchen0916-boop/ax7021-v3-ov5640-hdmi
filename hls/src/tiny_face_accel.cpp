#include "tiny_face_accel.h"

#include "tiny_face_params.h"

namespace {

int32_t requantize(int32_t accumulator, int32_t multiplier_q31, int exponent) {
    int64_t product = static_cast<int64_t>(accumulator) * multiplier_q31;
    const int shift = 31 - exponent;
    const bool negative = product < 0;
    uint64_t absolute = negative ? static_cast<uint64_t>(-product) : static_cast<uint64_t>(product);
    uint64_t rounded;
    if (shift > 0) {
        rounded = (absolute + (static_cast<uint64_t>(1) << (shift - 1))) >> shift;
    } else {
        rounded = absolute << (-shift);
    }
    int64_t signed_value = negative ? -static_cast<int64_t>(rounded) : static_cast<int64_t>(rounded);
    if (signed_value < 0) {
        return 0;
    }
    if (signed_value > 255) {
        return 255;
    }
    return static_cast<int32_t>(signed_value);
}

template <int INPUT_CHANNELS,
          int OUTPUT_CHANNELS,
          int INPUT_HEIGHT,
          int INPUT_WIDTH,
          int OUTPUT_HEIGHT,
          int OUTPUT_WIDTH,
          int KERNEL,
          int STRIDE,
          int PADDING,
          int DILATION,
          int GROUPS>
void conv_relu_uint8(const uint8_t input[INPUT_CHANNELS * INPUT_HEIGHT * INPUT_WIDTH],
                     uint8_t output[OUTPUT_CHANNELS * OUTPUT_HEIGHT * OUTPUT_WIDTH],
                     const int8_t weights[OUTPUT_CHANNELS * (INPUT_CHANNELS / GROUPS) * KERNEL * KERNEL],
                     const int32_t bias[OUTPUT_CHANNELS],
                     const int32_t multiplier_q31[OUTPUT_CHANNELS],
                     const int8_t multiplier_exponent[OUTPUT_CHANNELS]) {
    const int channels_per_group = INPUT_CHANNELS / GROUPS;
    const int outputs_per_group = OUTPUT_CHANNELS / GROUPS;
    for (int output_channel = 0; output_channel < OUTPUT_CHANNELS; ++output_channel) {
        const int group = output_channel / outputs_per_group;
        const int input_channel_start = group * channels_per_group;
        for (int output_y = 0; output_y < OUTPUT_HEIGHT; ++output_y) {
            for (int output_x = 0; output_x < OUTPUT_WIDTH; ++output_x) {
                int32_t accumulator = bias[output_channel];
                for (int input_local = 0; input_local < channels_per_group; ++input_local) {
                    for (int kernel_y = 0; kernel_y < KERNEL; ++kernel_y) {
                        for (int kernel_x = 0; kernel_x < KERNEL; ++kernel_x) {
#pragma HLS PIPELINE II = 1
                            const int input_y = output_y * STRIDE + kernel_y * DILATION - PADDING;
                            const int input_x = output_x * STRIDE + kernel_x * DILATION - PADDING;
                            if (input_y >= 0 && input_y < INPUT_HEIGHT && input_x >= 0 && input_x < INPUT_WIDTH) {
                                const int input_channel = input_channel_start + input_local;
                                const int input_index =
                                    (input_channel * INPUT_HEIGHT + input_y) * INPUT_WIDTH + input_x;
                                const int weight_index =
                                    ((output_channel * channels_per_group + input_local) * KERNEL + kernel_y) *
                                        KERNEL +
                                    kernel_x;
                                accumulator += static_cast<int32_t>(input[input_index]) * weights[weight_index];
                            }
                        }
                    }
                }
                const int output_index =
                    (output_channel * OUTPUT_HEIGHT + output_y) * OUTPUT_WIDTH + output_x;
                output[output_index] = static_cast<uint8_t>(
                    requantize(accumulator, multiplier_q31[output_channel], multiplier_exponent[output_channel]));
            }
        }
    }
}

template <int INPUT_CHANNELS,
          int OUTPUT_CHANNELS,
          int HEIGHT,
          int WIDTH>
void conv_head(const uint8_t input[INPUT_CHANNELS * HEIGHT * WIDTH],
               int32_t output[OUTPUT_CHANNELS * HEIGHT * WIDTH],
               const int8_t weights[OUTPUT_CHANNELS * INPUT_CHANNELS],
               const int32_t bias[OUTPUT_CHANNELS]) {
    for (int output_channel = 0; output_channel < OUTPUT_CHANNELS; ++output_channel) {
        for (int y = 0; y < HEIGHT; ++y) {
            for (int x = 0; x < WIDTH; ++x) {
                int32_t accumulator = bias[output_channel];
                for (int input_channel = 0; input_channel < INPUT_CHANNELS; ++input_channel) {
#pragma HLS PIPELINE II = 1
                    const int input_index = (input_channel * HEIGHT + y) * WIDTH + x;
                    const int weight_index = output_channel * INPUT_CHANNELS + input_channel;
                    accumulator += static_cast<int32_t>(input[input_index]) * weights[weight_index];
                }
                output[(output_channel * HEIGHT + y) * WIDTH + x] = accumulator;
            }
        }
    }
}

}  // namespace

extern "C" void tiny_face_accel(const uint8_t input[TINY_FACE_INPUT_SIZE],
                                int32_t output[TINY_FACE_OUTPUT_SIZE]) {
#pragma HLS INTERFACE m_axi port = input offset = slave bundle = gmem0 depth = 19200
#pragma HLS INTERFACE m_axi port = output offset = slave bundle = gmem1 depth = 1500
#pragma HLS INTERFACE s_axilite port = input bundle = control
#pragma HLS INTERFACE s_axilite port = output bundle = control
#pragma HLS INTERFACE s_axilite port = return bundle = control

    static uint8_t input_buffer[1 * 120 * 160];
    static uint8_t feature1[8 * 60 * 80];
    static uint8_t feature2[16 * 30 * 40];
    static uint8_t feature3[24 * 15 * 20];
    static uint8_t context1_depthwise[24 * 15 * 20];
    static uint8_t context1_pointwise[24 * 15 * 20];
    static uint8_t context2_depthwise[24 * 15 * 20];
    static uint8_t context2_pointwise[24 * 15 * 20];

#pragma HLS BIND_STORAGE variable = input_buffer type = ram_2p impl = bram
#pragma HLS BIND_STORAGE variable = feature1 type = ram_2p impl = bram
#pragma HLS BIND_STORAGE variable = feature2 type = ram_2p impl = bram
#pragma HLS BIND_STORAGE variable = feature3 type = ram_2p impl = bram
#pragma HLS BIND_STORAGE variable = context1_depthwise type = ram_2p impl = bram
#pragma HLS BIND_STORAGE variable = context1_pointwise type = ram_2p impl = bram
#pragma HLS BIND_STORAGE variable = context2_depthwise type = ram_2p impl = bram
#pragma HLS BIND_STORAGE variable = context2_pointwise type = ram_2p impl = bram

    for (int index = 0; index < TINY_FACE_INPUT_SIZE; ++index) {
#pragma HLS PIPELINE II = 1
        input_buffer[index] = input[index];
    }

    conv_relu_uint8<1, 8, 120, 160, 60, 80, 3, 2, 1, 1, 1>(
        input_buffer, feature1, conv1_weights, conv1_bias, conv1_multiplier_q31, conv1_multiplier_exponent);
    conv_relu_uint8<8, 16, 60, 80, 30, 40, 3, 2, 1, 1, 1>(
        feature1, feature2, conv2_weights, conv2_bias, conv2_multiplier_q31, conv2_multiplier_exponent);
    conv_relu_uint8<16, 24, 30, 40, 15, 20, 3, 2, 1, 1, 1>(
        feature2, feature3, conv3_weights, conv3_bias, conv3_multiplier_q31, conv3_multiplier_exponent);
    conv_relu_uint8<24, 24, 15, 20, 15, 20, 3, 1, 2, 2, 24>(
        feature3,
        context1_depthwise,
        context1_dw_weights,
        context1_dw_bias,
        context1_dw_multiplier_q31,
        context1_dw_multiplier_exponent);
    conv_relu_uint8<24, 24, 15, 20, 15, 20, 1, 1, 0, 1, 1>(
        context1_depthwise,
        context1_pointwise,
        context1_pw_weights,
        context1_pw_bias,
        context1_pw_multiplier_q31,
        context1_pw_multiplier_exponent);
    conv_relu_uint8<24, 24, 15, 20, 15, 20, 3, 1, 4, 4, 24>(
        context1_pointwise,
        context2_depthwise,
        context2_dw_weights,
        context2_dw_bias,
        context2_dw_multiplier_q31,
        context2_dw_multiplier_exponent);
    conv_relu_uint8<24, 24, 15, 20, 15, 20, 1, 1, 0, 1, 1>(
        context2_depthwise,
        context2_pointwise,
        context2_pw_weights,
        context2_pw_bias,
        context2_pw_multiplier_q31,
        context2_pw_multiplier_exponent);
    conv_head<24, 5, 15, 20>(context2_pointwise, output, head_weights, head_bias);
}
