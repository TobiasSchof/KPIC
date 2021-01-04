/*
 * A header file to define the KPIC_FliObserver class.
 *   This class handles whenever the D shms need to be updated for the tracking camera
 */

#ifndef KPIC_CAM_OBSERVER_INCLUDE
#define KPIC_CAM_OBSERVER_INCLUDE

#include <semaphore.h>

#include "FliSdk.h"
#include "IFliCameraObserver.h"
#include "KPIC_shmlib.hpp"


class KPIC_FliObserver : public IFliCameraObserver, public IRawImageReceivedObserver{

  public:
    // constructor
    KPIC_FliObserver();

    // inherited from IRawImageReceivedObserver

    // The method that is called when a new image is ready
    //   even though the pointer is cast as uint8_t, the image is 16-bit
    void imageReceived(const uint8_t* image);
    // Defines the speed that the above method is triggered at. A return 
    //   of 0 means maximum speed
    uint16_t fpsTrigger();

    // inherited from IFliCameraObserver
    
    // The method that's called on successful fps change
    void onFpsChanged(double _fps);
    // The method that's called on successful exposure time change
    void onTintChanged(double tint);
    // The mthod that's called on successful NDR change
    void onNbReadWoResetChanged(int nbRead);
    // The method that's called on successful crop change
    void onCroppingChanged(bool enabled, uint16_t col1, uint16_t col2,
                                   uint16_t row1, uint16_t row2);
    // The method that's called when cropping window begins change
    void onBeginChangeCropping();
    // The method that's called when cropping window finishes change
    void onEndChangeCropping();

    // destructor
    ~KPIC_FliObserver();

  private: 
    // Shared memories

    // To store the image
    Shm *img;
    // To store D_FPS
    Shm *fps;
    // to store D_Exp
    Shm *exp;
    // to store D_NDR
    Shm *ndr;
    // to store D_Crop
    Shm *crop;

    /*
     * a semaphore that locks during a crop change to prevent image acquisition
     *    while camera and shm are in an unresolved crop state.
     */
    sem_t shm_res;

    /* to track whether the camera is just connecting. This will be changed
     *     the first time that shm_res is posted
     */
    bool started;
}; 

#endif