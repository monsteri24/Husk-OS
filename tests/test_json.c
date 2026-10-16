#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include "../native/json_escape.h"

int main(void) {
    char *s = json_escape("Title\"\\\n\t\001");
    assert(s && strcmp(s, "Title\\\"\\\\\\n\\t\\u0001") == 0);
    free(s);
    s = json_escape("ää 🦅");
    assert(s && strcmp(s, "ää 🦅") == 0);
    free(s);
    s = json_escape(NULL);
    assert(s && strcmp(s, "") == 0);
    free(s);
    return 0;
}
