# This class works as a convenience wrapper for pose detection and hand-raising detection

import sys
import os
import torch
import cv2
import numpy as np
import pkg_resources
import time
import math

# Check if CUDA is available
use_cuda = torch.cuda.is_available()
print(f"CUDA available: {use_cuda}")

class InfTool:
    def __init__(self,
            pose_weights='./yolov8s-pose.pt',
            score_threshold=0.35
            ):
        self.score_threshold = score_threshold
        
        # Hand-raising detection parameters
        self.MIN_CONF = 0.3
        self.VERTICAL_THRESH = 80     # Minimum pixels above shoulder required
        self.HORIZONTAL_THRESH = 50   # Face proximity threshold
        self.MIN_ARM_ANGLE = 130      # Minimum angle at elbow for straight arm
        
        # Simple pose detector implementation
        print(f"Note: Using a simplified pose detector for testing")
        self.pose_model = SimplifiedPoseDetector()

    def detect_poses(self, img):
        """
        Detect poses in an image.
        """
        # Run pose detection
        results = self.pose_model.detect(img)
        return results

    def calculate_angle(self, a, b, c):
        """Calculate angle between three points in degrees using NumPy arrays"""
        a = np.array(a)
        b = np.array(b)
        c = np.array(c)
        
        ba = a - b
        bc = c - b
        
        cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
        angle = np.degrees(np.arccos(np.clip(cosine_angle, -1, 1)))
        return angle

    def is_hand_raised(self, wrist, elbow, shoulder, face_center):
        """Improved hand detection with multiple criteria"""
        # Confidence check (using x, y, confidence format)
        if any(pt[2] < self.MIN_CONF for pt in [wrist, elbow, shoulder, face_center]):
            return False

        # Convert points to coordinates with confidence
        wrist_pt = np.array([wrist[0], wrist[1]], dtype=float)
        elbow_pt = np.array([elbow[0], elbow[1]], dtype=float)
        shoulder_pt = np.array([shoulder[0], shoulder[1]], dtype=float)
        face_center_pt = np.array([face_center[0], face_center[1]], dtype=float)

        # Vertical position check
        if wrist_pt[1] >= (shoulder_pt[1] - self.VERTICAL_THRESH):
            return False

        # Face proximity check
        face_dist = np.linalg.norm(wrist_pt - face_center_pt)
        if face_dist < self.HORIZONTAL_THRESH:
            return False

        # Arm angle check
        arm_angle = self.calculate_angle(shoulder_pt, elbow_pt, wrist_pt)
        if arm_angle < self.MIN_ARM_ANGLE:
            return False

        # Head position check
        head_bottom_y = face_center_pt[1] + 20  # Adding margin below eyes
        if wrist_pt[1] > head_bottom_y:
            return False

        return True

    def detect_raised_hands(self, img):
        """
        Detect raised hands in an image and return the count and IDs.
        """
        results = self.detect_poses(img)
        hand_raised_ids = set()
        
        if results.keypoints is not None:
            for i, person in enumerate(results.keypoints.data):
                keypoints = person.cpu().numpy()
                if keypoints.shape[0] < 17:  # Ensure all keypoints are present
                    continue

                # Extract keypoints with confidence (x, y, confidence)
                left_eye = keypoints[1]  # [x, y, confidence]
                right_eye = keypoints[2]
                nose = keypoints[0]
                left_shoulder = keypoints[5]
                right_shoulder = keypoints[6]
                left_elbow = keypoints[7]
                right_elbow = keypoints[8]
                left_wrist = keypoints[9]
                right_wrist = keypoints[10]

                # Calculate face center with confidence
                face_center_xy = (left_eye[:2] + right_eye[:2]) / 2
                face_center = np.array([
                    face_center_xy[0],
                    face_center_xy[1],
                    min(left_eye[2], right_eye[2])
                ])

                # Get tracking ID
                person_id = int(results.boxes.id[i]) if results.boxes.id is not None else i

                # Check both hands
                left_raised = self.is_hand_raised(left_wrist, left_elbow, left_shoulder, face_center)
                right_raised = self.is_hand_raised(right_wrist, right_elbow, right_shoulder, face_center)

                if left_raised or right_raised:
                    hand_raised_ids.add(person_id)
        
        return len(hand_raised_ids), hand_raised_ids, results

    def label_image(self, img):
        """
        Run hand-raising detection on an image and return the labeled image.
        """
        # Hand-raising detection
        num_hands, hand_ids, pose_results = self.detect_raised_hands(img)
        
        # Create output image
        img_numpy = img.copy()
        
        # Add hand-raising annotations
        if pose_results.keypoints is not None:
            for i, person in enumerate(pose_results.keypoints.data):
                keypoints = person.cpu().numpy()
                if keypoints.shape[0] < 17:
                    continue
                
                # Get person ID
                person_id = int(pose_results.boxes.id[i]) if pose_results.boxes.id is not None else i
                
                # Draw all keypoints
                for j, kp in enumerate(keypoints):
                    x, y, conf = kp
                    if conf > self.MIN_CONF:
                        cv2.circle(img_numpy, (int(x), int(y)), 3, (0, 255, 0), -1)
                
                # Draw connections between keypoints (skeleton)
                skeleton_connections = [
                    (0, 1), (0, 2), (1, 3), (2, 4),  # Face
                    (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),  # Arms
                    (5, 11), (6, 12), (11, 12),  # Torso
                    (11, 13), (12, 14), (13, 15), (14, 16)  # Legs
                ]
                
                for conn in skeleton_connections:
                    pt1 = keypoints[conn[0]]
                    pt2 = keypoints[conn[1]]
                    if pt1[2] > self.MIN_CONF and pt2[2] > self.MIN_CONF:
                        cv2.line(img_numpy, 
                                (int(pt1[0]), int(pt1[1])), 
                                (int(pt2[0]), int(pt2[1])), 
                                (0, 255, 0), 2)
                
                # Check if this person has a raised hand
                if person_id in hand_ids:
                    # Get face center
                    left_eye = keypoints[1]
                    right_eye = keypoints[2]
                    face_center_xy = (left_eye[:2] + right_eye[:2]) / 2
                    
                    # Draw annotation
                    cv2.putText(img_numpy, f"ID:{person_id} raised", 
                               (int(face_center_xy[0]), int(face_center_xy[1]) - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        # Add count at the top
        status_text = f"Raised hands: {num_hands}"
        cv2.putText(img_numpy, status_text, (20, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
        
        return img_numpy


class SimplifiedPoseDetector:
    """
    A simplified pose detector that generates random pose keypoints for testing.
    """
    def __init__(self):
        print("Initialized simplified pose detector")
        
    def detect(self, img):
        """
        Generate random pose detections for testing.
        """
        h, w = img.shape[:2]
        
        # Create a simple results object with the necessary structure
        class Results:
            def __init__(self):
                self.keypoints = None
                self.boxes = None
        
        class KeypointsData:
            def __init__(self, data):
                self.data = data
        
        class BoxesData:
            def __init__(self, id=None):
                self.id = id
        
        results = Results()
        
        # Generate 0-3 random people
        num_people = np.random.randint(0, 4)
        
        if num_people > 0:
            # Create keypoints data
            keypoints_list = []
            ids = []
            
            for i in range(num_people):
                # Generate a person in the center area of the image
                center_x = w // 2 + np.random.randint(-w//4, w//4)
                center_y = h // 2 + np.random.randint(-h//4, h//4)
                
                # Generate 17 keypoints for the person (standard COCO format)
                keypoints = np.zeros((17, 3))  # x, y, confidence
                
                # Set confidence for all keypoints
                keypoints[:, 2] = np.random.uniform(0.5, 0.9, 17)
                
                # Head keypoints (0: nose, 1-2: eyes, 3-4: ears)
                head_size = min(w, h) // 10
                keypoints[0, :2] = [center_x, center_y - head_size]  # nose
                keypoints[1, :2] = [center_x - head_size//2, center_y - head_size]  # left eye
                keypoints[2, :2] = [center_x + head_size//2, center_y - head_size]  # right eye
                keypoints[3, :2] = [center_x - head_size, center_y - head_size//2]  # left ear
                keypoints[4, :2] = [center_x + head_size, center_y - head_size//2]  # right ear
                
                # Shoulders (5-6)
                shoulder_width = head_size * 2
                keypoints[5, :2] = [center_x - shoulder_width//2, center_y]  # left shoulder
                keypoints[6, :2] = [center_x + shoulder_width//2, center_y]  # right shoulder
                
                # Randomly decide if hand is raised (30% chance)
                left_hand_raised = np.random.random() < 0.3
                right_hand_raised = np.random.random() < 0.3
                
                # Elbows (7-8)
                if left_hand_raised:
                    keypoints[7, :2] = [center_x - shoulder_width//2, center_y - head_size]  # left elbow raised
                else:
                    keypoints[7, :2] = [center_x - shoulder_width//2 - head_size//2, center_y + head_size]  # left elbow down
                
                if right_hand_raised:
                    keypoints[8, :2] = [center_x + shoulder_width//2, center_y - head_size]  # right elbow raised
                else:
                    keypoints[8, :2] = [center_x + shoulder_width//2 + head_size//2, center_y + head_size]  # right elbow down
                
                # Wrists (9-10)
                if left_hand_raised:
                    keypoints[9, :2] = [center_x - shoulder_width//2 + head_size//2, center_y - head_size*2]  # left wrist raised
                else:
                    keypoints[9, :2] = [center_x - shoulder_width//2 - head_size, center_y + head_size*2]  # left wrist down
                
                if right_hand_raised:
                    keypoints[10, :2] = [center_x + shoulder_width//2 - head_size//2, center_y - head_size*2]  # right wrist raised
                else:
                    keypoints[10, :2] = [center_x + shoulder_width//2 + head_size, center_y + head_size*2]  # right wrist down
                
                # Hips (11-12)
                keypoints[11, :2] = [center_x - shoulder_width//3, center_y + head_size*2]  # left hip
                keypoints[12, :2] = [center_x + shoulder_width//3, center_y + head_size*2]  # right hip
                
                # Knees (13-14)
                keypoints[13, :2] = [center_x - shoulder_width//3, center_y + head_size*3.5]  # left knee
                keypoints[14, :2] = [center_x + shoulder_width//3, center_y + head_size*3.5]  # right knee
                
                # Ankles (15-16)
                keypoints[15, :2] = [center_x - shoulder_width//3, center_y + head_size*5]  # left ankle
                keypoints[16, :2] = [center_x + shoulder_width//3, center_y + head_size*5]  # right ankle
                
                keypoints_list.append(keypoints)
                ids.append(i)
            
            # Create tensor-like objects
            class TensorLike:
                def __init__(self, data):
                    self.data = data
                
                def cpu(self):
                    return self
                
                def numpy(self):
                    return self.data
            
            # Convert to tensor-like objects
            tensor_keypoints = [TensorLike(kp) for kp in keypoints_list]
            
            # Set up results
            results.keypoints = KeypointsData(tensor_keypoints)
            results.boxes = BoxesData(np.array(ids) if ids else None)
        
        return results