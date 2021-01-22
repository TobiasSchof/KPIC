
#ifndef UTIL_MACROS_H
#define UTIL_MACROS_H

/* Convert a macro into a string.  This lets the compiler command line
 * be simple, containing something like KTLSERVICE=xyz, and then we
 * can use STRINGIFY(KTLSERVICE) to generate "xyz".
 */
#define QUOTE(x) #x
#define STRINGIFY(x) QUOTE(x)

/* Basic pasting, but doesn't work if x or y is itself a macro */
#define JOIN(x, y) x ## y
#define JOIN3(x, y, z) x ## y ## z

/* A join that works if x or y is a macro.
 * This lets us write something like JOINM(KTLSERVICE, _abc) and the
 * result (for KTLSERVICE=xyz) will be xyz_abc.
 */
#define JOINM(x, y) JOIN(x,y)
#define JOINM3(x, y, z) JOIN3(x,y,z)

#endif /* UTIL_MACROS_H */
