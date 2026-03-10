/*
 * switch_map_test.c — tests switch/case and hash-map-like patterns
 * Used to verify xpile roundtrip for switch and map-like structures.
 */
#include <stdio.h>
#include <string.h>

/* Simple word-frequency counter using parallel arrays (map-like) */
#define MAX_WORDS 20

static char* keys[MAX_WORDS];
static int   counts[MAX_WORDS];
static int   n_words = 0;

void word_inc(char* word) {
    for (int i = 0; i < n_words; i++) {
        if (strcmp(keys[i], word) == 0) { counts[i]++; return; }
    }
    if (n_words < MAX_WORDS) {
        keys[n_words] = word;
        counts[n_words] = 1;
        n_words++;
    }
}

int word_get(char* word) {
    for (int i = 0; i < n_words; i++)
        if (strcmp(keys[i], word) == 0) return counts[i];
    return 0;
}

/* Day-of-week via switch */
const char* day_name(int d) {
    switch (d) {
        case 0: return "Sunday";
        case 1: return "Monday";
        case 2: return "Tuesday";
        case 3: return "Wednesday";
        case 4: return "Thursday";
        case 5: return "Friday";
        case 6: return "Saturday";
        default: return "Unknown";
    }
}

/* Token classifier via switch with fall-through */
const char* token_class(char c) {
    switch (c) {
        case 'a': case 'e': case 'i': case 'o': case 'u':
            return "vowel";
        case ' ': case '\t': case '\n':
            return "space";
        default:
            return "other";
    }
}

int main(void) {
    /* switch/case */
    for (int d = 0; d <= 6; d++)
        printf("%s\n", day_name(d));

    printf("a=%s e=%s b=%s\n",
           token_class('a'), token_class('e'), token_class('b'));

    /* map-like word count */
    char* words[] = {"the","cat","sat","on","the","mat","the","cat"};
    int nw = 8;
    for (int i = 0; i < nw; i++) word_inc(words[i]);
    printf("the=%d cat=%d sat=%d on=%d mat=%d\n",
           word_get("the"), word_get("cat"), word_get("sat"),
           word_get("on"),  word_get("mat"));

    return 0;
}
