/*
 * headless.c -- the glue that turns XPPAUT into a library.
 *
 * XPP's GUI is a keyboard/menu machine: a key press reaches commander(),
 * which calls a menu handler, which asks the user questions through a small
 * set of dialog primitives (new_float, pop_up_list, two_choice,
 * do_string_box, file_selector, ...).  The build script renames the original
 * X11 versions of those primitives to gui_<name> and links in the versions
 * below instead.  Each one takes its answer from an "input tape" -- a FIFO of
 * strings filled from Python -- or, if the tape is empty, accepts XPP's own
 * default, exactly as if the user had pressed Enter.
 *
 * Every question asked and every answer used is appended to a transcript so
 * the Python side can show what a button asked for.
 *
 * Errors: anything that would kill or hang the process (exit(), an
 * unhandled interactive loop) longjmps back to the entry point with a
 * message, which Python raises as XPPError.
 */
#include <setjmp.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <ctype.h>
#include <X11/Xlib.h>

#include "auto_nox.h"
#include "mykeydef.h"

#define EXPORT __attribute__((visibility("default")))

/* ------------------------------------------------------------------ */
/* XPP internals we need                                                */
/* ------------------------------------------------------------------ */
extern void do_main(int argc, char **argv);
extern void commander(char ch);
extern void run_the_commands(int com);
extern int do_calc(char *temp, double *z);
extern void traverse_out(DIAGRAM *d, int *ix, int *iy, int dodraw);
extern void redraw_diagram(void);
extern void evaluate_derived(void);
extern void redraw_params(void);
extern void redraw_ics(void);
extern void set_ivar(int i, double value);
extern void get_ic(int it, double *x);
extern void set_option(char *s1, char *s2, int force, void *mask);
extern void do_meth(void);
extern int get_val(char *name, double *value);
extern int set_val(char *name, double value);
extern void do_sing_info(double *x, double eps, double err, double big, int maxit,
                         int n, double *er, double *em, int *ierr);
extern void do_auto_win(void);
extern void auto_plot_par(void), auto_num_par(void), auto_grab(void), auto_run(void);
extern void draw_bif_axes(void), auto_per_par(void), auto_params(void), auto_file(void);
extern void get_num_par(char ch);
extern void help(void);

extern int help_menu;
extern int NODE, NEQ, NUPAR, NMarkov, FIX_VAR, storind, Xup, XPPBatch;
extern char uvar_names[][12];
extern char upar_names[][11];
extern float **storage;
extern double last_ic[];
extern double NEWT_ERR, EVEC_ERR, BOUND;
extern int EVEC_ITER;
extern FILE *logfile;
extern int XPPVERBOSE;
extern int RunImmediately;

extern GRABPT grabpt;
extern BIFUR Auto;
extern DIAGRAM *bifd, *CUR_DIAGRAM;
extern int NBifs, NAutoPar, Auto_index_to_array[];
extern double constants[];

/* ------------------------------------------------------------------ */
/* error handling                                                       */
/* ------------------------------------------------------------------ */
static jmp_buf *guard = NULL;
static char errbuf[1024];
static int in_api = 0;

EXPORT const char *pyxpp_error(void) { return errbuf; }

void pyxpp_fail(const char *fmt, ...) {
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(errbuf, sizeof errbuf, fmt, ap);
  va_end(ap);
  if (guard) longjmp(*guard, 1);
  fprintf(stderr, "pyxpp fatal (no guard): %s\n", errbuf);
  abort();
}

/* every exit() inside the library is redirected here by force.h, so XPP
   can never terminate the Python interpreter. */
void pyxpp_exit(int code) { pyxpp_fail("XPP tried to exit (code %d)", code); }

/* run BODY under a setjmp guard; returns 0 on success, -1 on failure */
#define GUARDED(BODY)                                  \
  do {                                                 \
    jmp_buf jb, *old = guard;                          \
    errbuf[0] = 0;                                     \
    guard = &jb;                                       \
    in_api = 1; unanswered = 0;                        \
    if (setjmp(jb) == 0) {                             \
      BODY;                                            \
      guard = old; in_api = 0;                         \
      return 0;                                        \
    }                                                  \
    guard = old; in_api = 0;                           \
    return -1;                                         \
  } while (0)

/* ------------------------------------------------------------------ */
/* input tape and transcript                                            */
/* ------------------------------------------------------------------ */
#define TAPE_MAX 4096
static char *tape[TAPE_MAX];
static int tape_head = 0, tape_tail = 0;

EXPORT void pyxpp_tape_clear(void) {
  while (tape_head < tape_tail) free(tape[tape_head++]);
  tape_head = tape_tail = 0;
}
EXPORT int pyxpp_tape_push(const char *s) {
  if (tape_tail >= TAPE_MAX) return -1;
  tape[tape_tail++] = strdup(s);
  return 0;
}
EXPORT int pyxpp_tape_len(void) { return tape_tail - tape_head; }

/* pops the next answer; returns NULL if tape empty (caller uses default).
   Caller must free. */
static char *tape_pop(void) {
  if (tape_head >= tape_tail) return NULL;
  return tape[tape_head++];
}

/* Some XPP loops keep asking until they get a particular answer (the
   tutorial, "Parameter:" loops, ...).  With an empty tape that would spin
   forever, so too many unanswered questions in one call is an error. */
static int unanswered = 0;
#define MAX_UNANSWERED 500
static void no_answer(const char *what) {
  if (++unanswered > MAX_UNANSWERED)
    pyxpp_fail("XPP asked '%s' (and others) %d times without an answer; "
               "supply answers or end the loop explicitly", what, MAX_UNANSWERED);
}

static int is_escape(const char *s) {
  return s && (strcmp(s, "\x1b") == 0 || strcasecmp(s, "<esc>") == 0);
}

static char *tr = NULL;
static size_t trlen = 0, trcap = 0;
static void tlog(const char *fmt, ...) {
  char line[2048];
  va_list ap;
  size_t n;
  va_start(ap, fmt);
  vsnprintf(line, sizeof line, fmt, ap);
  va_end(ap);
  n = strlen(line);
  if (trlen + n + 2 > trcap) {
    trcap = 2 * (trcap + n + 2);
    tr = (char *)realloc(tr, trcap);
  }
  memcpy(tr + trlen, line, n);
  trlen += n;
  tr[trlen++] = '\n';
  tr[trlen] = 0;
}
EXPORT const char *pyxpp_transcript(void) { return tr ? tr : ""; }
EXPORT void pyxpp_transcript_clear(void) { trlen = 0; if (tr) tr[0] = 0; }

static void strip(char *s) {
  char *p = s, *e;
  while (*p && isspace((unsigned char)*p)) p++;
  memmove(s, p, strlen(p) + 1);
  e = s + strlen(s);
  while (e > s && isspace((unsigned char)e[-1])) *--e = 0;
}

/* ------------------------------------------------------------------ */
/* replacements for XPP's dialog primitives                             */
/* ------------------------------------------------------------------ */

/* one-line text prompt.  1 = accepted, 0 = cancelled (matches original) */
int new_string(char *name, char *value) {
  char *a = tape_pop();
  if (a == NULL) {
    no_answer(name);
    tlog("prompt  %s [%s] -> (default)", name, value);
    return 1;
  }
  if (is_escape(a)) {
    tlog("prompt  %s [%s] -> <esc>", name, value);
    free(a);
    return 0;
  }
  tlog("prompt  %s [%s] -> %s", name, value, a);
  strcpy(value, a); /* XPP buffers are >= 80 chars; Python enforces limits */
  free(a);
  return 1;
}

int new_float(char *name, double *value) {
  char tvalue[256];
  double z;
  snprintf(tvalue, sizeof tvalue, "%.16g", *value);
  if (new_string(name, tvalue) == 0 || strlen(tvalue) == 0) return -1;
  if (tvalue[0] == '%') {
    if (do_calc(&tvalue[1], &z) != -1) *value = z;
    return 0;
  }
  *value = atof(tvalue);
  return 0;
}

int new_int(char *name, int *value) {
  char svalue[256];
  snprintf(svalue, sizeof svalue, "%d", *value);
  if (new_string(name, svalue) == 0 || strlen(svalue) == 0) return -1;
  *value = atoi(svalue);
  return 0;
}

/* match an answer against a menu: a single key char, or the entry label
   (case-insensitive, ignoring parentheses), or a unique label prefix. */
static int match_menu(const char *ans, char **list, const char *key, int n) {
  int i, hit = -1, nhit = 0;
  char lab[256], a[256];
  if (strlen(ans) == 1) {
    for (i = 0; i < n; i++)
      if (tolower((unsigned char)key[i]) == tolower((unsigned char)ans[0])) return i;
    if (ans[0] == 27) return -2;
    return -1;
  }
  snprintf(a, sizeof a, "%s", ans);
  for (i = 0; a[i]; i++) a[i] = (char)tolower((unsigned char)a[i]);
  for (i = 0; i < n; i++) {
    const char *s = list[i];
    int k = 0;
    for (; *s && k < 255; s++)
      if (*s != '(' && *s != ')') lab[k++] = (char)tolower((unsigned char)*s);
    lab[k] = 0;
    strip(lab);
    if (strcmp(lab, a) == 0) return i;
    if (strncmp(lab, a, strlen(a)) == 0) { hit = i; nhit++; }
  }
  return nhit == 1 ? hit : -1;
}

int pop_up_list(Window *root, char *title, char **list, char *key, int n, int max,
                int def, int x, int y, char **hints, Window hwin, char *httxt) {
  char *a = tape_pop();
  int i;
  (void)root; (void)max; (void)x; (void)y; (void)hints; (void)hwin; (void)httxt;
  if (a == NULL || is_escape(a)) {
    if (a == NULL) no_answer(title);
    tlog("menu    %s -> %s", title, a ? "<esc>" : "(cancel: no answer on tape)");
    free(a);
    return 27;
  }
  i = match_menu(a, list, key, n);
  if (i < 0) {
    char msg[512];
    snprintf(msg, sizeof msg, "menu '%s' has no entry '%s'", title, a);
    free(a);
    pyxpp_fail("%s", msg);
  }
  tlog("menu    %s -> %s", title, list[i]);
  free(a);
  (void)def;
  return (int)key[i];
}

int two_choice(char *c1, char *c2, char *q, char *key, int x, int y, Window w, char *title) {
  char *a = tape_pop();
  int r;
  (void)x; (void)y; (void)w; (void)title;
  if (a == NULL) {
    /* the GUI returns the Enter key code, which callers treat as neither
       choice (in practice: "no") */
    no_answer(q);
    tlog("choice  %s (%s/%s) -> <enter> (no answer on tape)", q, c1, c2);
    return 13;
  }
  if (is_escape(a)) { r = 27; }
  else if (tolower((unsigned char)a[0]) == tolower((unsigned char)key[0]) || strcasecmp(a, c1) == 0) r = key[0];
  else if (tolower((unsigned char)a[0]) == tolower((unsigned char)key[1]) || strcasecmp(a, c2) == 0) r = key[1];
  else { char m[300]; snprintf(m, sizeof m, "choice '%s' expects %s or %s, got '%s'", q, c1, c2, a); free(a); pyxpp_fail("%s", m); r = 0; }
  tlog("choice  %s (%s/%s) -> %s", q, c1, c2, r == key[0] ? c1 : (r == 27 ? "<esc>" : c2));
  free(a);
  return r;
}

/* Apply "name=value;name=value" to a list of fields.  Field names are
   matched case-insensitively after stripping a trailing '=' and spaces. */
static int apply_assignments(const char *spec, const char *title, int n, char **names,
                             char *values, int stride) {
  char *buf = strdup(spec), *save = NULL, *tok;
  int i, found;
  for (tok = strtok_r(buf, ";\n", &save); tok; tok = strtok_r(NULL, ";\n", &save)) {
    char *eq = strchr(tok, '='), lhs[256], nm[256];
    if (!eq) continue;
    *eq = 0;
    snprintf(lhs, sizeof lhs, "%s", tok);
    strip(lhs);
    found = 0;
    for (i = 0; i < n; i++) {
      /* XPP marks drop-down fields with a "*<digit>" prefix: skip it */
      const char *src = names[i];
      if (src[0] == '*' && isdigit((unsigned char)src[1])) src += 2;
      snprintf(nm, sizeof nm, "%s", src);
      if (strlen(nm) && nm[strlen(nm) - 1] == '=') nm[strlen(nm) - 1] = 0;
      strip(nm);
      {
        /* also accept the name without a trailing "(Y/N)"-style hint or ':' */
        char shortnm[256];
        char *paren;
        snprintf(shortnm, sizeof shortnm, "%s", nm);
        paren = strrchr(shortnm, '(');
        if (paren && paren > shortnm && shortnm[strlen(shortnm) - 1] == ')') *paren = 0;
        strip(shortnm);
        if (strlen(shortnm) && shortnm[strlen(shortnm) - 1] == ':') shortnm[strlen(shortnm) - 1] = 0;
        strip(shortnm);
        if (strcasecmp(shortnm, lhs) == 0) snprintf(nm, sizeof nm, "%s", lhs);
      }
      if (strcasecmp(nm, lhs) == 0) {
        char v[512];
        snprintf(v, sizeof v, "%s", eq + 1);
        strip(v);
        if ((int)strlen(v) >= stride) { free(buf); pyxpp_fail("value for %s too long", lhs); }
        tlog("field   %s.%s = %s (was %s)", title, nm, v, values + i * stride);
        strcpy(values + i * stride, v);
        found = 1;
        break;
      }
    }
    if (!found) {
      char m[600], all[400] = "";
      for (i = 0; i < n && strlen(all) < 350; i++) {
        const char *src = names[i];
        if (src[0] == '*' && isdigit((unsigned char)src[1])) src += 2;
        strcat(all, "'"); strcat(all, src); strcat(all, "' ");
      }
      snprintf(m, sizeof m, "dialog '%s' has no field '%s' (fields: %s)", title, lhs, all);
      free(buf);
      pyxpp_fail("%s", m);
    }
  }
  free(buf);
  return 0;
}

#define MAX_LEN_SBOX 25
/* multi-field dialog.  Returns DONE_ALL(2) on accept, FORGET_ALL(0) on esc */
int do_string_box(int n, int row, int col, char *title, char **names,
                  char values[][MAX_LEN_SBOX], int maxchar) {
  char *a = tape_pop();
  (void)row; (void)col; (void)maxchar;
  if (a == NULL) { no_answer(title); tlog("dialog  %s -> (defaults)", title); return 2; }
  if (is_escape(a)) { tlog("dialog  %s -> <esc>", title); free(a); return 0; }
  apply_assignments(a, title, n, names, &values[0][0], MAX_LEN_SBOX);
  free(a);
  return 2;
}

/* RHS / function editor */
#define MAX_LEN_EBOX 86
int do_edit_box(int n, char *title, char **names, char **values) {
  char *a = tape_pop(), *flat;
  int i;
  if (a == NULL) { tlog("editor  %s -> (unchanged)", title); return 0; }
  if (is_escape(a)) { tlog("editor  %s -> <esc>", title); free(a); return 0; }
  flat = (char *)calloc((size_t)n, MAX_LEN_EBOX);
  for (i = 0; i < n; i++) snprintf(flat + i * MAX_LEN_EBOX, MAX_LEN_EBOX, "%s", values[i]);
  apply_assignments(a, title, n, names, flat, MAX_LEN_EBOX);
  for (i = 0; i < n; i++) strcpy(values[i], flat + i * MAX_LEN_EBOX);
  free(flat);
  free(a);
  return 2;
}

/* check-box list: answer is a comma list of 0/1 or of entry names to tick */
int do_choice_box(Window root, char *wname, int n, int mcc, char **names, int *check, int type) {
  char *a = tape_pop(), *save = NULL, *tok;
  int i;
  (void)root; (void)mcc; (void)type;
  if (a == NULL) { tlog("checks  %s -> (unchanged)", wname); return 1; }
  if (is_escape(a)) { free(a); tlog("checks  %s -> <esc>", wname); return 0; }
  if (strspn(a, "01, ") == strlen(a)) {
    i = 0;
    for (tok = strtok_r(a, ", ", &save); tok && i < n; tok = strtok_r(NULL, ", ", &save))
      check[i++] = atoi(tok);
  } else {
    for (i = 0; i < n; i++) check[i] = 0;
    for (tok = strtok_r(a, ",", &save); tok; tok = strtok_r(NULL, ",", &save)) {
      strip(tok);
      for (i = 0; i < n; i++) {
        char nm[256]; snprintf(nm, sizeof nm, "%s", names[i]); strip(nm);
        if (strcasecmp(nm, tok) == 0) check[i] = 1;
      }
    }
  }
  tlog("checks  %s -> set", wname);
  free(a);
  return 1;
}

int get_dialog(char *wname, char *name, char *value, char *ok, char *cancel, int max) {
  char *a = tape_pop();
  (void)ok; (void)cancel;
  if (a == NULL) { no_answer(name); tlog("dialog  %s: %s [%s] -> (default)", wname, name, value); return 1; }
  if (is_escape(a)) { free(a); tlog("dialog  %s -> <esc>", wname); return 0; }
  if ((int)strlen(a) >= max) { free(a); pyxpp_fail("answer too long for %s", name); }
  tlog("dialog  %s: %s [%s] -> %s", wname, name, value, a);
  strcpy(value, a);
  free(a);
  return 1;
}

int file_selector(char *title, char *file, char *wild) {
  char *a = tape_pop();
  if (a == NULL || is_escape(a) || !*a) {
    tlog("file    %s (%s) -> (cancel)", title, wild);
    free(a);
    return 0;
  }
  tlog("file    %s (%s) -> %s", title, wild, a);
  strcpy(file, a);
  free(a);
  return 1;
}

/* mouse clicks: the answer is "ix,iy" in window pixels.  Python converts
   data coordinates to pixels with pyxpp_real_to_pixel. */
int get_mouse_xy(int *x, int *y, Window w) {
  char *a = tape_pop();
  (void)w;
  if (a == NULL || is_escape(a)) {
    tlog("click   -> (cancel)");
    free(a);
    return 0;
  }
  if (sscanf(a, "%d,%d", x, y) != 2) { free(a); pyxpp_fail("click answer must be 'ix,iy'"); }
  tlog("click   -> %d,%d", *x, *y);
  free(a);
  return 1;
}

int rubber(int *x1, int *y1, int *x2, int *y2, Window w, int f) {
  char *a = tape_pop();
  (void)w; (void)f;
  if (a == NULL || is_escape(a)) { tlog("drag    -> (cancel)"); free(a); return 0; }
  if (sscanf(a, "%d,%d,%d,%d", x1, y1, x2, y2) != 4) { free(a); pyxpp_fail("drag answer must be 'x1,y1,x2,y2'"); }
  tlog("drag    -> %d,%d,%d,%d", *x1, *y1, *x2, *y2);
  free(a);
  return 1;
}

void respond_box(char *button, char *message) {
  (void)button;
  tlog("message %s", message);
}

/* calculator: each tape entry is an expression; stops at <esc> or empty */
void q_calc(void) {
  char *a;
  double z;
  while ((a = tape_pop()) != NULL) {
    if (is_escape(a)) { free(a); break; }
    if (do_calc(a, &z) != -1) tlog("calc    %s = %.16g", a, z);
    else tlog("calc    %s = <error>", a);
    free(a);
  }
}

/* AUTO "Grab": answer selects a diagram point.
     "<n>"     the point with label n
     "#<k>"    the k-th point in the diagram list (0 = first, -1 = last)
     "<esc>"   cancel */
void traverse_diagram(void) {
  char *a = tape_pop();
  DIAGRAM *d = bifd, *e;
  int ix, iy, i, k;
  if (NBifs < 2 || d == NULL) { tlog("grab    -> (no diagram)"); free(a); return; }
  if (a == NULL || is_escape(a)) { tlog("grab    -> (cancel)"); free(a); return; }
  if (a[0] == '#') {
    k = atoi(a + 1);
    if (k < 0) { for (e = d; e->next; e = e->next) ; d = e; k = -k - 1; while (k-- > 0 && d->prev) d = d->prev; }
    else while (k-- > 0 && d->next) d = d->next;
  } else {
    int lab = atoi(a);
    for (e = bifd; e; e = e->next) if (e->lab == lab) break;
    if (e == NULL) { free(a); pyxpp_fail("no diagram point with label %d", lab); }
    d = e;
  }
  tlog("grab    -> %s (branch %d, pt %d, label %d)", a, d->ibr, d->ntot, d->lab);
  free(a);
  CUR_DIAGRAM = d;
  traverse_out(d, &ix, &iy, 1);
  /* identical to the Enter branch of the GUI traverse_diagram() */
  grabpt.ibr = d->ibr;
  grabpt.lab = d->lab;
  for (i = 0; i < 8; i++) grabpt.par[i] = d->par[i];
  grabpt.icp1 = d->icp1;
  grabpt.icp2 = d->icp2;
  grabpt.per = d->per;
  grabpt.torper = d->torper;
  for (i = 0; i < NODE; i++) {
    grabpt.uhi[i] = d->uhi[i];
    grabpt.ulo[i] = d->ulo[i];
    grabpt.u0[i] = d->u0[i];
    grabpt.ubar[i] = d->ubar[i];
    set_ivar(i + 1, grabpt.u0[i]);
  }
  get_ic(0, grabpt.u0);
  grabpt.flag = 1;
  grabpt.itp = d->itp;
  grabpt.ntot = d->ntot;
  grabpt.nfpar = d->nfpar;
  grabpt.index = d->index;
  for (i = 0; i < NAutoPar; i++) constants[Auto_index_to_array[i]] = grabpt.par[i];
  evaluate_derived();
  redraw_params();
  redraw_ics();
}

/* ------------------------------------------------------------------ */
/* per-instance AUTO scratch directory (replaces $HOME in auto_nox.c)   */
/* ------------------------------------------------------------------ */
static char autodir[1024] = "";
char *pyxpp_auto_home(void) {
  if (autodir[0]) return autodir;
  return getenv("HOME");
}
EXPORT void pyxpp_set_auto_dir(const char *d) { snprintf(autodir, sizeof autodir, "%s", d); }

/* ------------------------------------------------------------------ */
/* API                                                                  */
/* ------------------------------------------------------------------ */
EXPORT int pyxpp_init(int argc, char **argv, const char *logpath) {
  if (logpath && *logpath) {
    FILE *f = fopen(logpath, "a");
    if (f) logfile = f;
  }
  GUARDED({
    do_main(argc, argv);
    /* what do_events() does before its loop */
    help();
    if (RunImmediately == 1) { run_the_commands(4); RunImmediately = 0; }
    if (logfile) fflush(logfile);
  });
}

EXPORT void pyxpp_flush_log(void) { if (logfile) fflush(logfile); }

/* the logfile is reset by do_main; keep it pointed at our file */
EXPORT int pyxpp_set_log(const char *logpath) {
  FILE *f = fopen(logpath, "a");
  if (!f) return -1;
  logfile = f;
  return 0;
}

/* one key press in the main window, honouring XPP's menu state */
EXPORT int pyxpp_key(int ch) { GUARDED(commander((char)ch)); }

/* run a command by its internal id (menudrive.h M_* constants) */
EXPORT int pyxpp_command(int com) { GUARDED(run_the_commands(com)); }

/* numerics menu key (same as pressing 'u' then ch) */
EXPORT int pyxpp_num_key(int ch) { GUARDED(get_num_par((char)ch)); }

EXPORT int pyxpp_menu_state(void) { return help_menu; }
EXPORT int pyxpp_main_menu(void) { GUARDED(help()); }

/* AUTO window buttons (keys a n g r d c u p f).  Opens the window first. */
EXPORT int pyxpp_auto_key(int ch) {
  GUARDED({
    if (Auto.exist == 0) do_auto_win();
    switch (tolower(ch)) {
      case 'a': auto_plot_par(); break;
      case 'n': auto_num_par(); break;
      case 'g': auto_grab(); break;
      case 'r': auto_run(); break;
      case 'd': redraw_diagram(); break;
      case 'c': draw_bif_axes(); break;
      case 'u': auto_per_par(); break;
      case 'p': auto_params(); break;
      case 'f': auto_file(); break;
      default: pyxpp_fail("unknown AUTO key '%c'", ch);
    }
  });
}
EXPORT int pyxpp_auto_open(void) { GUARDED(if (Auto.exist == 0) do_auto_win()); }

/* set any @-option exactly as in an .ode file */
EXPORT int pyxpp_set_option(const char *name, const char *value) {
  char n[256], v[256];
  snprintf(n, sizeof n, "%s", name);
  snprintf(v, sizeof v, "%s", value);
  GUARDED({ set_option(n, v, 1, NULL); do_meth(); });
}

/* parameters and variables by name */
EXPORT int pyxpp_get_val(const char *name, double *v) {
  char n[256];
  snprintf(n, sizeof n, "%s", name);
  return get_val(n, v) ? 0 : -1;
}
EXPORT int pyxpp_set_val(const char *name, double v) {
  char n[256];
  int ok;
  snprintf(n, sizeof n, "%s", name);
  ok = set_val(n, v);
  evaluate_derived();
  return ok ? 0 : -1;
}

/* equilibrium via Newton from x (in/out); eigenvalues into er/em */
EXPORT int pyxpp_equilibrium(double *x, double *er, double *em, int *ierr) {
  GUARDED({
    evaluate_derived();
    do_sing_info(x, NEWT_ERR, EVEC_ERR, BOUND, EVEC_ITER, NODE, er, em, ierr);
  });
}

/* sizes and names */
EXPORT int pyxpp_node(void) { return NODE; }
EXPORT int pyxpp_neq(void) { return NEQ; }
EXPORT int pyxpp_nmarkov(void) { return NMarkov; }
EXPORT int pyxpp_npar(void) { return NUPAR; }
EXPORT const char *pyxpp_var_name(int i) { return uvar_names[i]; }
EXPORT const char *pyxpp_par_name(int i) { return upar_names[i]; }

/* browser data: rows = storind, cols = NEQ+1 (t first) */
EXPORT int pyxpp_data_rows(void) { return storind; }
EXPORT int pyxpp_data_cols(void) { return NEQ + 1; }
EXPORT void pyxpp_data_copy(double *out) {
  int r, c, nc = NEQ + 1;
  for (r = 0; r < storind; r++)
    for (c = 0; c < nc; c++) out[r * nc + c] = storage[c][r];
}

/* bifurcation diagram */
EXPORT int pyxpp_diag_count(void) {
  int n = 0;
  DIAGRAM *d;
  for (d = bifd; d; d = d->next) n++;
  return n;
}
/* ints: ibr ntot itp lab icp1 icp2 flag2 index nfpar  (9)
   dbl : norm per torper par[0..19]                     (23)
   vec : uhi ulo u0 ubar evr evi, each NODE long        */
EXPORT int pyxpp_diag_get(int k, int *ints, double *dbl, double *vec) {
  DIAGRAM *d = bifd;
  int i;
  while (k-- > 0 && d) d = d->next;
  if (!d) return -1;
  ints[0] = d->ibr; ints[1] = d->ntot; ints[2] = d->itp; ints[3] = d->lab;
  ints[4] = d->icp1; ints[5] = d->icp2; ints[6] = d->flag2; ints[7] = d->index;
  ints[8] = d->nfpar;
  dbl[0] = d->norm; dbl[1] = d->per; dbl[2] = d->torper;
  for (i = 0; i < 20; i++) dbl[3 + i] = d->par[i];
  for (i = 0; i < NODE; i++) {
    vec[i] = d->uhi[i];
    vec[NODE + i] = d->ulo[i];
    vec[2 * NODE + i] = d->u0[i];
    vec[3 * NODE + i] = d->ubar[i];
    vec[4 * NODE + i] = d->evr ? d->evr[i] : 0.0;
    vec[5 * NODE + i] = d->evi ? d->evi[i] : 0.0;
  }
  return 0;
}
EXPORT int pyxpp_auto_par_index(int i) { return Auto_index_to_array[i]; }
EXPORT int pyxpp_n_auto_par(void) { return NAutoPar; }

/* AUTO settings snapshot.
   ints: ntst nmx npr ncol icp1 icp2 var plot ips nfpar grab_flag grab_lab exist
   dbl : ds dsmin dsmax rl0 rl1 a0 a1 epsl epsu epss xmin xmax ymin ymax */
extern int AutoPar[];
EXPORT void pyxpp_auto_settings(int *ints, double *dbl) {
  ints[0] = Auto.ntst; ints[1] = Auto.nmx; ints[2] = Auto.npr; ints[3] = Auto.ncol;
  ints[4] = Auto.icp1; ints[5] = Auto.icp2; ints[6] = Auto.var; ints[7] = Auto.plot;
  ints[8] = Auto.ips; ints[9] = Auto.nfpar; ints[10] = grabpt.flag; ints[11] = grabpt.lab;
  ints[12] = Auto.exist;
  dbl[0] = Auto.ds; dbl[1] = Auto.dsmin; dbl[2] = Auto.dsmax; dbl[3] = Auto.rl0;
  dbl[4] = Auto.rl1; dbl[5] = Auto.a0; dbl[6] = Auto.a1; dbl[7] = Auto.epsl;
  dbl[8] = Auto.epsu; dbl[9] = Auto.epss; dbl[10] = Auto.xmin; dbl[11] = Auto.xmax;
  dbl[12] = Auto.ymin; dbl[13] = Auto.ymax;
}
EXPORT const char *pyxpp_auto_par_name(int i) { return upar_names[AutoPar[i]]; }

/* data-coordinate -> draw-window pixel, for answering mouse prompts */
extern void scale_to_screen(double x, double y, int *i, int *j);
EXPORT void pyxpp_real_to_pixel(double x, double y, int *ix, int *iy) {
  scale_to_screen(x, y, ix, iy);
}

/* Phase space > Choose: which variables live on a circle.
   Answer: comma list of variable names; empty/<esc> keeps the old choice. */
extern int itor[], TORUS;
void choose_torus(void) {
  char *a = tape_pop(), *save = NULL, *tok;
  int i, any = 0;
  if (a == NULL || is_escape(a)) { tlog("torus   -> (unchanged)"); free(a); return; }
  for (i = 0; i < NEQ; i++) itor[i] = 0;
  for (tok = strtok_r(a, ", ", &save); tok; tok = strtok_r(NULL, ", ", &save)) {
    int found = 0;
    for (i = 0; i < NEQ; i++)
      if (strcasecmp(uvar_names[i], tok) == 0) { itor[i] = 1; found = 1; }
    if (!found) { char m[200]; snprintf(m, sizeof m, "no variable '%s'", tok); free(a); pyxpp_fail("%s", m); }
  }
  tlog("torus   -> %s", a);
  free(a);
  for (i = 0; i < NEQ; i++) if (itor[i] == 1) any = 1;
  TORUS = any;
}
