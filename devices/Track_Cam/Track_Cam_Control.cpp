/*
 * A script meant to be run in a tmux session that listens for new input from
 *   the user with regards to the FIU CRED2 and performs actions accordingly. 
 */

#include <string>
#include <fstream>
#include <stdlib.h>
#include <cstring>

#include "FliSdk.h"
#include "KPIC_shmlib.hpp"

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

// the rate at which the temperatures in the state shared memory should be
//   updated (seconds).
double temp_refresh=5;

/*
 * Function that connects to shared memories. 
 *
 * Returns:
 *   int = 1 if pointers already initialized, 0 otherwise.
 */
int Shm_connect(){
    if (Stat_D == NULL){ return 1; }
    // find path to config filez
    std::string path = getenv("CONFIG");
    if (path == NULL) {
        perror("No CONFIG environment variable found.");
        exit(EXIT_FAILURE);
    }
    path += "Track_Cam.ini";

    // make a file object and open config file
    std::ifstream conf

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
    conf.open(path.c_str())
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

    idx = dstat_cf.find(",");
    if (idx == std::string::npos) {
        perror ("Config file unreadable.");
        exit(EXIT_FAILURE);
    } else { dstat_cf.erase(idx, std::string::npos); }

    idx = err_cf.find(",");
    if (idx == std::string::npos) {
        perror ("Config file unreadable.");
        exit(EXIT_FAILURE);
    } else { err_cf.erase(idx, std::string::npos); }

    idx = dtemp_cf.find(",");
    if (idx == std::string::npos) {
        perror ("Config file unreadable.");
        exit(EXIT_FAILURE);
    } else { dtemp_cf.erase(idx, std::string::npos); }

    idx = pstat_cf.find(",");
    if (idx == std::string::npos) {
        perror ("Config file unreadable.");
        exit(EXIT_FAILURE);
    } else { pstat_cf.erase(idx, std::string::npos); }

    idx = crop_cf.find(",");
    if (idx == std::string::npos) {
        perror ("Config file unreadable.");
        exit(EXIT_FAILURE);
    } else { crop_cf.erase(idx, std::string::npos); }

    idx = pndr_cf.find(",");
    if (idx == std::string::npos) {
        perror ("Config file unreadable.");
        exit(EXIT_FAILURE);
    } else { pndr_cf.erase(idx, std::string::npos); }

    idx = pfps_cf.find(",");
    if (idx == std::string::npos) {
        perror ("Config file unreadable.");
        exit(EXIT_FAILURE);
    } else { pfps_cf.erase(idx, std::string::npos); }

    idx = ptemp_cf.find(",");
    if (idx == std::string::npos) {
        perror ("Config file unreadable.");
        exit(EXIT_FAILURE);
    } else { ptemp_cf.erase(idx, std::string::npos); }

    idx = pexp_cf.find(",");
    if (idx == std::string::npos) {
        perror ("Config file unreadable.");
        exit(EXIT_FAILURE);
    } else { pexp_cf.erase(idx, std::string::npos); }

    // query whether camera is on, this will tell us whether to pull values for
    //   shm or just populate with whatever
    bool cam = q_cam_pow();
    
    // if a shared memory doesn't exist and we try to connect to it,
    //   it will throw an error. So make one in that case.
    try { Stat_D = new Shm(dstat_cf); }
    catch (NoShm) {
        uint8_t data[1];
        uint16_t size[3] = {1, 0, 0};
        bool script = 1;
        bool fan;
        bool led;
        if (cam) {
            std::string fan;
            fli->credTwo()->getFanMode(fan);
            fan = (fan == "Automatic");
            fli->getLedStat(led);
        } else { fan = false; led = false; }

        data[0] = (uint8_t)script + (uint8_t)cam << 1 + (uint8_t)fan << 2 +
               (uint8_t)led << 3;
        Stat_D = new Shm(dstat_cf, &size, 3, 1, &data);
    } 

    try { Error = new Shm(err_cf); }
    catch (NoShm) {
        uint8_t data[1] = {0};
        uint16_t size[3] = {1, 0, 0};
        Error = new Shm(err_cf, &size, 3, 1, &data); 
    }

    try { Temp_D = new Shm(dtemp_cf) }
    catch (NoShm) {
        double data[6];
        uint16_t size[3] = {6, 0, 0};
        if (cam) { fli->getAllTemp(&data, &data + 1, &data + 2, &data + 3, 
                                   &data + 4, &data + 5) }
        Temp_D = new Shm(dtemp_cf, &size, 3, 10, &data);
    }

    try { Stat_P = new Shm(pstat_cf); }
    catch (NoShm) {
        uint8_t data[1];
        uint16_t size[3] = {1, 0, 0};
        Stat_P = new Shm(pstat_cf, &size, 3, 1, &data);
    }

    try { Crop = new Shm(crop_cf); }
    catch (NoShm) {
        uint16_t data[4];
        uint16_t size[3] = {4, 0, 0};
        Crop = new Shm(crop_cf, &size, 3, 3, &data);
    }

    try { NDR_P = new Shm(pndr_cf); }
    catch (NoShm) {
        uint8_t data[1];
        uint16_t size[3] = {1, 0, 0};
        NDR_P = new Shm(pndr_cf, &size, 3, 1, &data);
    }

    try { FPS_P = new Shm(pfps_cf); }
    catch (NoShm) {
        double data[1];
        uint16_t size[3] = {1, 0, 0};
        FPS_P = new Shm(pfps_cf, &size, 3, 10, &data);
    }

    try { Temp_P = new Shm(ptemp_cf); }
    catch (NoShm) {
        double data[2] = {0, temp_refresh};
        uint16_t size[3] = {2, 0, 0};
        Temp_P = new Shm(ptemp_cf, &size, 3, 10, &data);
    }

    try { Exp_P = new Shm(pexp_cf); }
    catch (NoShm) {
        double data[1];
        uint16_t size[3] = {1, 0, 0};
        Exp_P = new Shm(pexp_cf, &size, 3, 10, &data);
    }

    return 0;
}

bool q_cam_pow(){
}

void cam_on(){
}

void cam_off(){
}

int main(){
    fli = new FliSdk();

    // Connect to Shared memories
    Shm_connect();
}
