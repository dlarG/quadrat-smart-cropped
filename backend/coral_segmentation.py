import torch
import torch.nn as nn
import cv2
import numpy as np
import albumentations as A
from albumentations.pytorch import ToTensorV2
import os

# Coral class definitions
CORAL_CLASSES = {
    1: {'name': 'acropora-branching', 'color': '#FF6B6B', 'category': 'hard_coral'},
    2: {'name': 'acropora-tabulate', 'color': '#FFD166', 'category': 'hard_coral'},
    3: {'name': 'encrusting', 'color': '#06D6A0', 'category': 'hard_coral'},
    4: {'name': 'foliose', 'color': '#118AB2', 'category': 'hard_coral'},
    5: {'name': 'massive', 'color': '#073B4C', 'category': 'hard_coral'},
    6: {'name': 'mushroom', 'color': '#EF476F', 'category': 'hard_coral'},
    7: {'name': 'non-acropora-branching', 'color': '#7209B7', 'category': 'hard_coral'},
    8: {'name': 'submassive', 'color': '#F72585', 'category': 'hard_coral'}
}

COLOR_MAP = {
    0: [0, 0, 0],           # Background - Black
    1: [255, 107, 107],     # Acropora-branching - #FF6B6B  
    2: [255, 209, 102],     # Acropora-tabulate - #FFD166
    3: [76, 205, 196],      # Encrusting - #4ECDC4
    4: [17, 138, 178],      # Foliose - #118AB2
    5: [7, 59, 76],         # Massive - #073B4C
    6: [239, 71, 111],      # Mushroom - #EF476F
    7: [114, 9, 183],       # Non-acropora-branching - #7209B7
    8: [247, 37, 133]       # Submassive - #F72585
}

class UNet(nn.Module):
    def __init__(self, n_channels=3, n_classes=9, bilinear=True):
        super(UNet, self).__init__()
        self.n_channels = n_channels
        self.n_classes = n_classes
        self.bilinear = bilinear

        self.inc = DoubleConv(n_channels, 64)
        self.down1 = Down(64, 128)
        self.down2 = Down(128, 256)
        self.down3 = Down(256, 512)
        factor = 2 if bilinear else 1
        self.down4 = Down(512, 1024 // factor)
        self.up1 = Up(1024, 512 // factor, bilinear)
        self.up2 = Up(512, 256 // factor, bilinear)
        self.up3 = Up(256, 128 // factor, bilinear)
        self.up4 = Up(128, 64, bilinear)
        self.outc = OutConv(64, n_classes)

    def forward(self, x):
        x1 = self.inc(x)
        x2 = self.down1(x1)
        x3 = self.down2(x2)
        x4 = self.down3(x3)
        x5 = self.down4(x4)
        x = self.up1(x5, x4)
        x = self.up2(x, x3)
        x = self.up3(x, x2)
        x = self.up4(x, x1)
        logits = self.outc(x)
        return logits

class DoubleConv(nn.Module):
    def __init__(self, in_channels, out_channels, mid_channels=None):
        super().__init__()
        if not mid_channels:
            mid_channels = out_channels
        self.double_conv = nn.Sequential(
            nn.Conv2d(in_channels, mid_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(mid_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True)
        )

    def forward(self, x):
        return self.double_conv(x)

class Down(nn.Module):
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.maxpool_conv = nn.Sequential(
            nn.MaxPool2d(2),
            DoubleConv(in_channels, out_channels)
        )

    def forward(self, x):
        return self.maxpool_conv(x)

class Up(nn.Module):
    def __init__(self, in_channels, out_channels, bilinear=True):
        super().__init__()
        if bilinear:
            self.up = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)
            self.conv = DoubleConv(in_channels, out_channels, in_channels // 2)
        else:
            self.up = nn.ConvTranspose2d(in_channels, in_channels // 2, kernel_size=2, stride=2)
            self.conv = DoubleConv(in_channels, out_channels)

    def forward(self, x1, x2):
        x1 = self.up(x1)
        diffY = x2.size()[2] - x1.size()[2]
        diffX = x2.size()[3] - x1.size()[3]

        x1 = nn.functional.pad(x1, [diffX // 2, diffX - diffX // 2,
                                    diffY // 2, diffY - diffY // 2])
        x = torch.cat([x2, x1], dim=1)
        return self.conv(x)

class OutConv(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(OutConv, self).__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size=1)

    def forward(self, x):
        return self.conv(x)

def load_segmentation_model(model_path):
    """Load the coral segmentation model with comprehensive error handling"""
    try:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"Loading model from: {model_path}")
        
        # Load checkpoint
        checkpoint = torch.load(model_path, map_location=device)
        print(f"Checkpoint type: {type(checkpoint)}")
        
        # Strategy 1: Direct model object
        if hasattr(checkpoint, 'eval') and hasattr(checkpoint, 'forward'):
            model = checkpoint
            model.to(device)
            model.eval()
            print("✅ Loaded as complete model object")
            return model
        
        # Strategy 2: Model saved with torch.save(model.state_dict(), path)
        if isinstance(checkpoint, dict):
            print(f"Dictionary with keys: {list(checkpoint.keys())}")
            
            # Try different state dict keys
            state_dict = None
            if 'state_dict' in checkpoint:
                state_dict = checkpoint['state_dict']
                print("Using 'state_dict' key")
            elif 'model_state_dict' in checkpoint:
                state_dict = checkpoint['model_state_dict']
                print("Using 'model_state_dict' key")
            elif 'model' in checkpoint:
                state_dict = checkpoint['model']
                print("Using 'model' key")
            else:
                # Assume the whole dict is the state dict
                state_dict = checkpoint
                print("Using entire checkpoint as state dict")
            
            # Try to load with our UNet architecture
            try:
                model = UNet(n_channels=3, n_classes=9)
                model.load_state_dict(state_dict)
                model.to(device)
                model.eval()
                print("✅ Loaded with custom UNet architecture")
                return model
            except Exception as unet_error:
                print(f"Custom UNet failed: {str(unet_error)}")
                
                # The model might have a different architecture
                # Let's try to create a generic wrapper
                print("Attempting to create a generic model wrapper...")
                
                # Create a simple wrapper class that can work with any segmentation model
                class GenericSegmentationModel(nn.Module):
                    def __init__(self, state_dict):
                        super().__init__()
                        self.state_dict_data = state_dict
                        
                    def forward(self, x):
                        # This is a placeholder - we'll handle prediction differently
                        return x
                
                # For now, return None to disable segmentation
                print("❌ Could not match model architecture")
                return None
        
        # If we get here, unknown format
        print("❌ Unknown model format")
        return None
        
    except Exception as e:
        print(f"❌ Failed to load segmentation model: {str(e)}")
        print("Coral segmentation will be disabled.")
        return None

def predict_segmentation(model, image):
    """Perform segmentation using UNet model with flexible input handling"""
    if model is None:
        raise Exception("Segmentation model not available")
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    transform = A.Compose([
        A.Resize(832, 832),
        A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ToTensorV2()
    ])
    
    try:
        # Preprocess
        original_size = image.shape[:2]
        augmented = transform(image=image)
        input_tensor = augmented['image'].unsqueeze(0).to(device)
        
        # Predict with error handling for different model outputs
        with torch.no_grad():
            output = model(input_tensor)
            
            # Handle different output formats
            if isinstance(output, tuple):
                output = output[0]  # Take first output if multiple
            
            # Handle different tensor shapes
            if len(output.shape) == 4:  # [batch, classes, height, width]
                pred_mask = torch.argmax(output.squeeze(0), dim=0).cpu().numpy()
            elif len(output.shape) == 3:  # [classes, height, width]
                pred_mask = torch.argmax(output, dim=0).cpu().numpy()
            else:
                raise ValueError(f"Unexpected output shape: {output.shape}")
        
        # Resize back to original size
        pred_mask_resized = cv2.resize(pred_mask.astype(np.uint8), 
                                     (original_size[1], original_size[0]), 
                                     interpolation=cv2.INTER_NEAREST)
        
        return pred_mask_resized
        
    except Exception as e:
        print(f"Error in prediction: {str(e)}")
        # Return a dummy mask with background only
        return np.zeros((image.shape[0], image.shape[1]), dtype=np.uint8)

def create_colored_mask(mask):
    """Convert mask to colored image using color map"""
    colored_mask = np.zeros((mask.shape[0], mask.shape[1], 3), dtype=np.uint8)
    for class_id, color in COLOR_MAP.items():
        colored_mask[mask == class_id] = color
    return colored_mask

def create_overlay(image, mask, alpha=0.5):
    """Create overlay of original image and mask"""
    colored_mask = create_colored_mask(mask)
    overlay = cv2.addWeighted(image, 1 - alpha, colored_mask, alpha, 0)
    return overlay

def calculate_coral_coverage(mask):
    """Calculate coral coverage statistics for each class"""
    total_pixels = mask.shape[0] * mask.shape[1]
    unique_classes, pixel_counts = np.unique(mask, return_counts=True)
    
    coverage_data = []
    total_coral_pixels = 0
    
    for class_id, pixel_count in zip(unique_classes, pixel_counts):
        if class_id in CORAL_CLASSES:  # Skip background (class 0)
            percentage = (pixel_count / total_pixels) * 100
            total_coral_pixels += pixel_count
            
            coverage_data.append({
                'class_id': int(class_id),
                'class_name': CORAL_CLASSES[class_id]['name'],
                'category': CORAL_CLASSES[class_id]['category'],
                'color': CORAL_CLASSES[class_id]['color'],
                'pixel_count': int(pixel_count),
                'coverage_percent': round(percentage, 2)
            })
    
    # Calculate total coral coverage
    total_coral_percentage = (total_coral_pixels / total_pixels) * 100
    
    # Sort by coverage percentage (highest first)
    coverage_data.sort(key=lambda x: x['coverage_percent'], reverse=True)
    
    return coverage_data, round(total_coral_percentage, 2)

def segment_rectified_quadrat(model, image_path):
    """Segment coral lifeforms in a rectified quadrat image"""
    try:
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not load image from {image_path}")
        
        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Get segmentation predictions
        predictions = predict_segmentation(model, image_rgb)
        
        # Calculate coverage statistics
        coverage_data, total_coral_coverage = calculate_coral_coverage(predictions)
        
        # Create visualization images
        colored_mask = create_colored_mask(predictions)
        overlay_image = create_overlay(image_rgb, predictions, alpha=0.6)
        
        return {
            'coverage_data': coverage_data,
            'total_coral_coverage': total_coral_coverage,
            'segmentation_mask': predictions,
            'colored_mask': colored_mask,
            'overlay_image': overlay_image,
            'total_pixels': predictions.size
        }
        
    except Exception as e:
        print(f"Error in coral segmentation: {str(e)}")
        return None

def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
