/*
 * This script is alerted when the CRED2 takes a new image or when certain 
 *    supported parameters are changed and updates state shared memories
 *    accordingly.
 */


#include "FliSdk.h"
#include "shmlib.hpp"

class ImageReceiver : public IFliCameraObserver, 
                      public IRawImageReceivedObserver(){

  public:
    // constructor
    ImageReceiver();

    // inherited from IRawImageReceivedObserver

    // The method that is called when a new image is ready
    //   even though the pointer is cast as uint8_t, the image is 16-bit
    virtual void ImageReceived(uint8_t* image) override;
    // Defines the speed that the above method is triggered at. A return 
    //   of 0 means maximum speed
    virtual double fpsTrigger() override;

    // inherited from IFliCameraObserver
    
    // The method that's called on successful fps change
    virtual void onFpsChanged(double fps) override;
    // The method that's called on successful exposure time change
    virtual void onTintChanged(double tint) override;
    // The mthod that's called on successful NDR change
    virtual void onNbReadWoResetChanged(int nbRead) override;
    // The method that's called on successful crop change
    virtual void onCroppingChanged(bool enabled, uint16_t col1, uint16_t col2,
                                   uint16_t row1, uint16_t row2) override;

    // destructor
    ~ImageReceiver();

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
} 

void ImageReceiver::ImageReceiver(){

}
