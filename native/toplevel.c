#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <inttypes.h>
#include <poll.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wayland-client.h>
#include "foreign-toplevel-client-protocol.h"
#include "json_escape.h"

struct entry {
    uint32_t id;
    struct zwlr_foreign_toplevel_handle_v1 *handle;
    char *title, *app_id;
    bool active, minimized;
    struct entry *next;
};
static struct entry *entries;
static struct wl_seat *seat;
static struct zwlr_foreign_toplevel_manager_v1 *manager;
static uint32_t next_id = 1;
static bool running = true;

static void title(void *data, struct zwlr_foreign_toplevel_handle_v1 *h, const char *text) {
    (void)h; struct entry *e = data;
    free(e->title); e->title = strndup(text, 4096);
}
static void app_id(void *data, struct zwlr_foreign_toplevel_handle_v1 *h, const char *text) {
    (void)h; struct entry *e = data;
    free(e->app_id); e->app_id = strndup(text, 512);
}
static void output(void *data, struct zwlr_foreign_toplevel_handle_v1 *h, struct wl_output *o) {
    (void)data; (void)h; (void)o;
}
static void state(void *data, struct zwlr_foreign_toplevel_handle_v1 *h, struct wl_array *states) {
    (void)h; struct entry *e = data; uint32_t *s;
    e->active = e->minimized = false;
    wl_array_for_each(s, states) {
        if (*s == ZWLR_FOREIGN_TOPLEVEL_HANDLE_V1_STATE_ACTIVATED) e->active = true;
        if (*s == ZWLR_FOREIGN_TOPLEVEL_HANDLE_V1_STATE_MINIMIZED) e->minimized = true;
    }
}
static void done(void *data, struct zwlr_foreign_toplevel_handle_v1 *h) {
    (void)h; struct entry *e = data;
    char *t = json_escape(e->title), *a = json_escape(e->app_id);
    if (t && a) {
        printf("{\"event\":\"upsert\",\"id\":%" PRIu32 ",\"title\":\"%s\",\"app_id\":\"%s\",\"active\":%s,\"minimized\":%s}\n",
               e->id, t, a, e->active ? "true" : "false", e->minimized ? "true" : "false");
        fflush(stdout);
    }
    free(t); free(a);
}
static void closed(void *data, struct zwlr_foreign_toplevel_handle_v1 *h) {
    struct entry *e = data, **p = &entries;
    printf("{\"event\":\"closed\",\"id\":%" PRIu32 "}\n", e->id); fflush(stdout);
    while (*p && *p != e) p = &(*p)->next;
    if (*p) *p = e->next;
    zwlr_foreign_toplevel_handle_v1_destroy(h);
    free(e->title); free(e->app_id); free(e);
}
static void parent(void *data, struct zwlr_foreign_toplevel_handle_v1 *h,
                   struct zwlr_foreign_toplevel_handle_v1 *p) { (void)data; (void)h; (void)p; }
static const struct zwlr_foreign_toplevel_handle_v1_listener listener = {
    .title=title, .app_id=app_id, .output_enter=output, .output_leave=output,
    .state=state, .done=done, .closed=closed, .parent=parent
};
static void toplevel(void *data, struct zwlr_foreign_toplevel_manager_v1 *m,
                     struct zwlr_foreign_toplevel_handle_v1 *handle) {
    (void)data; (void)m; struct entry *e = calloc(1, sizeof(*e));
    if (!e) { running = false; return; }
    e->id = next_id++; e->handle = handle; e->next = entries; entries = e;
    zwlr_foreign_toplevel_handle_v1_add_listener(handle, &listener, e);
}
static void finished(void *data, struct zwlr_foreign_toplevel_manager_v1 *m) {
    (void)data; (void)m; running = false;
}
static const struct zwlr_foreign_toplevel_manager_v1_listener manager_listener = {
    .toplevel=toplevel, .finished=finished
};
static void global(void *data, struct wl_registry *registry, uint32_t name, const char *interface, uint32_t version) {
    (void)data;
    if (!strcmp(interface, zwlr_foreign_toplevel_manager_v1_interface.name)) {
        manager = wl_registry_bind(registry, name, &zwlr_foreign_toplevel_manager_v1_interface, version < 3 ? version : 3);
        zwlr_foreign_toplevel_manager_v1_add_listener(manager, &manager_listener, NULL);
    } else if (!strcmp(interface, wl_seat_interface.name) && !seat) {
        seat = wl_registry_bind(registry, name, &wl_seat_interface, 1);
    }
}
static void global_remove(void *data, struct wl_registry *registry, uint32_t name) { (void)data; (void)registry; (void)name; }
static const struct wl_registry_listener registry_listener = { .global=global, .global_remove=global_remove };

static void command(const char *line) {
    char action[32], extra; uint32_t id;
    if (sscanf(line, "%31s %" SCNu32 " %c", action, &id, &extra) != 2) return;
    for (struct entry *e = entries; e; e = e->next) if (e->id == id) {
        if (!strcmp(action, "activate") && seat) {
            if (e->minimized) zwlr_foreign_toplevel_handle_v1_unset_minimized(e->handle);
            zwlr_foreign_toplevel_handle_v1_activate(e->handle, seat);
        } else if (!strcmp(action, "minimize")) zwlr_foreign_toplevel_handle_v1_set_minimized(e->handle);
        else if (!strcmp(action, "close")) zwlr_foreign_toplevel_handle_v1_close(e->handle);
        return;
    }
}
int main(void) {
    struct wl_display *display = wl_display_connect(NULL);
    if (!display) { fprintf(stderr, "Husk OS: no Wayland display\n"); return 1; }
    struct wl_registry *registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, NULL);
    if (wl_display_roundtrip(display) < 0 || !manager) {
        fprintf(stderr, "Husk OS: foreign-toplevel protocol is unavailable\n"); wl_display_disconnect(display); return 1;
    }
    struct pollfd fds[] = {{ .fd=wl_display_get_fd(display), .events=POLLIN }, {.fd=0, .events=POLLIN}};
    if (wl_display_roundtrip(display) < 0) { wl_display_disconnect(display); return 1; }
    printf("{\"event\":\"ready\",\"foreign_toplevel\":true,\"seat\":%s}\n", seat ? "true" : "false");
    fflush(stdout);
    char line[128];
    /* poll() watches the fd, so stdio must not hide a second complete command. */
    setvbuf(stdin, NULL, _IONBF, 0);
    while (running) {
        if (wl_display_dispatch_pending(display) < 0) break;
        int flush = wl_display_flush(display);
        fds[0].events = POLLIN | ((flush < 0 && errno == EAGAIN) ? POLLOUT : 0);
        if (flush < 0 && errno != EAGAIN) break;
        int result = poll(fds, 2, -1);
        if (result < 0) { if (errno == EINTR) continue; break; }
        if (fds[0].revents & (POLLERR | POLLHUP)) break;
        if (fds[0].revents & POLLIN) if (wl_display_dispatch(display) < 0) break;
        if (fds[1].revents & POLLIN) { if (!fgets(line, sizeof line, stdin)) break; command(line); }
        if (fds[1].revents & (POLLERR | POLLHUP)) break;
    }
    while (entries) {
        struct entry *e = entries; entries = e->next;
        zwlr_foreign_toplevel_handle_v1_destroy(e->handle); free(e->title); free(e->app_id); free(e);
    }
    if (seat) wl_seat_destroy(seat);
    zwlr_foreign_toplevel_manager_v1_destroy(manager); wl_registry_destroy(registry); wl_display_disconnect(display);
    return 0;
}
