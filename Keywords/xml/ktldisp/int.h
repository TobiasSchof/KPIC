
RCSID_DEF(H_int_RCSID,"$Id: ktlxml2fiord.sin 96802 2017-08-23 14:40:23Z wdeich $");
FIORD_BROAD_INFO inst_int_resp2_kval_info = {
    OUT_RESP_MSG,
    (void *) NULL,
    (caddr_t) NULL,
    (int (*)()) NULL,
    RESP_KVAL_FUNC,
    KVAL_NOTIFY
};

FIORD_BROAD_INFO inst_int_bcast_kval_info = {
    BCAST_MSG,
    (void *) NULL,
    (caddr_t) NULL,
    (int (*)()) NULL,
    GET_KVAL_FUNC,
    KVAL_BROADCAST
};

/* The following definitions are leveraged to enable
   KTL_CONTINUOUS keyword reads/broadcasts.
*/

#define KW_MAP_NAME     int_id_to_kw_map
#define KW_MAP_TYPE     BASIC_KW_INFO
KW_MAP_TYPE KW_MAP_NAME[]=
{
	{ DISPERR, "DISPERR" },
	{ DISPMEM, "DISPMEM" },
	{ DISPSTA, "DISPSTA" },
	{ DISPSTOP, "DISPSTOP" },
	{ TEST, "TEST" },
	{ UPTIME, "UPTIME" },
    { TTMERR, "TTMERR" },
    { MCERR, "MCERR" }
};

#define KW_MAP_SIZE ( sizeof KW_MAP_NAME / sizeof (KW_MAP_TYPE) )

/* fiord */

#include "fiord/make_disp2_int_func.h"   /* define make_xxx_func macros */

/* broadcast message handler */

make_disp2_int_get_kvals_func( GET_KVAL_FUNC )
make_disp2_int_input_func  (input_disperr,  DISPERR)
/* DISPERR is a read-only keyword (no output function) */
make_disp2_int_input_func  (input_dispmem,  DISPMEM)
/* DISPMEM is a read-only keyword (no output function) */
make_disp2_int_input_func  (input_dispsta,  DISPSTA)
/* DISPSTA is a read-only keyword (no output function) */
make_disp2_int_input_func  (input_dispstop,  DISPSTOP)
make_disp2_int_output_func (output_dispstop, DISPSTOP)
make_disp2_int_input_func  (input_test,  TEST)
make_disp2_int_output_func (output_test, TEST)
make_disp2_int_input_func  (input_uptime,  UPTIME)
/* UPTIME is a read-only keyword (no output function) */
make_disp2_int_input_func  (input_ttmerr,  TTMERR)
make_disp2_int_output_func (output_ttmerr, TTMERR)
make_disp2_int_input_func  (input_ttmerr,  MCERR)
make_disp2_int_output_func (output_ttmerr, MCERR)
