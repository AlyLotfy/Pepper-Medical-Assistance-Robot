import pybullet as p
import gym
import sys
import os
import torch
import cv2
import pkg_resources
import subprocess
import threading
import json
import numpy as np
from copy import copy

# Path to the YOLOv5 model
weights_path = "./yolov5s.pt"  # Update this path to where you saved the YOLOv5 model

isFinished = False

# YOLOv5 detection tool class to replace InfTool
class YOLOv5Tool:
    def __init__(self, weights, score_threshold=0.35 ):
        self.score_threshold = score_threshold
        
        # Load YOLOv5 model
        print(f"Loading YOLOv5 model from {weights}")
        self.model = torch.hub.load('ultralytics/yolov5', 'custom', path=weights)
        self.model.conf = score_threshold  # Set confidence threshold
        
        # COCO class names
        self.class_names = ['person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
                           'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat',
                           'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack',
                           'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
                           'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
                           'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
                           'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair',
                           'couch', 'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse',
                           'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink', 'refrigerator',
                           'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush']
    
    def process_batch(self, img):
        # Process image through YOLOv5
        results = self.model(img)
        return results, None  # Return results and None for frame to match YOLACT API
    
    def raw_inference(self, img, preds=None, frame=None):
        if preds is None:
            preds, _ = self.process_batch(img)
        
        # Extract detection results
        pred = preds.xyxy[0].cpu().numpy()  # Get predictions in xyxy format
        
        if len(pred) == 0:
            return None, [], None, None, None, None
        
        # Extract classes, scores, boxes
        classes = pred[:, 5].astype(int)
        scores = pred[:, 4]
        boxes = pred[:, :4]  # [x1, y1, x2, y2]
        
        # Create dummy masks (YOLOv5 doesn't have masks like YOLACT)
        masks = np.zeros((len(classes), img.shape[0], img.shape[1]), dtype=np.uint8)
        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = box.astype(int)
            masks[i, y1:y2, x1:x2] = 1
        
        # Get class names
        class_names = [self.class_names[int(c)] for c in classes]
        
        # Calculate centroids from boxes
        centroids = []
        for box in boxes:
            x1, y1, x2, y2 = box
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)
            centroids.append([cx, cy])
        
        return classes, class_names, scores, boxes, masks, centroids
    
    def label_image(self, img, preds=None):
        if preds is None:
            preds, _ = self.process_batch(img)
        
        # Use YOLOv5's built-in rendering
        img_with_boxes = preds.render()[0]
        return img_with_boxes

def assignDirections(class_names, centroids):
    if not centroids:
        return {}
    xCentroids = [row[0] for row in centroids]
    center = max(xCentroids) - min(xCentroids)
    directions = {}
    for i in range(0, len(centroids)):
        if xCentroids[i] < center:
            directions[class_names[i]] = "left"
        else:
            directions[class_names[i]] = "right"
    return directions

def dumpData(data):
    with open('classes.json', 'w') as f:
        try:
            json.dump(data, f)
        except:
            dumpData(data)

def getData():
    with open("classes.json") as f:
        try:
            return json.load(f)
        except:
            return getData()

def assignAndDumpData(init, class_names, class_names_upd, directions, directions_upd):
    data = {'init': init, 'class_names': class_names, 'directions': directions, 'class_names_upd': class_names_upd, 'directions_upd': directions_upd}
    dumpData(data)

def firstJsonUpdate(class_names, directions):
    assignAndDumpData("true", class_names, class_names, directions, directions)

def normalJsonUpdate(class_names, directions):
    oldData = getData()
    assignAndDumpData("false", copy(oldData['class_names']), class_names, copy(oldData['directions']), directions)

def updateInfo(class_names, directions):
    data = getData()
    if data["init"] == "true":
        firstJsonUpdate(class_names, directions)
    else:
        normalJsonUpdate(class_names, directions)

def streamPepperCamera():
    subprocess.run(["python2", fileName, '--speak_constantly=True'])
    global isFinished
    isFinished = True

def clean(image):
    if os.path.exists(image):
        os.remove(image)
    data = {"init": "true"}
    dumpData(data)

if __name__ == "__main__":
    fileDir = os.path.dirname(os.path.realpath('__file__'))
    fileName = os.path.join(fileDir, "../yolactDemo.py")
    fileName = os.path.abspath(os.path.realpath(fileName))
    name = "camera.jpg"
    
    # Create an empty classes.json file if it doesn't exist
    if not os.path.exists("classes.json"):
        dumpData({"init": "true"})
    
    try:
        # Initialize the YOLOv5 model
        print(f"Initializing YOLOv5 model with weights: {weights_path}")
        cnn = YOLOv5Tool(weights=weights_path, score_threshold=0.35)
        
        pepperThread = threading.Thread(target=streamPepperCamera)
        pepperThread.start()
        
        while not isFinished:
            img = cv2.imread(name)
            if img is None:
                continue
            else:
                preds, frame = cnn.process_batch(img)
                classes, class_names, scores, boxes, masks, centroids = cnn.raw_inference(img, preds=preds, frame=frame)
                if classes is not None:
                    updateInfo(class_names, assignDirections(class_names, centroids))
                img_numpy = cnn.label_image(img, preds=preds)
                cv2.imshow('img_yolov5', img_numpy)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        
        clean(name)
    except Exception as e:
        print(f"Error initializing or running YOLOv5: {e}")
        import traceback
        traceback.print_exc()