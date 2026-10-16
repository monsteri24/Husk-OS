#ifndef OWNOS_JSON_ESCAPE_H
#define OWNOS_JSON_ESCAPE_H
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static char *json_escape(const char *text) {
    const unsigned char *p = (const unsigned char *)(text ? text : "");
    size_t len = strlen((const char *)p);
    if (len > (SIZE_MAX - 1) / 6) return NULL;
    char *result = malloc(len * 6 + 1), *out = result;
    if (!result) return NULL;
    const char hex[] = "0123456789abcdef";
    for (; *p; ++p) {
        if (*p == '"' || *p == '\\') { *out++ = '\\'; *out++ = (char)*p; }
        else if (*p == '\n') { *out++ = '\\'; *out++ = 'n'; }
        else if (*p == '\r') { *out++ = '\\'; *out++ = 'r'; }
        else if (*p == '\t') { *out++ = '\\'; *out++ = 't'; }
        else if (*p < 0x20) {
            *out++ = '\\'; *out++ = 'u'; *out++ = '0'; *out++ = '0';
            *out++ = hex[*p >> 4]; *out++ = hex[*p & 15];
        } else *out++ = (char)*p;
    }
    *out = 0;
    return result;
}
#endif
