/*
 * Minimal recursive descent JSON number/boolean/null tokenizer.
 * Real-world pattern: tokenizing + state machine parsing.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

typedef enum {
    TOK_NUM, TOK_TRUE, TOK_FALSE, TOK_NULL,
    TOK_LBRACE, TOK_RBRACE, TOK_LBRACKET, TOK_RBRACKET,
    TOK_COLON, TOK_COMMA, TOK_STRING, TOK_EOF, TOK_ERROR
} TokenKind;

typedef struct {
    TokenKind kind;
    double    num;
    char      str[64];
} Token;

typedef struct {
    const char* src;
    int         pos;
} Lexer;

static void skip_ws(Lexer* L) {
    while (L->src[L->pos] == ' '  || L->src[L->pos] == '\t' ||
           L->src[L->pos] == '\n' || L->src[L->pos] == '\r') {
        L->pos++;
    }
}

static Token next_token(Lexer* L) {
    Token t;
    skip_ws(L);
    char c = L->src[L->pos];
    if (c == '\0') { t.kind = TOK_EOF; return t; }
    if (c == '{')  { t.kind = TOK_LBRACE;   L->pos++; return t; }
    if (c == '}')  { t.kind = TOK_RBRACE;   L->pos++; return t; }
    if (c == '[')  { t.kind = TOK_LBRACKET; L->pos++; return t; }
    if (c == ']')  { t.kind = TOK_RBRACKET; L->pos++; return t; }
    if (c == ':')  { t.kind = TOK_COLON;    L->pos++; return t; }
    if (c == ',')  { t.kind = TOK_COMMA;    L->pos++; return t; }
    if (c == '"') {
        L->pos++;
        int i = 0;
        while (L->src[L->pos] != '"' && L->src[L->pos] != '\0' && i < 63) {
            t.str[i++] = L->src[L->pos++];
        }
        t.str[i] = '\0';
        if (L->src[L->pos] == '"') L->pos++;
        t.kind = TOK_STRING;
        return t;
    }
    if (c == '-' || (c >= '0' && c <= '9')) {
        char buf[32];
        int i = 0;
        if (c == '-') buf[i++] = L->src[L->pos++];
        while ((L->src[L->pos] >= '0' && L->src[L->pos] <= '9') && i < 30) {
            buf[i++] = L->src[L->pos++];
        }
        if (L->src[L->pos] == '.') {
            buf[i++] = L->src[L->pos++];
            while ((L->src[L->pos] >= '0' && L->src[L->pos] <= '9') && i < 30) {
                buf[i++] = L->src[L->pos++];
            }
        }
        buf[i] = '\0';
        t.kind = TOK_NUM;
        t.num  = atof(buf);
        return t;
    }
    if (strncmp(L->src + L->pos, "true", 4) == 0)  { t.kind = TOK_TRUE;  L->pos += 4; return t; }
    if (strncmp(L->src + L->pos, "false", 5) == 0) { t.kind = TOK_FALSE; L->pos += 5; return t; }
    if (strncmp(L->src + L->pos, "null", 4) == 0)  { t.kind = TOK_NULL;  L->pos += 4; return t; }
    t.kind = TOK_ERROR;
    return t;
}

int count_tokens(const char* json) {
    Lexer L;
    L.src = json;
    L.pos = 0;
    int count = 0;
    while (1) {
        Token t = next_token(&L);
        if (t.kind == TOK_EOF || t.kind == TOK_ERROR) break;
        count++;
    }
    return count;
}

int main(void) {
    const char* j1 = "{\"name\": \"Alice\", \"age\": 30, \"active\": true}";
    const char* j2 = "[1, 2.5, null, false, 42]";
    printf("%d\n", count_tokens(j1));
    printf("%d\n", count_tokens(j2));
    return 0;
}
