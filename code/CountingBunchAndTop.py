#!/usr/bin/env python
#import device_patches       # Device specific patches for Jetson Nano (needs to be before importing cv2)

import cv2
import os
import sys, getopt
import signal
import time
from edge_impulse_linux.image import ImageImpulseRunner
import pyrebase
import json
import time

Washer_count = 0
Faulty_washer_count = 0
Bolt_count = 0
Lollipop_count = 0
start = 0
flag = 0


start_value = {"Value" : start}
count_data = {"Bolt" : Bolt_count,"Washer":Washer_count,"Faulty_Washer":Faulty_washer_count,"Lollipop":Lollipop_count,}


runner = None
# if you don't want to see a camera preview, set this to False
show_camera = True

if (sys.platform == 'linux' and not os.environ.get('DISPLAY')):
    show_camera = False

def now():
    b = round(time.time() * 1000)
    print("NOW", b)
    return b

def get_webcams():
    port_ids = []
    for port in range(5):
        print("Looking for a camera in port %s:" %port)
        camera = cv2.VideoCapture(port)
        if camera.isOpened():
            ret = camera.read()[0]
            if ret:
                backendName =camera.getBackendName()
                w = camera.get(3)
                h = camera.get(4)
                print("Camera %s (%s x %s) found in port %s " %(backendName,h,w, port))
                port_ids.append(port)
            camera.release()
    return port_ids

def sigint_handler(sig, frame):
    print('Interrupted')
    if (runner):
        runner.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, sigint_handler)

def help():
    print('python classify.py <path_to_model.eim> <Camera port ID, only required when more than 1 camera is present>')

def main(argv):
    global Washer_count,Faulty_washer_count,Bolt_count,Lollipop_count,start,flag
    if flag == 0:
        config = {
        # You can get all these info from the firebase website. It's associated with your account.
        "apiKey": "va6SGLXk01DPOICa8afZkiQh8kWhx3z1usS1s9Qb",
        "authDomain": "counter-a2b53.firebaseapp.com",
        "databaseURL": "https://counter-a2b53-default-rtdb.firebaseio.com/",
        "storageBucket": "projectId.appspot.com"
                }
        firebase = pyrebase.initialize_app(config)
        db = firebase.database()
        db.child("Count").set(count_data)
        db.child("Count_start").set(start_value)
        flag = 1

    try:
        opts, args = getopt.getopt(argv, "h", ["--help"])
    except getopt.GetoptError:
        help()
        sys.exit(2)

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            help()
            sys.exit()

    if len(args) == 0:
        help()
        sys.exit(2)

    model = args[0]

    dir_path = os.path.dirname(os.path.realpath(__file__))
    modelfile = os.path.join(dir_path, model)

    print('MODEL: ' + modelfile)

    with ImageImpulseRunner(modelfile) as runner:
        try:
            model_info = runner.init()
            print('Loaded runner for "' + model_info['project']['owner'] + ' / ' + model_info['project']['name'] + '"')
            labels = model_info['model_parameters']['labels']
            if len(args)>= 2:
                videoCaptureDeviceId = int(args[1])
            else:
                port_ids = get_webcams()
                if len(port_ids) == 0:
                    raise Exception('Cannot find any webcams')
                if len(args)<= 1 and len(port_ids)> 1:
                    raise Exception("Multiple cameras found. Add the camera port ID as a second argument to use to this script")
                videoCaptureDeviceId = int(port_ids[0])

            camera = cv2.VideoCapture(videoCaptureDeviceId)
            ret = camera.read()[0]
            if ret:
                backendName = camera.getBackendName()
                w = camera.get(3)
                h = camera.get(4)
                print("Camera %s (%s x %s) in port %s selected." %(backendName,h,w, videoCaptureDeviceId))
                camera.release()
            else:
                raise Exception("Couldn't initialize selected camera.")

            next_frame = 0 # limit to ~10 fps here
            print("Setting next_frame zero")

            for res, img in runner.classifier(videoCaptureDeviceId):
                if (next_frame > now()):
                    print("NEXT FRAME : ",next_frame)
                    a = (next_frame - now()) / 100
                    print("SLEEPING TIME : ",a)
                    time.sleep(a)

                # print('classification runner response', res)

                if "bounding_boxes" in res["result"].keys():
                    print('Found %d bounding boxes (%d ms.)' % (len(res["result"]["bounding_boxes"]), res['timing']['dsp'] + res['timing']['classification']))
                    Count = len(res["result"]["bounding_boxes"])
                    print(Count)
                    Count_start = db.child("Count_start").get()
                    print(Count_start.val())
                    if Count_start.val()['Value'] == 1:
                      for bb in res["result"]["bounding_boxes"]:
                        #print('\t%s (%.2f): x=%d y=%d w=%d h=%d' % (bb['label'], bb['value'], bb['x'], bb['y'], bb['width'], bb['height']))
                        img = cv2.rectangle(img, (bb['x'], bb['y']), (bb['x'] + bb['width'], bb['y'] + bb['height']), (255, 0, 0), 1)
                        Label  = bb['label']
                        score  = bb['value']
                        if score > 0.85 :
                          if Label == "Washer":
                             Washer_count+=1
                          elif Label == "Faulty Washer":
                             Faulty_washer_count+=1
                          elif Label == "Bolt":
                             Bolt_count+=1
                          elif Label == "Lollipop":
                             Lollipop_count+=1
                    db.child("Count").update({"Bolt" : Bolt_count,"Washer":Washer_count,"Faulty_Washer":Faulty_washer_count,"Lollipop":Lollipop_count,})
                    print("Washer no",Washer_count)
                    print("Faulty Washer",Faulty_washer_count)
                    Washer_count = 0
                    Faulty_washer_count = 0 
                    Bolt_count = 0
                    Lollipop_count = 0
                if (show_camera):
                    cv2.imshow('edgeimpulse', cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
                    if cv2.waitKey(1) == ord('q'):
                        break

                next_frame = now() + 100
                #print("UPDATED NEXT FRAME",next_frame)
        finally:
            if (runner):
                runner.stop()

if __name__ == "__main__":
   main(sys.argv[1:])
