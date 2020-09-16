from labjack import ljm

def read_pd(nb_values:int=1, v_range:int=10, chn:int=2) -> float:
    """Reads the spcified number of values and returns the average

    Args:
        nb_values: the number of reads to average
            a value of 0 will read until a keyboard interrupt is given
        range: the Voltage range to read values at.
            Valid options are 10, 1, .1
        chn: the channel to read (AIN#)
            Valid options are 0, 1, 2, 3
    Returns:
        int = the average of the reads
    """

    # validate parameters
    try: assert v_range in [.1, 1, 10]
    except AssertionError: 
        raise ValueError("Valid ranges: 10, 1, .1")

    try:
        nb_values = int(nb_values)
        assert nb_values > 0
    except ValueError:
        raise ValueError("nb_values should be castable as an int.")
    except AssertionError:
        raise ValueError("nb_values should be a positive integer.")

    try: assert chn in [0, 1, 2, 3]
    except AssertionError:
        raise ValueError("chn should be 0, 1, 2, or 3.")

    # connection information for the labjack
    devnm = 'Labjack'
    IP    = '10.136.1.46'

    # store connection
    handle = ljm.openS("T7", "Ethernet", IP)

    # surround in a try block to capture keyboard interrupt
    try:
        # make variable to hold the current average
        cnt = 0.0
        avg = 0.0
        # set voltage range
        ljm.eWriteName(handle, "AIN{}_RANGE".format(chn), v_range)

        # get readings until we have nb_values readings
        while cnt < nb_values:
            cnt += 1
            # get a new value
            val = ljm.eReadName(handle, "AIN{}".format(chn))
            # calculate it into avg
            avg = ((avg * (cnt - 1)) + val) / cnt
    # absorb keyboard interrupts
    except KeyboardInterrupt: pass
    # clean up
    finally:
        # set voltage range back to the not-sensitive value
        ljm.eWriteName(handle, "AIN{}_RANGE".format(chn), 10)
        # close connection
        ljm.close(handle)
        # return average
        return avg

