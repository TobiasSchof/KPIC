/*
 * This script is alerted when the CRED2 takes a new image or when certain 
 *    supported parameters are changed and updates state shared memories
 *    accordingly.
 */

#include <string>   // for std::string class
#include <cstring>  // for strncmp
#include <fstream>  // for reading config file
#include <stdlib.h> // for getting environmental variables

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

/*
 * Set up shared memories in the constructor
 */
void FliObserver::ImageReceiver(){
    // prepare strings to store info from config file
    std::string img_cf;
    std::string fps_cf;
    std::string exp_cf;
    std::string ndr_cf;
    std::string crop_cf;
 
    // find path to config file
    std::string path = getenv("CONFIG");
    if (path == NULL) { 
        perror("No CONFIG environment variable found.";
        exit(EXIT_FAILURE);
    }
    path += "Track_Cam.ini";
 
    // make a file object and open config file
    std::ifstream conf;
    conf.open(path.c_str());
 
    // check for errors on opening the file
    if (!conf) { perror("Error loading config file."); exit(EXIT_FAILURE); }
 
    // iterate through the file (breaks are at spaces)
    std::string word;
    while (conf >> word){
        if (strncmp("IMG:", word.c_str(), 4) == 0){ conf >> img_cf; }
        else if(strncmp("FPS_D:", word.c_str(), 6) == 0){ conf >> fps_cf; }
        else if(strncmp("Exp_D:", word.c_str(), 6) == 0){ conf >> exp_cf; }
        else if(strncmp("NDR_D:", word.c_str(), 6) == 0){ conf >> ndr_cf; }
        else if(strncmp("Crop_D:", word.c_str(), 7) == 0){conf >> crop_cf;}
    }
 
    // close config file
    conf.close()
 
    // the paths for shared memory are up to the comma
    size_t idx;
 
    idx = img_fc.find(",");
    if (idx == std::string::npos) { 
        perror("Config file unreadable.");
        exit(EXIT_FAILURE);
    } else { img_cf.erase(idx, std::string::npos); }
 
    idx = fps_fc.find(",");
    if (idx == std::string::npos) { 
        perror("Config file unreadable.");
        exit(EXIT_FAILURE);
    } else { fps_cf.erase(idx, std::string::npos); }
 
    idx = exp_fc.find(",");
    if (idx == std::string::npos) { 
        perror("Config file unreadable.");
        exit(EXIT_FAILURE);
    } else { exp_cf.erase(idx, std::string::npos); }
 
    idx = ndr_fc.find(",");
    if (idx == std::string::npos) { 
        perror("Config file unreadable.");
        exit(EXIT_FAILURE);
    } else { ndr_cf.erase(idx, std::string::npos); }
 
    idx = crop_fc.find(",");
    if (idx == std::string::npos) { 
        perror("Config file unreadable.");
        exit(EXIT_FAILURE);
    } else { crop_cf.erase(idx, std::string::npos); }
 
    // if a shared memory doesn't exist and we try to connect to it,
    //    it will throw an error.
    try { img = new Shm(img_fc); }
    catch (NoShm) {
        uint16_t data[640*512];
        uint16_t size[3] = {640, 512, 0};
        img = new Shm(img_fc, &size, 3, 3, &data); 
    }
 
    try { fps = new Shm(fps_fc); }
    catch (NoShm) {
        uint16_t data[1];
        uint16_t size[3] = {1, 0, 0};
        fps = new Shm(fps_fc, &size, 3, 10, &data); 
    }
    
    try { exp = new Shm(exp_fc); }
    catch (NoShm) {
        uint16_t data[1];
        uint16_t size[3] = {1, 0, 0};
        exp = new Shm(exp_fc, &size, 3, 10, &data); 
    }
    
    try { ndr = new Shm(ndr_fc); }
    catch (NoShm) {
        uint16_t data[1];
        uint16_t size[3] = {1, 0, 0};
        ndr = new Shm(ndr_fc, &size, 3, 1, &data); 
    }
 
    try { crop = new Shm(crop_fc); }
    catch (NoShm) {
        uint16_t data[4];
        uint16_t size[3] = {4, 0, 0};
        crop = new Shm(crop_fc, &size, 3, 3, &data); 
    }
}

/*
 * Set fps trigger to 0 to do fastest updates
 */
double FliObserver::fpsTrigger(){ return 0; }

/*
 * This method is called any time a new image is ready.
 *   cam_res and shm_res ensure that the image size matches our shared
 *   memory size, so copy can only be done if they are resolved.
 *
 * NOTE: The FliSdk casts the pointer to the image as uint8_t* but the image is
 *   really 16-bit
 */
void FliObserver::ImageReceived(uint8_t* image){
    if (cam_res && shm_res){ img->set_data(image); } 
}

/*
 * This method is called when the fps is updated
 */
void FliObserver::onFpsChanged(double _fps){ fps->set_data(&_fps); }

/*
 * This method is called when the exposure time is updated
 */
void FliObserver::onTintChanged(double tint){ exp->set_data(&tint); }

/*
 * This method is called when the NDR is updated
 */
void FliObserver::onNbReadWoResetChanged(int nbRead){ 
    // make sure that the data is 8 bit
    uint8_t _ndr = nbRead;
    ndr->set_data(&_ndr); 
}

/*
 * This method is called when a cropping is started (i.e., entering undefined
 *   size state.)
 */
void FliObserver::onBeginChangeCropping(){
    // set cam_res and shm_res to false so that image copying stops until
    //    size is resolved.
    cam_res = false; 
    shm_res = false; 
}

/*
 * This method is called when a cropping is finished (i.e., camera is at a
 *   known cropping size)
 */
void FliObserver::onEndChangeCropping(){ cam_res = true; }

/*
 * This method is called when cropping has changed. 
 * 
 * It will update the shared memory, and then set shm_res to true to indicate
 *    that the shared memory size is resolved.
 */
void FliObserver::onCroppingChanged(bool enabled, uint16_t col1, 
                                      uint16_t col2, uint16_t row1,
                                      uint16_t row2){
    if (enabled){
        // resize the image in shm
        uint16_t size[3] = {col2 - col1, row2 - row1, 0};
        img->resize(&size);

        // set crop_d shm
        uint16_t data[4] = {col1, col2, row1, row2};
        crop->set_data(&data);

    } else {
        // resize the image in shm to max
        uint16_t size[3] = {640, 512, 0};
        img->resize(&size);

        // set crop_d shm to "no crop"
        uint16_t data[4] = {-1, -1, -1, -1};
        crop->set_data(&data);
    }

    // indicate that image is correctly resized
    shm_res = true; 
}

/*
 * Delete references to shared memories in the destructor
 */
void FliObserver::~FliObserver(){
    delete img;
    delete fps;
    delete exp;
    delete ndr;
    delete crop;
}
