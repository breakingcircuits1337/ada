import platform
import psutil
import GPUtil
from typing import Dict, Union

def info() -> str:
    """
    Gathers system information including CPU, RAM, and GPU details.
    
    Returns:
        str: A formatted string summary of system stats.
    """
    
    # Gather Data
    cpu_percent = psutil.cpu_percent()
    svmem = psutil.virtual_memory()
    mem_percent = svmem.percent
    
    gpu_info = "No GPU Detected"
    try:
        gpus = GPUtil.getGPUs()
        if gpus:
            gpu = gpus[0]
            gpu_info = f"{gpu.name} ({gpu.load*100:.1f}%)"
    except Exception:
        pass

    summary = (
        f"System Status: ONLINE\n"
        f"CPU Usage: {cpu_percent}%\n"
        f"Memory Usage: {mem_percent}%\n"
        f"GPU: {gpu_info}"
    )
    
    return summary

def get_stats_dict() -> Dict[str, float]:
    """
    Returns a dictionary of current system stats for API/Broadcasting.
    
    Returns:
        dict: {"cpu": float, "memory": float, "gpu": float}
    """
    try:
        gpus = GPUtil.getGPUs()
        gpu_load = gpus[0].load * 100 if gpus else 0.0
    except Exception:
        gpu_load = 0.0
        
    return {
        "cpu": psutil.cpu_percent(),
        "memory": psutil.virtual_memory().percent,
        "gpu": gpu_load
    }

if __name__ == "__main__":
    print(info())
