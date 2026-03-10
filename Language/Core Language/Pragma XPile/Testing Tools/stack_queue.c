/* Stack and queue implemented with dynamic arrays */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---- Dynamic int stack ---- */
typedef struct {
    int* data;
    int  top;
    int  cap;
} Stack;

Stack stack_new(int initial_cap) {
    Stack s;
    s.data = (int*)malloc(sizeof(int) * initial_cap);
    s.top  = 0;
    s.cap  = initial_cap;
    return s;
}

void stack_push(Stack* s, int val) {
    if (s->top == s->cap) {
        s->cap  *= 2;
        s->data  = (int*)realloc(s->data, sizeof(int) * s->cap);
    }
    s->data[s->top] = val;
    s->top += 1;
}

int stack_pop(Stack* s) {
    s->top -= 1;
    return s->data[s->top];
}

int stack_peek(Stack* s) {
    return s->data[s->top - 1];
}

int stack_empty(Stack* s) {
    return s->top == 0;
}

/* ---- Int queue (circular buffer) ---- */
typedef struct {
    int* data;
    int  head;
    int  tail;
    int  size;
    int  cap;
} Queue;

Queue queue_new(int cap) {
    Queue q;
    q.data = (int*)malloc(sizeof(int) * cap);
    q.head = 0;
    q.tail = 0;
    q.size = 0;
    q.cap  = cap;
    return q;
}

void queue_enqueue(Queue* q, int val) {
    q->data[q->tail] = val;
    q->tail = (q->tail + 1) % q->cap;
    q->size += 1;
}

int queue_dequeue(Queue* q) {
    int val = q->data[q->head];
    q->head = (q->head + 1) % q->cap;
    q->size -= 1;
    return val;
}

int queue_empty(Queue* q) {
    return q->size == 0;
}

/* ---- Main ---- */
int main(void) {
    /* Stack: push 1..5, pop all */
    Stack s = stack_new(4);
    for (int i = 1; i <= 5; i++) {
        stack_push(&s, i * 10);
    }
    while (!stack_empty(&s)) {
        printf("%d\n", stack_pop(&s));
    }

    /* Queue: enqueue 1..4, dequeue all */
    Queue q = queue_new(8);
    queue_enqueue(&q, 100);
    queue_enqueue(&q, 200);
    queue_enqueue(&q, 300);
    queue_enqueue(&q, 400);
    while (!queue_empty(&q)) {
        printf("%d\n", queue_dequeue(&q));
    }

    return 0;
}
