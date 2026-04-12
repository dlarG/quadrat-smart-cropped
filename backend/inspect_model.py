import torch
import os

def inspect_model(model_path):
    """Inspect the structure of the saved model"""
    print(f"Inspecting model: {model_path}")
    
    if not os.path.exists(model_path):
        print("❌ Model file does not exist!")
        return
    
    try:
        # Load checkpoint
        device = torch.device('cpu')  # Use CPU for inspection
        checkpoint = torch.load(model_path, map_location=device)
        
        print(f"Model file type: {type(checkpoint)}")
        print(f"Model file size: {os.path.getsize(model_path) / (1024*1024):.2f} MB")
        
        if isinstance(checkpoint, dict):
            print("Dictionary keys:", list(checkpoint.keys()))
            
            # Check for common keys
            if 'model_state_dict' in checkpoint:
                state_dict = checkpoint['model_state_dict']
                print("Found 'model_state_dict'")
            elif 'state_dict' in checkpoint:
                state_dict = checkpoint['state_dict']
                print("Found 'state_dict'")
            elif 'model' in checkpoint:
                if hasattr(checkpoint['model'], 'state_dict'):
                    state_dict = checkpoint['model'].state_dict()
                    print("Found 'model' object")
                else:
                    state_dict = checkpoint['model']
                    print("Found 'model' as state dict")
            else:
                # Assume the whole checkpoint is the state dict
                state_dict = checkpoint
                print("Using entire checkpoint as state dict")
            
            if isinstance(state_dict, dict):
                print(f"\nState dict has {len(state_dict)} keys")
                print("First 10 layer names:")
                for i, key in enumerate(list(state_dict.keys())[:10]):
                    shape = state_dict[key].shape if hasattr(state_dict[key], 'shape') else 'unknown'
                    print(f"  {i+1}. {key}: {shape}")
                
                if len(state_dict) > 10:
                    print(f"  ... and {len(state_dict) - 10} more layers")
                    
        elif hasattr(checkpoint, '__dict__'):
            print("This appears to be a complete model object")
            print("Model type:", type(checkpoint))
            if hasattr(checkpoint, 'state_dict'):
                state_dict = checkpoint.state_dict()
                print(f"Model has {len(state_dict)} parameters")
                print("First 5 layer names:")
                for i, key in enumerate(list(state_dict.keys())[:5]):
                    shape = state_dict[key].shape if hasattr(state_dict[key], 'shape') else 'unknown'
                    print(f"  {i+1}. {key}: {shape}")
        else:
            print("Unknown model format")
            
    except Exception as e:
        print(f"❌ Error inspecting model: {str(e)}")

if __name__ == "__main__":
    model_path = os.path.join('models', 'segmentation', 'coral_unet_best.pth')
    inspect_model(model_path)
