#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define N 10

int main() {
    int arr[N];
    srand(time(NULL));

    for (int i = 0; i < N; i++) {
        arr[i] = rand() % 100;
    }

    printf("Unsorted: ");
    for (int i = 0; i < N; i++) {
        printf("%d ", arr[i]);
    }
    printf("\n");

    for (int i = 0; i < N - 1; i++) {
        for (int j = 0; j < N - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                int tmp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = tmp;
            }
        }
    }

    printf("Sorted:   ");
    for (int i = 0; i < N; i++) {
        printf("%d ", arr[i]);
    }
    printf("\n");

    return 0;
}

