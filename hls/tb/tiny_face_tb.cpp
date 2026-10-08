#include <iostream>

#include "test_vector.h"
#include "tiny_face_accel.h"

int main() {
    static int32_t actual[TINY_FACE_OUTPUT_SIZE];
    tiny_face_accel(test_input, actual);
    int mismatches = 0;
    int32_t maximum_error = 0;
    for (int index = 0; index < TINY_FACE_OUTPUT_SIZE; ++index) {
        int32_t difference = actual[index] - expected_output[index];
        if (difference < 0) {
            difference = -difference;
        }
        if (difference != 0) {
            if (mismatches < 10) {
                std::cerr << "mismatch index=" << index << " expected=" << expected_output[index]
                          << " actual=" << actual[index] << std::endl;
            }
            ++mismatches;
            if (difference > maximum_error) {
                maximum_error = difference;
            }
        }
    }
    std::cout << "HLS_CSIM_OUTPUTS=" << TINY_FACE_OUTPUT_SIZE << std::endl;
    std::cout << "HLS_CSIM_MISMATCHES=" << mismatches << std::endl;
    std::cout << "HLS_CSIM_MAX_ERROR=" << maximum_error << std::endl;
    return mismatches == 0 ? 0 : 1;
}
