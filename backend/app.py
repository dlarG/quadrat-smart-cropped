from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import cv2
import numpy as np
from ultralytics import YOLO
import os
import base64
from PIL import Image
import io
import uuid
import shutil
import gc
import torch

app = Flask(__name__)
CORS(app)

torch.backends.cudnn.benchmark = False
if torch.cuda.is_available():
    torch.cuda.empty_cache()

MODEL_PATH = os.path.join('models', 'best.pt')
model = YOLO(MODEL_PATH)

UPLOAD_DIR = 'uploads'
OUTPUT_DIR = 'outputs'
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def order_points(pts):
    #Order points in clockwise order starting from top-left
    rect = np.zeros((4, 2), dtype="float32")
    
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    
    return rect

def four_point_transform(image, pts, width=None, height=None):
    #Apply perspective transform to get top-down view
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    
    if width is None or height is None:
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))
        
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))
        
        width = maxWidth if width is None else width
        height = maxHeight if height is None else height
    
    dst = np.array([
        [0, 0],
        [width - 1, 0],
        [width - 1, height - 1],
        [0, height - 1]
    ], dtype="float32")
    
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (width, height))
    
    return warped

def enhance_contour_detection(mask):
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.dilate(mask, kernel, iterations=1)
    return mask

def resize_image_if_large(image, max_size=1024):
    height, width = image.shape[:2]
    
    if max(height, width) > max_size:
        if height > width:
            new_height = max_size
            new_width = int(width * max_size / height)
        else:
            new_width = max_size
            new_height = int(height * max_size / width)
        
        image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
        scale_factor = max_size / max(height, width)
        return image, scale_factor
    
    return image, 1.0

def detect_and_rectify_quadrats(image_path, conf_threshold=0.25):
    #"Main function to detect and rectify quadrats
    try:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("Could not load image")
        
        print(f"Original image size: {img.shape}")
        
        #resize image if too large to save memory
        img_resized, scale_factor = resize_image_if_large(img, max_size=1024)
        print(f"Resized image size: {img_resized.shape}, scale factor: {scale_factor}")
        
        original_img = img.copy()
        
        # Run YOLO inference
        results = model(img_resized, conf=conf_threshold, verbose=False)
        
        rectified_data = []
        
        if results[0].masks is not None:
            masks = results[0].masks.data.cpu().numpy()
            boxes = results[0].boxes.data.cpu().numpy()
            class_names = results[0].names
            
            print(f"Found {len(masks)} detections")
            
            for i, (mask, box) in enumerate(zip(masks, boxes)):
                try:
                    x1, y1, x2, y2, conf, cls = box
                    
                    # Scale coordinates back to original image size
                    if scale_factor != 1.0:
                        x1, y1, x2, y2 = x1/scale_factor, y1/scale_factor, x2/scale_factor, y2/scale_factor
                    
                    mask_binary = (mask > 0.5).astype(np.uint8) * 255
                    mask_resized = cv2.resize(mask_binary, (original_img.shape[1], original_img.shape[0]))
                    mask_enhanced = enhance_contour_detection(mask_resized)
                    
                    contours, _ = cv2.findContours(mask_enhanced, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    
                    if contours:
                        largest_contour = max(contours, key=cv2.contourArea)
                        contour_area = cv2.contourArea(largest_contour)
                        
                        epsilon = 0.02 * cv2.arcLength(largest_contour, True)
                        approx = cv2.approxPolyDP(largest_contour, epsilon, True)
                        
                        success = False
                        method_used = ""
                        
                        if len(approx) == 4:
                            points = approx.reshape(4, 2).astype(np.float32)
                            method_used = "corner_detection"
                            success = True
                        elif len(approx) > 4:
                            hull = cv2.convexHull(largest_contour)
                            epsilon = 0.01 * cv2.arcLength(hull, True)
                            approx_hull = cv2.approxPolyDP(hull, epsilon, True)
                            
                            if len(approx_hull) == 4:
                                points = approx_hull.reshape(4, 2).astype(np.float32)
                                method_used = "convex_hull"
                                success = True
                        
                        if not success:
                            rect = cv2.minAreaRect(largest_contour)
                            box_points = cv2.boxPoints(rect)
                            points = np.float32(box_points)
                            method_used = "min_area_rect"
                            success = True
                        
                        if success:
                            rectified = four_point_transform(original_img, points)
                            
                            if rectified.shape[0] > 10 and rectified.shape[1] > 10:
                                # Generate unique filename
                                filename = f"rectified_{i+1}_{uuid.uuid4().hex[:8]}.png"
                                output_path = os.path.join(OUTPUT_DIR, filename)
                                cv2.imwrite(output_path, rectified)
                                
                                # Convert to base64 for frontend
                                _, buffer = cv2.imencode('.png', rectified)
                                img_base64 = base64.b64encode(buffer).decode('utf-8')
                                
                                class_name = class_names[int(cls)] if int(cls) in class_names else "quadrat"
                                
                                rectified_data.append({
                                    'id': i + 1,
                                    'image_base64': img_base64,
                                    'class': class_name,
                                    'confidence': float(conf),
                                    'method_used': method_used,
                                    'filename': filename,
                                    'size': {
                                        'width': rectified.shape[1],
                                        'height': rectified.shape[0]
                                    },
                                    'contour_area': float(contour_area)
                                })
                                
                                print(f"Successfully processed quadrat {i+1}")
                                
                except Exception as e:
                    print(f"Error processing quadrat {i+1}: {str(e)}")
                    continue
        
        # Create annotated image using resized image for display
        annotated_img = results[0].plot() if results[0].masks is not None else img_resized
        _, buffer = cv2.imencode('.png', annotated_img)
        annotated_base64 = base64.b64encode(buffer).decode('utf-8')
          # Clean up memory
        del img_resized
        if 'masks' in locals() and masks is not None:
            del masks
        if 'boxes' in locals() and boxes is not None:
            del boxes
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        return rectified_data, annotated_base64
        
    except Exception as e:
        print(f"Error in detect_and_rectify_quadrats: {str(e)}")
        # Clean up memory even on error
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        raise e

@app.route('/api/upload', methods=['POST'])
def upload_image():
    try:
        print("Upload request received")
        
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        print(f"Processing file: {file.filename}")
        
        # Get confidence threshold from form data
        conf_threshold = float(request.form.get('confidence', 0.75))
        print(f"Using confidence threshold: {conf_threshold}")
        
        # Save uploaded file
        filename = f"upload_{uuid.uuid4().hex[:8]}_{file.filename}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        file.save(filepath)
        print(f"File saved to: {filepath}")
        
        # Process the image
        print("Starting quadrat detection...")
        rectified_data, annotated_base64 = detect_and_rectify_quadrats(filepath, conf_threshold)
        print(f"Detection completed. Found {len(rectified_data)} quadrats")
        
        # Convert original image to base64 (resize for display)
        original_img = cv2.imread(filepath)
        original_resized, _ = resize_image_if_large(original_img, max_size=800)
        _, buffer = cv2.imencode('.png', original_resized)
        original_base64 = base64.b64encode(buffer).decode('utf-8')
        
        response_data = {
            'success': True,
            'original_image': original_base64,
            'annotated_image': annotated_base64,
            'rectified_quadrats': rectified_data,
            'total_detected': len(rectified_data),
            'confidence_threshold': conf_threshold
        }
        
        # Clean up uploaded file
        try:
            os.remove(filepath)
            print("Cleaned up uploaded file")
        except:
            pass
        
        print("Sending response to frontend")
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error in upload_image: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Clean up memory on error
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

@app.route('/api/download/<filename>')
def download_file(filename):
    try:
        filepath = os.path.join(OUTPUT_DIR, filename)
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health_check():
    return jsonify({'status': 'healthy', 'model_loaded': True})

@app.route('/api/clear-outputs')
def clear_outputs():
    try:
        if os.path.exists(OUTPUT_DIR):
            shutil.rmtree(OUTPUT_DIR)
            os.makedirs(OUTPUT_DIR)
        return jsonify({'success': True, 'message': 'Output directory cleared'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)