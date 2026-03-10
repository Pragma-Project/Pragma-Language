/* Simple singly-linked list in C — round-trip test */
#include <stdio.h>
#include <stdlib.h>

typedef struct Node {
    int value;
    struct Node* next;
} Node;

typedef struct List {
    Node* head;
    int length;
} List;

List list_new() {
    List l;
    l.head   = NULL;
    l.length = 0;
    return l;
}

void list_push(List* lst, int val) {
    Node* n = (Node*)malloc(sizeof(Node));
    n->value = val;
    n->next  = lst->head;
    lst->head   = n;
    lst->length += 1;
}

int list_sum(List* lst) {
    int total = 0;
    Node* cur = lst->head;
    while (cur != NULL) {
        total += cur->value;
        cur = cur->next;
    }
    return total;
}

int list_max(List* lst) {
    if (lst->head == NULL) return 0;
    int mx = lst->head->value;
    Node* cur = lst->head->next;
    while (cur != NULL) {
        if (cur->value > mx) mx = cur->value;
        cur = cur->next;
    }
    return mx;
}

void list_print(List* lst) {
    Node* cur = lst->head;
    while (cur != NULL) {
        printf("%d\n", cur->value);
        cur = cur->next;
    }
}

int main(void) {
    List lst = list_new();
    list_push(&lst, 10);
    list_push(&lst, 30);
    list_push(&lst, 20);
    list_push(&lst, 5);

    printf("%d\n", lst.length);
    printf("%d\n", list_sum(&lst));
    printf("%d\n", list_max(&lst));
    list_print(&lst);

    return 0;
}
