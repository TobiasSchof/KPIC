/*
 * This is a C++ script to listen for updates to command shared memory for the
 *    tracking camera and send commands to the camera accordingly.
 */

#include <semaphore.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sstream>
#include <cstring>
#include <fstream>

#include "FliSdk.h"
#include "MetaStruct.h"

#define SHM_DIR "/tmp/TrackCam/"

#define IMAGE_OFFSET sizeof(im_metadata)
#define LATIME_OFFSET 96`
