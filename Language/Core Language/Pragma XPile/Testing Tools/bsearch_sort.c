/* Binary search + insertion sort + merge sort */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Insertion sort (in-place) */
void insertion_sort(int* arr, int n) {
    for (int i = 1; i < n; i++) {
        int key = arr[i];
        int j = i - 1;
        while (j >= 0 && arr[j] > key) {
            arr[j + 1] = arr[j];
            j -= 1;
        }
        arr[j + 1] = key;
    }
}

/* Binary search — returns index or -1 */
int binary_search(int* arr, int n, int target) {
    int lo = 0;
    int hi = n - 1;
    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2;
        if (arr[mid] == target) return mid;
        if (arr[mid] < target)  lo = mid + 1;
        else                    hi = mid - 1;
    }
    return -1;
}

/* Merge helper */
void merge(int* arr, int lo, int mid, int hi) {
    int n1 = mid - lo + 1;
    int n2 = hi - mid;
    int* left  = (int*)malloc(sizeof(int) * n1);
    int* right = (int*)malloc(sizeof(int) * n2);
    for (int i = 0; i < n1; i++) left[i]  = arr[lo + i];
    for (int j = 0; j < n2; j++) right[j] = arr[mid + 1 + j];
    int i = 0, j = 0, k = lo;
    while (i < n1 && j < n2) {
        if (left[i] <= right[j]) { arr[k] = left[i];  i++; }
        else                     { arr[k] = right[j]; j++; }
        k++;
    }
    while (i < n1) { arr[k] = left[i];  i++; k++; }
    while (j < n2) { arr[k] = right[j]; j++; k++; }
    free(left);
    free(right);
}

/* Merge sort */
void merge_sort(int* arr, int lo, int hi) {
    if (lo < hi) {
        int mid = lo + (hi - lo) / 2;
        merge_sort(arr, lo, mid);
        merge_sort(arr, mid + 1, hi);
        merge(arr, lo, mid, hi);
    }
}

int main(void) {
    int a[] = {5, 3, 8, 1, 9, 2, 7, 4, 6};
    int n = 9;

    insertion_sort(a, n);
    for (int i = 0; i < n; i++) printf("%d ", a[i]);
    printf("\n");

    int idx = binary_search(a, n, 7);
    printf("%d\n", idx);

    int b[] = {42, 17, 99, 3, 55, 28, 71};
    int m = 7;
    merge_sort(b, 0, m - 1);
    for (int i = 0; i < m; i++) printf("%d ", b[i]);
    printf("\n");

    return 0;
}
