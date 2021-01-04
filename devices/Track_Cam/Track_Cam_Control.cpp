/*
 * A script meant to be run in a tmux session that listens for new input from
 *   the user with regards to the FIU CRED2 and performs actions accordingly. 
 */

#include <string>
#include <fstream>
#include <stdlib.h>
#include <stdio.h>
#include <cstring>
#include <vector>
#include <unistd.h>
#include <csignal>
#include <thread>
#include <iostream>

#include "KPIC_Cam_Observer.hpp"

// Shared memories and the sdk which threads will need
FliSdk *fli;
Shm *Stat_D;
Shm *Error;
Shm *Temp_D;
Shm *Stat_P;
Shm *Crop;
Shm *NDR_P;
Shm *FPS_P;
Shm *Temp_P;
Shm *Exp_P;
Shm *NPSD;
Shm *NPSP;

// temperature to set the camera to on startp
double STARTTEMP = 0;
double STARTFPS  = 20;
double STARTTINT = .01;
int STARTNDR  = 0;

// mutex to control fli sdk
std::mutex mtx;

// fliobserver class
KPIC_FliObserver *obs;

// variables to store whether this script should die and whether
//   the camera is connected
bool alive = true;
bool camConnected = false;

// semaphore to wake up main thread when a signal is received
sem_t wait;

// variable to store which NPS port the Tracking Camera is on
uint8_t TC_PORT; 

// path to config files
std::string CONFIG;

/*
 * Cleanup function to handle signals
 */
void TCC_close(int signum){
    alive = false;
    sem_post(&wait);
}

/*
 * A function to check the NPS shm for on status of camera
 */
bool q_cam_pow(){
    
    // get data in NPS shm
    uint8_t stat;
    NPSD->get_data(&stat);

    // bit in NPS shm corresponds to port - 1 so use bit-wise and to see if it's on
    return ((stat & (1 << (TC_PORT - 1))) != 0);
}

/*
 * handles connecting the camera to the sdk
 */
void cam_connect(){

    if (camConnected) { return; }

    // get fli lock
    mtx.lock();

    // search for grabbers for a maximum of 10 seconds
    std::vector<std::string> listOfGrabbers = fli->detectGrabbers();
    uint8_t cnt = 0;
    while(!listOfGrabbers.size()){
        if (cnt >= 10){
            std::cout << "No grabber could be found.\n";
            uint8_t err = 5;
            Error->set_data(&err);
            return;
        }
        sleep(1);
        listOfGrabbers = fli->detectGrabbers();
        cnt += 1;
    }

    // search for cameras for a maximum of 30 seconds
    std::vector<std::string> listOfCameras = fli->detectCameras();
    cnt = 0;
    while(!listOfCameras.size()){
        if (cnt >= 60){
            std::cout << "No camera could be found.\n";
            uint8_t err = 4;
            Error->set_data(&err);
            return;
        }
        sleep(1);
        listOfCameras = fli->detectCameras();
        cnt += 1;
    }

    //take the first camera in the list
    fli->setCamera(listOfCameras[0]);
    fli->setGrabber(listOfGrabbers[0]);
    //set full mode
    fli->setMode(FliSdk::Mode::Full);
    //update
    fli->update();

    // release fli lock
    mtx.unlock();

    // the cred2 will return operational once camera is cooled.
    {
        std::string stat;

        // get camera status
        mtx.lock();
        fli->camera()->getStatus(stat);
        mtx.unlock();

        while(stat != "operational"){ 
            // get fli status with lock
            mtx.lock();
            fli->camera()->getStatus(stat);
            mtx.unlock();
            sleep(.5);
        }
    }

    mtx.lock();

    // add observer to sdk
    fli->camera()->addObserver(obs);
    // add image receiver
    fli->addRawImageReceivedObserver(obs);

    // set cropping to current cropping to make sure that shm and camera match
    {
        bool enabled;
        uint16_t col1;
        uint16_t col2;
        uint16_t row1;
        uint16_t row2;
        fli->credTwo()->getCropping(enabled, col1, col2, row1, row2);
        fli->credTwo()->setCropping(enabled, col1, col2, row1, row2);
    }
    // set fps, tint, and ndrs to populate shms
    {
        fli->camera()->setFps(STARTFPS);
        fli->credTwo()->setTint(STARTTINT);
        fli->credTwo()->setNbReadWoReset(STARTNDR);
    }

    mtx.unlock();

    camConnected = true;

    // put starting temp in Temp_D
    double p_data[2] = {STARTTEMP, 5};
    // set temp to 0
    mtx.lock();
    fli->credTwo()->setSensorTemp(STARTTEMP);
    mtx.unlock();
    // set temp_p
    Temp_P->set_data(&p_data); 

    // set stat_d
    {
        bool fan;
        bool led;
        std::string fan_m;
        mtx.lock();
        fli->credTwo()->getFanMode(fan_m);
        fan = (fan_m == "automatic");
        fli->camera()->getLedState(led);
        mtx.unlock();

        uint8_t stat;
        stat = (led << 3) + (fan << 2) + (1 << 1) + 1;
        Stat_D->set_data(&stat);
    }

    // start grabber
    fli->start();

}

/*
 * A function to turn on the camera and connect it through the FliSdk
 */
void cam_on(){

    if (camConnected){ return; }

    // prepare camera bit
    uint8_t cam = (1 << (TC_PORT - 1));

    // get current NPS D Shm
    uint8_t stat;
    NPSD->get_data(&stat);

    if (!(stat & cam)){
        // set new status using bit-wise or
        stat = stat | cam;
        NPSP->set_data(&stat);
    }

    cam_connect();
}

/*
 * A function to disconnect from the camera and shut it down
 */
void cam_off(){

    if (!camConnected){ return; }

    mtx.lock();
    // stop acquisition
    fli->stop();
    // turn off the camera
    fli->camera()->shutDown();
    mtx.unlock();

    // give time for camera to shutdown
    sleep(2);

    // request nps to turn off power
    // prepare camera bit
    uint8_t cam = (1 << (TC_PORT - 1));

    // get current NPS D Shm
    uint8_t stat;
    NPSD->get_data(&stat);

    // set new status using subtraction and bit-wise
    //  (we use bit-wise and to ensure we only subtract if the camera bit is 1)
    stat = stat - (cam & stat);
    NPSP->set_data(&stat);

    // update Stat_D
    stat = 1;
    Stat_D->set_data(&stat);

    camConnected = false;
}

/*
 * Function that connects to shared memories. 
 *
 * Returns:
 *   int = 1 if pointers already initialized, 0 otherwise.
 */
int Shm_connect(){
    if (Stat_D != NULL){ return 1; }

    std::string path = CONFIG + "/Track_Cam.ini";

    // make a file object and open config file
    std::ifstream conf;

    // strings to hold shm paths for each shm
    std::string dstat_cf;
    std::string err_cf;
    std::string dtemp_cf;
    std::string pstat_cf;
    std::string crop_cf;
    std::string pndr_cf;
    std::string pfps_cf;
    std::string ptemp_cf;
    std::string pexp_cf;

    // open the config file and check for error
    conf.open(path.c_str());
    if (!conf) { perror("Error loading config file."); exit(EXIT_FAILURE); }
    
    // iterate through the file (breaks are at spaces
    std::string word;
    while (conf >> word){
        if (strncmp("Stat_D:", word.c_str(), 7) == 0){ conf >> dstat_cf; }
        else if (strncmp("Error:", word.c_str(), 6) == 0){ conf >> err_cf; }
        else if (strncmp("Temp_D:", word.c_str(), 7) == 0){ conf >> dtemp_cf; }
        else if (strncmp("Stat_P:", word.c_str(), 7) == 0){ conf >> pstat_cf; }
        else if (strncmp("Crop_P:", word.c_str(), 7) == 0){ conf >> crop_cf; }
        else if (strncmp("NDR_P:", word.c_str(), 6) == 0){ conf >> pndr_cf; }
        else if (strncmp("FPS_P:", word.c_str(), 6) == 0){ conf >> pfps_cf; }
        else if (strncmp("Temp_P:", word.c_str(), 7) == 0){ conf >> ptemp_cf; }
        else if (strncmp("Exp_P:", word.c_str(), 6) == 0){ conf >> pexp_cf; } 
    }

    // close config file
    conf.close();

    // paths to shms are up to comma, so find index of ,
    size_t idx;
    dstat_cf.erase(dstat_cf.find(","), std::string::npos);
    err_cf.erase(err_cf.find(","), std::string::npos);
    dtemp_cf.erase(dtemp_cf.find(","), std::string::npos);
    pstat_cf.erase(pstat_cf.find(","), std::string::npos);
    crop_cf.erase(crop_cf.find(","), std::string::npos);
    pndr_cf.erase(pndr_cf.find(","), std::string::npos);
    pfps_cf.erase(pfps_cf.find(","), std::string::npos);
    ptemp_cf.erase(ptemp_cf.find(","), std::string::npos);
    pexp_cf.erase(pexp_cf.find(","), std::string::npos);

    // query whether camera is on, this will tell us whether to pull values for
    //   shm or just populate with whatever
    bool cam = q_cam_pow();
    
    // if a shared memory doesn't exist and we try to connect to it,
    //   it will throw an error. So make one in that case.
    try { 
        Stat_D = new Shm(dstat_cf);
        uint8_t data;
        Stat_D->get_data(&data);
        // if there's already a control script running, fail
        if (data & 1){
            perror("Control script already alive.");
            delete fli;
            delete obs;
            delete NPSD;
            delete NPSP;
            delete Stat_D;
            exit(EXIT_FAILURE);
        }
    }
    catch (MissingSharedMemory& ex) {
        uint8_t data[1];
        uint16_t size[3] = {1, 0, 0};
        bool script = 1;
        bool fan;
        bool led;
        if (cam) {
            std::string fan_m;
            fli->credTwo()->getFanMode(fan_m);
            fan = (fan_m == "Automatic");
            fli->camera()->getLedState(led);
        } else { fan = false; led = false; }

        data[0] = (uint8_t)script + ((uint8_t)cam << 1) + ((uint8_t)fan << 2) +
               ((uint8_t)led << 3);
        Stat_D = new Shm(dstat_cf, size, 3, 1, &data, false, false, false);
    } 

    try { Error = new Shm(err_cf); }
    catch (MissingSharedMemory& ex) {
        uint8_t data[1] = {0};
        uint16_t size[3] = {1, 0, 0};
        Error = new Shm(err_cf, size, 3, 1, &data, false, false, false); 
    }

    try { Temp_D = new Shm(dtemp_cf); }
    catch (MissingSharedMemory& ex) {
        double data[6];
        uint16_t size[3] = {6, 0, 0};
        if (cam) { fli->credTwo()->getAllTemp(data[0], data[1], data[2], data[3], 
                                   data[4], data[5]); }
        Temp_D = new Shm(dtemp_cf, size, 3, 10, &data, false, false, false);
    }

    try { Stat_P = new Shm(pstat_cf, true); }
    catch (MissingSharedMemory& ex) {
        uint8_t data[1] = {1};
        uint16_t size[3] = {1, 0, 0};
        Stat_P = new Shm(pstat_cf, size, 3, 1, &data, false, true, false);
    }

    try { Crop = new Shm(crop_cf, true); }
    catch (MissingSharedMemory& ex) {
        uint16_t data[4] = {0, 0, 0, 0};
        uint16_t size[3] = {4, 0, 0};
        Crop = new Shm(crop_cf, size, 3, 3, &data, false, true, false);
    }

    try { NDR_P = new Shm(pndr_cf, true); }
    catch (MissingSharedMemory& ex) {
        uint8_t data[1] = {0};
        uint16_t size[3] = {1, 0, 0};
        NDR_P = new Shm(pndr_cf, size, 3, 1, &data, false, true, false);
    }

    try { FPS_P = new Shm(pfps_cf, true); }
    catch (MissingSharedMemory& ex) {
        double data[1] = {20};
        uint16_t size[3] = {1, 0, 0};
        FPS_P = new Shm(pfps_cf, size, 3, 10, &data, false, true, false);
    }

    try { Temp_P = new Shm(ptemp_cf, true); }
    catch (MissingSharedMemory& ex) {
        double data[2] = {0, 5};
        uint16_t size[3] = {2, 0, 0};
        Temp_P = new Shm(ptemp_cf, size, 3, 10, &data, false, true, false);
    }

    try { Exp_P = new Shm(pexp_cf, true); }
    catch (MissingSharedMemory& ex) {
        double data[1] = {.001};
        uint16_t size[3] = {1, 0, 0};
        Exp_P = new Shm(pexp_cf, size, 3, 10, &data, false, true, false);
    }

    if (cam){ cam_connect(); }
    else{ uint8_t stat=1; Stat_D->set_data(&stat); }

    return 0;
}

/*
 * Function that connects to the NPS shms.
 * 
 * Returns:
 *    int = 1 if pointers already initialized, 0 otherwise.
 */
int NPS_connect(){

    // do nothing if shm already initialized
    if (NPSD != NULL){ return 1; }

    std::string path = CONFIG + "/NPS.ini";

    // make a file object and open config file
    std::ifstream conf;
    
    // iterate through the file (breaks are at spaces
    std::string word;
    std::string fnamed;
    std::string fnamep;
    std::string prev;
    uint8_t port = 0;

    // open the nps config file and check for error
    conf.open(path.c_str(), std::ifstream::in);
    if (!conf) { perror("Error loading config file."); exit(EXIT_FAILURE); }

    while (conf >> word){
        if (strncmp("D_Shm:", word.c_str(), 6) == 0){ conf >> fnamed; }
        else if (strncmp("P_Shm:", word.c_str(), 6) == 0){ conf >> fnamep; }
        else if (word.find("CRED2") != std::string::npos){ 
            port = atoi(prev.c_str()); }
        prev = word;
    }
    // close config file
    conf.close();

    // if port wasn't found, throw an error
    if (port == 0){
        perror("No 'Tracking Camera' port found in NPS.ini");
        exit(EXIT_FAILURE);
    } else { TC_PORT = port; }

    // get file name
    fnamed.erase(fnamed.find(","), std::string::npos);
    fnamep.erase(fnamep.find(","), std::string::npos);
    
    // connect to shms
    try { NPSD = new Shm(fnamed); }
    catch(MissingSharedMemory& ex) {
        perror("NPS control script must be alive");
        exit(EXIT_FAILURE);
    }
    try { NPSP = new Shm(fnamep); }
    catch(MissingSharedMemory& ex) {
        perror("NPS control script must be alive");
        exit(EXIT_FAILURE);
    }

    return 0;
}

/*
 * Function to handle Shm_P. To be used in a thread
 */
void handle_stat(){

    // create variables to store new stat, old stat, and error
    uint8_t stat;
    uint8_t old;
    uint8_t err;

    // wait for shm to be updated so we can end loop with wait
    Stat_P->get_data(&stat, true);
    old = 1;

    while (alive){

        // if nothing has changed, do nothing
        if (old == stat){
            Stat_P->get_data(&stat, true);
            continue;
        }

        // if script bit is turned to 0, end
        if (!(stat & 1)){ TCC_close(0); continue; }

        // if camera bit is 1 and camera is not on, turn on
        if ((stat & (1 << 1)) && !camConnected){ cam_on(); }
        // if camera bit is 0 and camera is on, turn off
        else if (!(stat & (1 << 1)) && camConnected){ cam_off(); continue; }

        bool fan_a = false;
        bool led_a = false;

        // if camera is on, check led and fan status
        if (camConnected){
            // extract fan bit and led bit from stat
            bool fan_req = stat & (1 << 2);
            bool led_req = stat & (1 << 3);
            // get current status of fan and led
            std::string fan_m;
            mtx.lock();
            fli->credTwo()->getFanMode(fan_m);
            fan_a = (fan_m == "automatic");
            fli->camera()->getLedState(led_a);
            mtx.unlock();

            // act if there's a difference between state and request
            if (fan_req != fan_a){
                // if fan bit is on, set fan to automatic
                if (fan_req){
                    mtx.lock();
                    fli->credTwo()->setFanModeAutomatic();
                    mtx.unlock();
                // if fan bit is off, set fan to speed 0
                } else {
                    mtx.lock();
                    fli->credTwo()->setFanModeManual();
                    fli->credTwo()->setFanSpeed(0);
                    mtx.unlock();
                }
            }
            if (led_req != led_a){
                mtx.lock();
                fli->camera()->enableLed(led_req);
                mtx.unlock();
            }
        // otherwise, set error
        } else {
            err = 1;
            Error->set_data(&err);
        }

        uint8_t data[1];
        data[0] = 1 + ((uint8_t)camConnected << 1) + ((uint8_t)fan_a << 2) +
            ((uint8_t)led_a << 3);         
        Stat_D->set_data(&data);

        // wait for an update to shm
        old = stat;
        Stat_P->get_data(&stat, true);
    }

}

/*
 * Function to handle Crop. To be used in a thread
 */
void handle_crop(){

    // create variables to store crop and error
    uint16_t crop[4];
    uint8_t err;

    // wait for shm to be updated so we can end loop with wait
    Crop->get_data(&crop, true);

    while (alive){

        // if camera is not on, set error and continue
        if (!camConnected){
            err = 1;
            Error->set_data(&err);
            Crop->get_data(&crop, true);
            continue;
        }

        // check if subwindowing should be turned off
        if (crop[0] == 0 && crop[1] == 0 && crop[2] == 0 && crop[3] == 0){
            mtx.lock();
            fli->credTwo()->setCropping(false, 0, 639, 0, 511);
            mtx.unlock();

            // clear any error that might be stored
            err = 0;
            Error->set_data(&err);
        } else {
            // check if subwindowing is valid
            mtx.lock();
            if (fli->credTwo()->isCroppingValid(crop[0], crop[1], 
                    crop[2], crop[3]) == FliSdkError::noError){
                // set cropping window
                fli->credTwo()->setCropping(true, crop[0], crop[1],
                    crop[2], crop[3]);

                // clear any error that might be stored
                err = 0;
                Error->set_data(&err);
            // otherwise, set an error
            } else {
                err = 2;
                Error->set_data(&err);
            }
            mtx.unlock();
        }

        // wait for an update to shm
        Crop->get_data(&crop, true);
    }

}

/*
 * Function to handle NDR_P. To be used in a thread
 */
void handle_ndr(){

    // create variables to store ndr and err
    uint8_t ndr;
    uint8_t err;

    // wait for shm to be updated so we can end loop with wait
    NDR_P->get_data(&ndr, true);

    while (alive){
        // if camera is not on, set error and continue
        if (!camConnected){
            err = 1;
            Error->set_data(&err);
            NDR_P->get_data(&ndr, true);
            continue;
        }

        mtx.lock();
        fli->credTwo()->setNbReadWoReset(ndr);
        mtx.unlock();

        // if there was an error, clear it
        err = 0;
        Error->set_data(&err);

        // wait for an update to shm
        NDR_P->get_data(&ndr, true);
    }

}

/*
 * Function to handle FPS_P. To be used in a thread
 */
void handle_fps(){

    // create variables to store fps and error
    double fps;
    uint8_t err;

    // wait for shm to be updated so we can end loop with wait
    FPS_P->get_data(&fps, true);

    while (alive){
        // if camera is not on, set error and continue
        if (!camConnected){
            err = 1;
            Error->set_data(&err);
            FPS_P->get_data(&fps, true);
            continue;
        }

        // if fps is valid (positive), set it
        if (fps > 0){
            mtx.lock();
            fli->camera()->setFps(fps);
            mtx.unlock();

            // if there was an error, clear it
            err = 0;
            Error->set_data(&err);
        // otherwise, set error
        } else {
            err = 2;
            Error->set_data(&err);
        }

        // wait for an update to shm
        FPS_P->get_data(&fps, true);
    }
}

/*
 * Function to handle Temp_P and update Temp_D. To be used in a thread
 */
void handle_temp(){

    // create a variable to store error
    uint8_t err;
    // create a variable to hold new data
    double p_data[2];
    double d_data[6];
    Temp_P->get_data(&p_data);
    // variable to hold the update refresh rate
    timespec wait_time;
    // create variable to hold current temp setpoint
    double old = p_data[0];

    while (alive){
        // set old setpoint
        old = p_data[0];

        // get newest P data
        Temp_P->get_data(&p_data);

        // check if temp needs to be set
        if (p_data[0] != old){
            // if camera is not on, set error and continue
            if (!camConnected){
                err = 1;
                Error->set_data(&err);
                continue;
            }

            mtx.lock();
            fli->credTwo()->setSensorTemp(p_data[0]);
            mtx.unlock();
            
            // if there's an error, clear it
            err = 0;
            Error->set_data(&err);
        }

        // if camera is not on, skip updating temp_d
        if (camConnected){
            // get new temps
            mtx.lock();
            fli->credTwo()->getAllTemp(d_data[0], d_data[1], d_data[2], 
                                       d_data[3], d_data[4], d_data[5]);
            mtx.unlock();

            // update temp_d
            Temp_D->set_data(&d_data);
        }

        // do a timed wait on temp_p semaphore.
        clock_gettime(CLOCK_REALTIME, &wait_time);
        wait_time.tv_sec += (long) p_data[1];
        wait_time.tv_nsec += (long) (p_data[1] - (long) p_data[1])*(1000000000);
        sem_timedwait(Temp_P->sem, &wait_time);
    }
}

/*
 * Function to handle Exp_P. To be used in a thread
 * 
 * If an exposure time greater than 1/fps is set, an error is set instead
 */
void handle_exp(){

    // create variables to store exposure time and current fps
    double exp;
    double fps;
    uint8_t err;

    // wait for shm to be updated so we can end loop with wait
    Exp_P->get_data(&exp, true);

    while (alive){
        // get fps from camera
        mtx.lock();
        fli->camera()->getFps(fps);
        mtx.unlock();

        // if exposure time is valid, set exposure
        if (exp <= (1/fps)){
            mtx.lock();
            fli->credTwo()->setTint(exp);
            mtx.unlock();

            // if there was an error, clear it
            err = 0;
            Error->set_data(&err);
        // otherwise, set error
        } else {
            err = 2;
            Error->set_data(&err);
        }

        // wait for an update to shm
        Exp_P->get_data(&exp, true);
    }
}

int main(){

    // get the location of config files
    CONFIG = getenv("RELDIR");
    // format CONFIG to a known state
    if (CONFIG == "") {
        perror("No $RELDIR environment variable found.");
        exit(EXIT_FAILURE);
    } else if (CONFIG.compare(CONFIG.length() - 1, 1, "/") == 0){
        CONFIG.erase(CONFIG.length() - 1, 1);
    }

    CONFIG += "/data";

    fli = new FliSdk();
    fli->enableRingBuffer(false);

    // connect to NPS shm to see power
    NPS_connect();

    // create a new KPIC_FliObserver
    obs = new KPIC_FliObserver();

    // Connect to Shared memories, and connect to camera if it's on
    Shm_connect();

    // start threads with each of the P shms
    std::thread th_stat(handle_stat);
    std::thread th_crop(handle_crop);
    std::thread th_ndr(handle_ndr);
    std::thread th_fps(handle_fps);
    std::thread th_temp(handle_temp);
    std::thread th_exp(handle_exp);

    // initialize semaphore to wake up main when signal is received
    sem_init(&wait, 0, 0);

    // setup cleanup methods
    signal(SIGTERM, TCC_close);                                                     
    signal(SIGINT, TCC_close);                                                      
    signal(SIGABRT, TCC_close); 
    signal(SIGHUP, TCC_close);

    // wait for cleanup method to post semaphore
    sem_wait(&wait);

    // post semaphores for all shms so that threads wake up
    sem_post(Stat_P->sem);
    sem_post(Crop->sem);
    sem_post(NDR_P->sem);
    sem_post(FPS_P->sem);
    sem_post(Temp_P->sem);
    sem_post(Exp_P->sem);

    // join all the threads to make sure they've finished
    if (th_stat.joinable()) { th_stat.join(); }
    if (th_crop.joinable()) { th_crop.join(); }
    if (th_ndr.joinable()) { th_ndr.join(); }
    if (th_fps.joinable()) { th_fps.join(); }
    if (th_temp.joinable()) { th_temp.join(); }
    if (th_exp.joinable()) { th_exp.join(); }

    // turn off camera
    cam_off();

    // set Stat_D shm
    uint8_t stat = 0;
    Stat_D->set_data(&stat);

    // cleanup semaphore
    sem_destroy(&wait);

    // get P shm file names to delete them later
    std::string pstat_fname;
    pstat_fname.assign(Stat_P->fname);
    std::string pfps_fname;
    pfps_fname.assign(FPS_P->fname);
    std::string pndr_fname;
    pndr_fname.assign(NDR_P->fname);
    std::string ptemp_fname;
    ptemp_fname.assign(Temp_P->fname);
    std::string pexp_fname;
    pexp_fname.assign(Exp_P->fname);
    std::string pcrop_fname;
    pcrop_fname.assign(Crop->fname);

    // delete classes so destructors are called
    delete fli;
    delete obs;
    delete Stat_D;
    delete Error;
    delete Temp_D;
    delete Stat_P;
    delete Crop;
    delete NDR_P;
    delete FPS_P;
    delete Temp_P;
    delete Exp_P;
    delete NPSD;
    delete NPSP;

    // delete P_Shms
    remove(pstat_fname.c_str());
    remove(pfps_fname.c_str());
    remove(pndr_fname.c_str());
    remove(ptemp_fname.c_str());
    remove(pexp_fname.c_str());
    remove(pcrop_fname.c_str());
}