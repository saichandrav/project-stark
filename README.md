# STARK: Real-Time Weapon Detection and Alert System

STARK is an AI-driven security system designed to detect weapons such as guns and knives in real time using computer vision. When a threat is detected, the system instantly sends alerts, uploads evidence, and logs all events securely.

---

## Features

- Real-time video analysis using YOLO
- Detection of weapons such as guns and knives
- Instant alert system using Twilio (SMS or WhatsApp)
- Automatic image upload using Cloudinary
- Local event logging using SQLite
- Multi-threaded architecture for efficient performance
- Lightweight and deployable on edge devices or servers

---

## Tech Stack

### Core Libraries
- **Python**
- **Ultralytics YOLO** for object detection
- **OpenCV** for camera feed and image processing
- **SQLite** for event logging
- **Twilio** for notifications
- **Cloudinary** for media storage
- **Socket Programming** for internal communication

---

## How It Works

1. STARK loads the trained YOLO model.
2. The camera feed is processed frame by frame.
3. If a weapon is detected:
   - The frame is captured and uploaded to Cloudinary.
   - An alert message is sent with the detection details.
   - The event is stored in the SQLite database.
4. The system continues monitoring without interruption.

---



## prerequisites 

1. twilio :- create a twilio account and get the phone number of twilio account and get the required details of the code like authtoken and sid from profile section !!
2. create a cloudnary account and get the required details like secret key and api key
3. make sure that all the packages used in the code are installed properly in your device
4. replace (0) with the path of cctv camera at the captude function/keyword to connect it to cctv camera
5. we can even try it out with the webcam or the laptopcamera just donot change the 0 value from the capture function
6. go to the whatsapp and send the joining chat(eg : join-sample-code ) to twilio phone number to get started with messages
7. run the python file !!