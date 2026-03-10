/* Fixed-size 3x3 matrix math */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define N 3

typedef struct {
    double data[N][N];
} Mat3;

Mat3 mat3_zero() {
    Mat3 m;
    for (int i = 0; i < N; i++)
        for (int j = 0; j < N; j++)
            m.data[i][j] = 0.0;
    return m;
}

Mat3 mat3_identity() {
    Mat3 m = mat3_zero();
    for (int i = 0; i < N; i++)
        m.data[i][i] = 1.0;
    return m;
}

Mat3 mat3_add(Mat3 a, Mat3 b) {
    Mat3 r = mat3_zero();
    for (int i = 0; i < N; i++)
        for (int j = 0; j < N; j++)
            r.data[i][j] = a.data[i][j] + b.data[i][j];
    return r;
}

Mat3 mat3_mul(Mat3 a, Mat3 b) {
    Mat3 r = mat3_zero();
    for (int i = 0; i < N; i++)
        for (int j = 0; j < N; j++)
            for (int k = 0; k < N; k++)
                r.data[i][j] += a.data[i][k] * b.data[k][j];
    return r;
}

double mat3_trace(Mat3 m) {
    double t = 0.0;
    for (int i = 0; i < N; i++)
        t += m.data[i][i];
    return t;
}

void mat3_print(Mat3 m) {
    for (int i = 0; i < N; i++) {
        for (int j = 0; j < N; j++) {
            printf("%g ", m.data[i][j]);
        }
        printf("\n");
    }
}

int main(void) {
    Mat3 I = mat3_identity();
    Mat3 A = mat3_zero();
    A.data[0][0] = 1.0; A.data[0][1] = 2.0; A.data[0][2] = 3.0;
    A.data[1][0] = 4.0; A.data[1][1] = 5.0; A.data[1][2] = 6.0;
    A.data[2][0] = 7.0; A.data[2][1] = 8.0; A.data[2][2] = 9.0;

    /* A * I should equal A */
    Mat3 R = mat3_mul(A, I);
    mat3_print(R);
    printf("%g\n", mat3_trace(A));

    return 0;
}
