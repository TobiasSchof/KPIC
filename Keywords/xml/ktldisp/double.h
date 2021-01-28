
RCSID_DEF(H_double_RCSID,"$Id: ktlxml2fiord.sin 96802 2017-08-23 14:40:23Z wdeich $");
FIORD_BROAD_INFO inst_double_resp2_kval_info = {
    OUT_RESP_MSG,
    (void *) NULL,
    (caddr_t) NULL,
    (int (*)()) NULL,
    RESP_KVAL_FUNC,
    KVAL_NOTIFY
};

FIORD_BROAD_INFO inst_double_bcast_kval_info = {
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

#define KW_MAP_NAME     double_id_to_kw_map
#define KW_MAP_TYPE     BASIC_KW_INFO
KW_MAP_TYPE KW_MAP_NAME[]=
{
	{ FIUTTMX, "FIUTTMX" },
};

#define KW_MAP_SIZE ( sizeof KW_MAP_NAME / sizeof (KW_MAP_TYPE) )

/* fiord */

#include "fiord/make_disp2_double_func.h"   /* define make_xxx_func macros */

/* broadcast message handler */

make_disp2_double_get_kvals_func( GET_KVAL_FUNC )
make_disp2_double_input_func  (input_ttmposx,  FIUTTMX)