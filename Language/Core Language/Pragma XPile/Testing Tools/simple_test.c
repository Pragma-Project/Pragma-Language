/* Simple C file for round-trip testing */
#include <stdio.h>

#define MAX 10
#define PI 3.14159

int add(int a, int b) {
    return a + b;
}

int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

int clamp(int val, int lo, int hi) {
    if (val < lo) return lo;
    else if (val > hi) return hi;
    return val;
}

int is_prime(int n) {
    if (n < 2) return 0;
    for (int i = 2; i * i <= n; i++) {
        if (n % i == 0) return 0;
    }
    return 1;
}

int main(void) {
    printf("%d\n", add(3, 7));
    printf("%d\n", factorial(6));
    printf("%d\n", clamp(150, 0, 100));
    printf("%d\n", clamp(-5, 0, 100));

    int sum = 0;
    for (int i = 1; i <= MAX; i++) {
        sum += i;
    }
    printf("%d\n", sum);

    int count = 0;
    int j = 1;
    while (j <= 20) {
        if (is_prime(j)) count++;
        j++;
    }
    printf("%d\n", count);

    int flags = 0b1010;
    flags = flags & 0b1100;
    flags = flags | 1;
    flags = flags ^ 3;
    flags = flags << 1;
    flags = flags >> 1;
    printf("%d\n", flags);

    double x = 3.7;
    int truncated = (int)x;
    printf("%d\n", truncated);

    return 0;
}
