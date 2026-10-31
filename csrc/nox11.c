/*
 * nox11.c -- a do-nothing implementation of the subset of Xlib that XPPAUT
 * calls.  Linking libxpp against this file instead of -lX11 removes the X
 * server entirely: every window, GC, font, and drawing call succeeds and
 * draws nothing.
 *
 * Two things matter for correctness:
 *
 *  1. Things XPP *reads back* must look like a real display: Display/Screen
 *     structs (used through the DefaultScreen/RootWindow/... macros), font
 *     metrics (DCURX/DCURY come from them), window geometry (used to scale
 *     plots), and a TrueColor visual so the colour code takes the simple path.
 *
 *  2. Anything that would *wait for a user* (XNextEvent) must never be
 *     reached.  All of XPP's interactive loops are replaced in headless.c;
 *     if one slips through, XNextEvent aborts the current Python call with a
 *     clear message instead of hanging the interpreter.
 */
#define XLIB_ILLEGAL_ACCESS 1
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/XKBlib.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* provided by headless.c: unwinds to the Python entry point with an error */
extern void pyxpp_fail(const char *fmt, ...);

/* ------------------------------------------------------------------ */
/* fake display                                                         */
/* ------------------------------------------------------------------ */
#define FAKE_W 1280
#define FAKE_H 1024
#define ROOT_ID 1

static Display *the_display = NULL;
static Screen the_screen;
static Visual the_visual;
static Depth the_depth;
static XID next_id = 100;

/* window geometry table so XGetGeometry returns what was created/resized */
typedef struct { Window w; int x, y; unsigned int wd, ht; } WinRec;
static WinRec *wins = NULL;
static int nwins = 0, capwins = 0;

static WinRec *find_win(Window w) {
  int i;
  for (i = nwins - 1; i >= 0; i--)
    if (wins[i].w == w) return &wins[i];
  return NULL;
}
static void add_win(Window w, int x, int y, unsigned wd, unsigned ht) {
  if (nwins == capwins) {
    capwins = capwins ? 2 * capwins : 256;
    wins = (WinRec *)realloc(wins, capwins * sizeof(WinRec));
  }
  wins[nwins].w = w; wins[nwins].x = x; wins[nwins].y = y;
  wins[nwins].wd = wd ? wd : 1; wins[nwins].ht = ht ? ht : 1;
  nwins++;
}

Display *XOpenDisplay(_Xconst char *name) {
  _XPrivDisplay d;
  (void)name;
  if (the_display) return the_display;
  d = (_XPrivDisplay)calloc(1, sizeof(*d));
  memset(&the_visual, 0, sizeof(the_visual));
  the_visual.visualid = 1;
  the_visual.class = TrueColor;
  the_visual.red_mask = 0xff0000;
  the_visual.green_mask = 0x00ff00;
  the_visual.blue_mask = 0x0000ff;
  the_visual.bits_per_rgb = 8;
  the_visual.map_entries = 256;
  the_depth.depth = 24; the_depth.nvisuals = 1; the_depth.visuals = &the_visual;
  memset(&the_screen, 0, sizeof(the_screen));
  the_screen.display = (Display *)d;
  the_screen.root = ROOT_ID;
  the_screen.width = FAKE_W; the_screen.height = FAKE_H;
  the_screen.mwidth = 340; the_screen.mheight = 270;
  the_screen.ndepths = 1; the_screen.depths = &the_depth;
  the_screen.root_depth = 24;
  the_screen.root_visual = &the_visual;
  the_screen.cmap = 1;
  the_screen.white_pixel = 0xffffff;
  the_screen.black_pixel = 0;
  d->screens = &the_screen;
  d->nscreens = 1;
  d->default_screen = 0;
  d->fd = -1;
  the_display = (Display *)d;
  add_win(ROOT_ID, 0, 0, FAKE_W, FAKE_H);
  return the_display;
}
int XCloseDisplay(Display *d) { (void)d; return 0; }

/* ------------------------------------------------------------------ */
/* windows                                                              */
/* ------------------------------------------------------------------ */
Window XCreateSimpleWindow(Display *d, Window p, int x, int y, unsigned int w,
                           unsigned int h, unsigned int bw, unsigned long b,
                           unsigned long bg) {
  Window id = next_id++;
  (void)d; (void)p; (void)bw; (void)b; (void)bg;
  add_win(id, x, y, w, h);
  return id;
}
int XDestroyWindow(Display *d, Window w) { (void)d; (void)w; return 0; }
int XDestroySubwindows(Display *d, Window w) { (void)d; (void)w; return 0; }
int XMapWindow(Display *d, Window w) { (void)d; (void)w; return 0; }
int XMapRaised(Display *d, Window w) { (void)d; (void)w; return 0; }
int XMapSubwindows(Display *d, Window w) { (void)d; (void)w; return 0; }
int XRaiseWindow(Display *d, Window w) { (void)d; (void)w; return 0; }
int XLowerWindow(Display *d, Window w) { (void)d; (void)w; return 0; }
Status XIconifyWindow(Display *d, Window w, int s) { (void)d; (void)w; (void)s; return 1; }
int XMoveResizeWindow(Display *d, Window w, int x, int y, unsigned int wd, unsigned int ht) {
  WinRec *r = find_win(w); (void)d;
  if (r) { r->x = x; r->y = y; r->wd = wd ? wd : 1; r->ht = ht ? ht : 1; }
  return 0;
}
int XResizeWindow(Display *d, Window w, unsigned int wd, unsigned int ht) {
  WinRec *r = find_win(w); (void)d;
  if (r) { r->wd = wd ? wd : 1; r->ht = ht ? ht : 1; }
  return 0;
}
Status XGetGeometry(Display *d, Drawable dr, Window *root, int *x, int *y,
                    unsigned int *w, unsigned int *h, unsigned int *bw,
                    unsigned int *depth) {
  WinRec *r = find_win(dr); (void)d;
  if (root) *root = ROOT_ID;
  if (x) *x = r ? r->x : 0;
  if (y) *y = r ? r->y : 0;
  if (w) *w = r ? r->wd : 640;
  if (h) *h = r ? r->ht : 480;
  if (bw) *bw = 0;
  if (depth) *depth = 24;
  return 1;
}
Status XGetWindowAttributes(Display *d, Window w, XWindowAttributes *a) {
  WinRec *r = find_win(w);
  memset(a, 0, sizeof(*a));
  a->x = r ? r->x : 0; a->y = r ? r->y : 0;
  a->width = r ? (int)r->wd : 640; a->height = r ? (int)r->ht : 480;
  a->depth = 24; a->visual = &the_visual; a->root = ROOT_ID;
  a->colormap = 1; a->map_state = IsViewable; a->screen = &the_screen;
  (void)d;
  return 1;
}
int XSelectInput(Display *d, Window w, long m) { (void)d; (void)w; (void)m; return 0; }
int XSetWindowBackground(Display *d, Window w, unsigned long p) { (void)d; (void)w; (void)p; return 0; }
int XSetWindowBackgroundPixmap(Display *d, Window w, Pixmap p) { (void)d; (void)w; (void)p; return 0; }
int XSetWindowBorder(Display *d, Window w, unsigned long p) { (void)d; (void)w; (void)p; return 0; }
int XSetWindowBorderWidth(Display *d, Window w, unsigned int b) { (void)d; (void)w; (void)b; return 0; }
int XDefineCursor(Display *d, Window w, Cursor c) { (void)d; (void)w; (void)c; return 0; }
Cursor XCreateFontCursor(Display *d, unsigned int s) { (void)d; (void)s; return next_id++; }
int XSetInputFocus(Display *d, Window f, int r, Time t) { (void)d; (void)f; (void)r; (void)t; return 0; }
int XGetInputFocus(Display *d, Window *f, int *r) { (void)d; if (f) *f = ROOT_ID; if (r) *r = 0; return 0; }
void XSetWMName(Display *d, Window w, XTextProperty *t) { (void)d; (void)w; (void)t; }
void XSetWMProperties(Display *d, Window w, XTextProperty *wn, XTextProperty *in,
                      char **argv, int argc, XSizeHints *nh, XWMHints *wh, XClassHint *ch) {
  (void)d; (void)w; (void)wn; (void)in; (void)argv; (void)argc; (void)nh; (void)wh; (void)ch;
}
Status XSetWMProtocols(Display *d, Window w, Atom *p, int n) { (void)d; (void)w; (void)p; (void)n; return 1; }
Status XStringListToTextProperty(char **l, int n, XTextProperty *t) {
  (void)l; (void)n; if (t) memset(t, 0, sizeof(*t)); return 1;
}
Status XGetIconSizes(Display *d, Window w, XIconSize **s, int *n) {
  (void)d; (void)w; if (s) *s = NULL; if (n) *n = 0; return 0;
}
Atom XInternAtom(Display *d, _Xconst char *n, Bool o) { (void)d; (void)n; (void)o; return next_id++; }

/* ------------------------------------------------------------------ */
/* graphics contexts, pixmaps, fonts                                    */
/* ------------------------------------------------------------------ */
GC XCreateGC(Display *d, Drawable dr, unsigned long m, XGCValues *v) {
  (void)d; (void)dr; (void)m; (void)v;
  return (GC)calloc(1, 256); /* opaque to XPP; only passed back to us */
}
int XFreeGC(Display *d, GC g) { (void)d; free(g); return 0; }
Pixmap XCreatePixmap(Display *d, Drawable dr, unsigned int w, unsigned int h, unsigned int dp) {
  Pixmap id = next_id++; (void)d; (void)dr; (void)dp;
  add_win(id, 0, 0, w, h);
  return id;
}
Pixmap XCreateBitmapFromData(Display *d, Drawable dr, _Xconst char *data, unsigned int w, unsigned int h) {
  (void)data; return XCreatePixmap(d, dr, w, h, 1);
}
Pixmap XCreatePixmapFromBitmapData(Display *d, Drawable dr, char *data, unsigned int w, unsigned int h,
                                   unsigned long fg, unsigned long bg, unsigned int dp) {
  (void)data; (void)fg; (void)bg; return XCreatePixmap(d, dr, w, h, dp);
}
int XFreePixmap(Display *d, Pixmap p) { (void)d; (void)p; return 0; }
int XReadBitmapFileData(_Xconst char *f, unsigned int *w, unsigned int *h, unsigned char **data,
                        int *xh, int *yh) {
  (void)f; (void)w; (void)h; (void)data; (void)xh; (void)yh;
  return BitmapOpenFailed;
}
int XFree(void *p) { free(p); return 0; }

XFontStruct *XLoadQueryFont(Display *d, _Xconst char *name) {
  /* A fixed-width 8x13 "font".  XPP derives its character-cell metrics
     (DCURX, DCURY) from these numbers. */
  XFontStruct *f = (XFontStruct *)calloc(1, sizeof(XFontStruct));
  (void)d; (void)name;
  f->fid = next_id++;
  f->ascent = 11; f->descent = 2;
  f->max_bounds.width = 8; f->min_bounds.width = 8;
  f->max_bounds.ascent = 11; f->max_bounds.descent = 2;
  return f;
}
int XUnloadFont(Display *d, Font f) { (void)d; (void)f; return 0; }
int XTextWidth(XFontStruct *f, _Xconst char *s, int n) { (void)f; (void)s; return 8 * n; }

/* ------------------------------------------------------------------ */
/* colours                                                              */
/* ------------------------------------------------------------------ */
Status XAllocColor(Display *d, Colormap c, XColor *x) {
  (void)d; (void)c;
  x->pixel = ((unsigned long)(x->red >> 8) << 16) | ((unsigned long)(x->green >> 8) << 8) |
             (unsigned long)(x->blue >> 8);
  return 1;
}
Status XParseColor(Display *d, Colormap c, _Xconst char *spec, XColor *x) {
  unsigned int r = 0, g = 0, b = 0; (void)d; (void)c;
  if (spec && spec[0] == '#' && strlen(spec) >= 7) sscanf(spec + 1, "%2x%2x%2x", &r, &g, &b);
  x->red = (unsigned short)(r << 8); x->green = (unsigned short)(g << 8); x->blue = (unsigned short)(b << 8);
  x->flags = DoRed | DoGreen | DoBlue;
  return 1;
}
int XQueryColors(Display *d, Colormap c, XColor *x, int n) {
  int i; (void)d; (void)c;
  for (i = 0; i < n; i++) {
    x[i].red = (unsigned short)(((x[i].pixel >> 16) & 0xff) << 8);
    x[i].green = (unsigned short)(((x[i].pixel >> 8) & 0xff) << 8);
    x[i].blue = (unsigned short)((x[i].pixel & 0xff) << 8);
  }
  return 1;
}

/* ------------------------------------------------------------------ */
/* drawing: all no-ops                                                  */
/* ------------------------------------------------------------------ */
int XClearArea(Display *d, Window w, int x, int y, unsigned int wd, unsigned int h, Bool e) {
  (void)d; (void)w; (void)x; (void)y; (void)wd; (void)h; (void)e; return 0; }
int XClearWindow(Display *d, Window w) { (void)d; (void)w; return 0; }
int XCopyArea(Display *d, Drawable s, Drawable t, GC g, int sx, int sy, unsigned int w,
              unsigned int h, int dx, int dy) {
  (void)d; (void)s; (void)t; (void)g; (void)sx; (void)sy; (void)w; (void)h; (void)dx; (void)dy; return 0; }
int XDrawArc(Display *d, Drawable w, GC g, int x, int y, unsigned int a, unsigned int b, int c, int e) {
  (void)d; (void)w; (void)g; (void)x; (void)y; (void)a; (void)b; (void)c; (void)e; return 0; }
int XFillArc(Display *d, Drawable w, GC g, int x, int y, unsigned int a, unsigned int b, int c, int e) {
  (void)d; (void)w; (void)g; (void)x; (void)y; (void)a; (void)b; (void)c; (void)e; return 0; }
int XDrawLine(Display *d, Drawable w, GC g, int a, int b, int c, int e) {
  (void)d; (void)w; (void)g; (void)a; (void)b; (void)c; (void)e; return 0; }
int XDrawPoint(Display *d, Drawable w, GC g, int x, int y) { (void)d; (void)w; (void)g; (void)x; (void)y; return 0; }
int XDrawRectangle(Display *d, Drawable w, GC g, int x, int y, unsigned int a, unsigned int b) {
  (void)d; (void)w; (void)g; (void)x; (void)y; (void)a; (void)b; return 0; }
int XFillRectangle(Display *d, Drawable w, GC g, int x, int y, unsigned int a, unsigned int b) {
  (void)d; (void)w; (void)g; (void)x; (void)y; (void)a; (void)b; return 0; }
int XDrawString(Display *d, Drawable w, GC g, int x, int y, _Xconst char *s, int n) {
  (void)d; (void)w; (void)g; (void)x; (void)y; (void)s; (void)n; return 0; }
int XSetBackground(Display *d, GC g, unsigned long p) { (void)d; (void)g; (void)p; return 0; }
int XSetForeground(Display *d, GC g, unsigned long p) { (void)d; (void)g; (void)p; return 0; }
int XSetFillStyle(Display *d, GC g, int s) { (void)d; (void)g; (void)s; return 0; }
int XSetFont(Display *d, GC g, Font f) { (void)d; (void)g; (void)f; return 0; }
int XSetFunction(Display *d, GC g, int f) { (void)d; (void)g; (void)f; return 0; }
int XSetDashes(Display *d, GC g, int o, _Xconst char *l, int n) { (void)d; (void)g; (void)o; (void)l; (void)n; return 0; }
int XSetLineAttributes(Display *d, GC g, unsigned int w, int s, int c, int j) {
  (void)d; (void)g; (void)w; (void)s; (void)c; (void)j; return 0; }
int XFlush(Display *d) { (void)d; return 0; }
Bool XkbBell(Display *d, Window w, int p, Atom n) { (void)d; (void)w; (void)p; (void)n; return True; }

XImage *XGetImage(Display *d, Drawable dr, int x, int y, unsigned int w, unsigned int h,
                  unsigned long pm, int fmt) {
  (void)d; (void)dr; (void)x; (void)y; (void)w; (void)h; (void)pm; (void)fmt;
  pyxpp_fail("screen capture (XGetImage) is not available headless; "
             "use the Python plotting helpers instead");
  return NULL;
}

/* ------------------------------------------------------------------ */
/* events: there are none                                               */
/* ------------------------------------------------------------------ */
int XPending(Display *d) { (void)d; return 0; }
Status XSendEvent(Display *d, Window w, Bool p, long m, XEvent *e) { (void)d; (void)w; (void)p; (void)m; (void)e; return 1; }
KeyCode XKeysymToKeycode(Display *d, KeySym k) { (void)d; return (KeyCode)(k & 0xff); }
int XLookupString(XKeyEvent *e, char *buf, int n, KeySym *ks, XComposeStatus *st) {
  (void)e; (void)st; if (ks) *ks = 0; if (buf && n > 0) buf[0] = 0; return 0;
}
int XNextEvent(Display *d, XEvent *ev) {
  (void)d; memset(ev, 0, sizeof(*ev));
  pyxpp_fail("this XPP command entered an interactive loop that has no "
             "headless equivalent yet");
  return 0;
}
