/* Dynamic string buffer — from-scratch, real-world pattern */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    char* buf;
    int   len;
    int   cap;
} StrBuf;

StrBuf sb_new(int initial_cap) {
    StrBuf s;
    s.buf = (char*)malloc(initial_cap);
    s.buf[0] = '\0';
    s.len = 0;
    s.cap = initial_cap;
    return s;
}

void sb_grow(StrBuf* s, int needed) {
    while (s->cap <= needed) {
        s->cap *= 2;
    }
    s->buf = (char*)realloc(s->buf, s->cap);
}

void sb_append(StrBuf* s, const char* str) {
    int slen = (int)strlen(str);
    if (s->len + slen + 1 >= s->cap) {
        sb_grow(s, s->len + slen + 1);
    }
    memcpy(s->buf + s->len, str, slen + 1);
    s->len += slen;
}

void sb_append_char(StrBuf* s, char c) {
    if (s->len + 2 >= s->cap) {
        sb_grow(s, s->len + 2);
    }
    s->buf[s->len]     = c;
    s->buf[s->len + 1] = '\0';
    s->len += 1;
}

int sb_find(StrBuf* s, char c) {
    for (int i = 0; i < s->len; i++) {
        if (s->buf[i] == c) return i;
    }
    return -1;
}

void sb_free(StrBuf* s) {
    free(s->buf);
    s->buf = NULL;
    s->len = 0;
    s->cap = 0;
}

int main(void) {
    StrBuf s = sb_new(16);
    sb_append(&s, "Hello");
    sb_append_char(&s, ',');
    sb_append_char(&s, ' ');
    sb_append(&s, "world");
    sb_append_char(&s, '!');
    printf("%s\n", s.buf);
    printf("%d\n", s.len);
    printf("%d\n", sb_find(&s, 'w'));
    sb_free(&s);
    return 0;
}
