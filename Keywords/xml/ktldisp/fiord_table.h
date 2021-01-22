/* $Header$ */
#define H_FIORD_RCSID "@(#)$Id: ktlxml2fiord.sin 96802 2017-08-23 14:40:23Z wdeich $"

/* Entries in this file have the following structure:
 *
 * {    "long name",
 *      "keyword name",
 *      data_type,
 *      input function,
 *      output function,
 *      servers array,
 *      {units array} OR {enum values},
 *      quantity (if array-type),
 *      {fiord broads array},
 *      bin_to_asc function,
 *      asc_to_bin function,
 *      user (misc.) data
 * },
 */
{	"",
	"TTMPOSX",
	_double,
	input_fiuttmx,
	fiuttmx_servers,
	{"urad","","%.3f"},
	0,
	{ &inst_double_bcast_kval_info,
	  &inst_double_resp2_kval_info,
	  (FIORD_BROAD_INFO *) NULL },
	(int (*)()) btoa_number,
	(int (*)()) NULL,
	(void *) NULL
}