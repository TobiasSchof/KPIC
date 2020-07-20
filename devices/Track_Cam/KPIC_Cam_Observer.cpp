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
#include "KPIC_Cam_Observer.hpp"

/*
 * Constructor for Observer class
 */
FliObserver::FliObserver(){
    // prepare strings to store info from config file
    std::string img_cf;
    std::string fps_cf;
    std::string exp_cf;
    std::string ndr_cf;
    std::string crop_cf;
 
    // find path to config file
    std::string path = getenv("RELDIR");
    if (path.compare(path.length() - 1, 1, "/")) { path.erase(path.length() - 1, 1); }
    path += "/data";
    if (path == "") { 
        perror("No CONFIG environment variable found.");
        exit(EXIT_FAILURE);
    }
    path += "/Track_Cam.ini";
 
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
    conf.close();
 
    // the paths for shared memory are up to the comma
    size_t idx;
 
    idx = img_cf.find(",");
    if (idx == std::string::npos) { 
        perror("Config file unreadable.");
        exit(EXIT_FAILURE);
    } else { img_cf.erase(idx, std::string::npos); }
 
    idx = fps_cf.find(",");
    if (idx == std::string::npos) { 
        perror("Config file unreadable.");
        exit(EXIT_FAILURE);
    } else { fps_cf.erase(idx, std::string::npos); }
 
    idx = exp_cf.find(",");
    if (idx == std::string::npos) { 
        perror("Config file unreadable.");
        exit(EXIT_FAILURE);
    } else { exp_cf.erase(idx, std::string::npos); }
 
    idx = ndr_cf.find(",");
    if (idx == std::string::npos) { 
        perror("Config file unreadable.");
        exit(EXIT_FAILURE);
    } else { ndr_cf.erase(idx, std::string::npos); }
 
    idx = crop_cf.find(",");
    if (idx == std::string::npos) { 
        perror("Config file unreadable.");
        exit(EXIT_FAILURE);
    } else { crop_cf.erase(idx, std::string::npos); }
 
    // if a shared memory doesn't exist and we try to connect to it,
    //    it will throw an error.
    try { img = new Shm(img_cf); }
    catch (MissingSharedMemory& ex) {
        uint16_t data[640*512];
        uint16_t size[3] = {640, 512, 0};
        img = new Shm(img_cf, size, 3, 3, &data, true); 
    }
 
    try { fps = new Shm(fps_cf); }
    catch (MissingSharedMemory& ex) {
        uint16_t data[1];
        uint16_t size[3] = {1, 0, 0};
        fps = new Shm(fps_cf, size, 3, 10, &data, false); 
    }
    
    try { exp = new Shm(exp_cf); }
    catch (MissingSharedMemory& ex) {
        uint16_t data[1];
        uint16_t size[3] = {1, 0, 0};
        exp = new Shm(exp_cf, size, 3, 10, &data, false); 
    }
    
    try { ndr = new Shm(ndr_cf); }
    catch (MissingSharedMemory& ex) {
        uint16_t data[1];
        uint16_t size[3] = {1, 0, 0};
        ndr = new Shm(ndr_cf, size, 3, 1, &data, false); 
    }
 
    try { crop = new Shm(crop_cf); }
    catch (MissingSharedMemory& ex) {
        uint16_t data[4];
        uint16_t size[3] = {4, 0, 0};
        crop = new Shm(crop_cf, size, 3, 3, &data, false); 
    }
}

/*
 * Set fps trigger to 0 to do fastest updates
 */
uint16_t FliObserver::fpsTrigger(){ return 0; }

/*
 * This method is called any time a new image is ready.
 *   cam_res and shm_res ensure that the image size matches our shared
 *   memory size, so copy can only be done if they are resolved.
 *
 * NOTE: The FliSdk casts the pointer to the image as uint8_t* but the image is
 *   really 16-bit
 */
void FliObserver::imageReceived(const uint8_t* image){
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
        img->resize(col2 - col1, row2 - row1, 0);

        // set crop_d shm
        uint16_t data[4] = {col1, col2, row1, row2};
        crop->set_data(&data);

    } else {
        // resize the image in shm to max
        img->resize(640, 512, 0);

        // set crop_d shm to "no crop"
        uint16_t data[4] = {0, 0, 0, 0};
        crop->set_data(&data);
    }

    // indicate that image is correctly resized
    shm_res = true; 
}

/*
 * Delete references to shared memories in the destructor
 */
FliObserver::~FliObserver(){
    delete img;
    delete fps;
    delete exp;
    delete ndr;
    delete crop;
}
