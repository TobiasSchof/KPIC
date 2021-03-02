/* $Header$ */
RCSID_DEF(H_PROTO_RCSID,"@(#)$Id: ktlxml2fiord.sin 96802 2017-08-23 14:40:23Z wdeich $");

extern FIORD_BROAD_INFO inst_int_resp2_kval_info;
extern FIORD_BROAD_INFO inst_int_bcast_kval_info;

extern FIORD_BROAD_INFO inst_int64_resp2_kval_info;
extern FIORD_BROAD_INFO inst_int64_bcast_kval_info;

extern FIORD_BROAD_INFO inst_string_resp2_kval_info;
extern FIORD_BROAD_INFO inst_string_bcast_kval_info;

extern FIORD_BROAD_INFO inst_float_resp2_kval_info;
extern FIORD_BROAD_INFO inst_float_bcast_kval_info;

extern FIORD_BROAD_INFO inst_double_resp2_kval_info;
extern FIORD_BROAD_INFO inst_double_bcast_kval_info;

extern FIORD_BROAD_INFO inst_int_array_resp2_kval_info;
extern FIORD_BROAD_INFO inst_int_array_bcast_kval_info;

extern FIORD_BROAD_INFO inst_int64_array_resp2_kval_info;
extern FIORD_BROAD_INFO inst_int64_array_bcast_kval_info;

extern FIORD_BROAD_INFO inst_float_array_resp2_kval_info;
extern FIORD_BROAD_INFO inst_float_array_bcast_kval_info;

extern FIORD_BROAD_INFO inst_double_array_resp2_kval_info;
extern FIORD_BROAD_INFO inst_double_array_bcast_kval_info;
extern int input_disperr  ();
/* DISPERR is a read-only keyword (no output function) */
extern int input_dispmem  ();
/* DISPMEM is a read-only keyword (no output function) */
extern int input_dispmsg  ();
/* DISPMSG is a read-only keyword (no output function) */
extern int input_dispsta  ();
/* DISPSTA is a read-only keyword (no output function) */
extern int input_dispstop  ();
extern int output_dispstop ();
extern int input_test  ();
extern int output_test ();
extern int input_ttmposx  ();
extern int output_ttmposx ();
extern int input_ttmposy  ();
extern int output_ttmposy ();
extern int input_ttmerr  ();
extern int output_ttmerr ();
extern int input_mcpos  ();
extern int output_mcpos ();
extern int input_mcerr  ();
extern int output_mcerr ();
extern int input_bdriftx  ();
extern int output_bdriftx ();
extern int input_bdrifty  ();
extern int output_bdrifty ();
extern int input_tcmaspx  ();
extern int output_tcmaspx ();
extern int input_tcinsta  ();
extern int output_tcinsta ();
extern int input_uptime  ();
/* UPTIME is a read-only keyword (no output function) */
extern int input_version  ();
/* VERSION is a read-only keyword (no output function) */
