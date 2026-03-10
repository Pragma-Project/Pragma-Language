/*
 * union_test.c — tests union (variant) and function pointers
 * Used to verify xpile roundtrip for these features.
 */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

/* --- variant (union) --- */
typedef union {
    int   i;
    float f;
    char  bytes[4];
} Word;

typedef union {
    struct { unsigned int r:8; unsigned int g:8; unsigned int b:8; unsigned int a:8; } rgba;
    unsigned int packed;
} Colour;

/* --- function pointers --- */
int add(int a, int b) { return a + b; }
int sub(int a, int b) { return a - b; }
int mul(int a, int b) { return a * b; }

typedef int (*BinOp)(int, int);

int apply(BinOp op, int a, int b) { return op(a, b); }

int compare_asc(const void* a, const void* b) {
    return (*(int*)a - *(int*)b);
}

int main(void) {
    /* union tests */
    Word w;
    w.i = 0x41424344;
    printf("%c%c%c%c\n", w.bytes[0], w.bytes[1], w.bytes[2], w.bytes[3]);

    w.f = 1.5f;
    printf("%.1f\n", w.f);

    Colour c;
    c.rgba.r = 255;
    c.rgba.g = 128;
    c.rgba.b = 0;
    c.rgba.a = 255;
    printf("%u %u %u\n", c.rgba.r, c.rgba.g, c.rgba.b);
    printf("%d\n", c.packed != 0);

    /* function pointer tests */
    BinOp ops[3] = { add, sub, mul };
    const char* names[3] = { "add", "sub", "mul" };
    for (int i = 0; i < 3; i++) {
        printf("%s(10,3) = %d\n", names[i], ops[i](10, 3));
    }

    /* function pointer as argument */
    printf("apply(add,7,8) = %d\n", apply(add, 7, 8));
    printf("apply(mul,4,5) = %d\n", apply(mul, 4, 5));

    /* qsort with function pointer */
    int arr[6] = {5, 2, 8, 1, 9, 3};
    qsort(arr, 6, sizeof(int), compare_asc);
    for (int i = 0; i < 6; i++) printf("%d\n", arr[i]);

    return 0;
}
