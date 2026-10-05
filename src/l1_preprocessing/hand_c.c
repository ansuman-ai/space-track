#include <stdint.h>
#include <math.h>

void d8_accum(const int64_t* order, const int64_t* target, int64_t n, int32_t* accum) {
    for (int64_t k = 0; k < n; k++) {
        int64_t i = order[k];
        int64_t tgt = target[i];
        if (tgt >= 0 && tgt < n) {
            accum[tgt] += accum[i];
        }
    }
}

void d8_propagate(const int64_t* rev_order, const int64_t* target, int64_t n, float* drainage) {
    for (int64_t k = 0; k < n; k++) {
        int64_t i = rev_order[k];
        if (isnan(drainage[i])) {
            int64_t tgt = target[i];
            if (tgt >= 0 && tgt < n && !isnan(drainage[tgt])) {
                drainage[i] = drainage[tgt];
            }
        }
    }
}
