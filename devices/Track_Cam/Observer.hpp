/*
 * A header file to define the FliObserver class.
 *   This class handles whenever the D shms need to be updated for the tracking camera
 */

#include "FliSdk.h"
#include "KPIC_shmlib.hpp"

class FliObserver : public IFliCameraObserver, 
                    public IRawImageReceivedObserver(){

  public:
    // constructor
    FliObserver();

    // inherited from IRawImageReceivedObserver

    // The method that is called when a new image is ready
    //   even though the pointer is cast as uint8_t, the image is 16-bit
    virtual void ImageReceived(uint8_t* image) override;
    // Defines the speed that the above method is triggered at. A return 
    //   of 0 means maximum speed
    virtual double fpsTrigger() override;

    // inherited from IFliCameraObserver
    
    // The method that's called on successful fps change
    virtual void onFpsChanged(double _fps) override;
    // The method that's called on successful exposure time change
    virtual void onTintChanged(double tint) override;
    // The mthod that's called on successful NDR change
    virtual void onNbReadWoResetChanged(int nbRead) override;
    // The method that's called on successful crop change
    virtual void onCroppingChanged(bool enabled, uint16_t col1, uint16_t col2,
                                   uint16_t row1, uint16_t row2) override;
    // The method that's called when cropping window begins change
    virtual void onBeginChangeCropping() override;
    // The method that's called when cropping window finishes change
    virtual void onEndChangeCropping() override;

    // destructor
    ~FliObserver();

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
     * boolean flags to make sure that the shared memory and camera agree
     *   on a subwindow before an image is copied to avoid seg faults
     *
     * NOTE: on script startup, shared memory and camera crop windows are 
     *   assumed to be in an undefined state. Crop window will have to be
     *   changed before images can start being recorded.
     */ 
    bool cam_res = false;
    bool shm_res - false;
} 