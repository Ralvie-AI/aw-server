
import numpy as np
import cv2
import json
import platform
import importlib.util
import gc
import os
import time
import logging
import psutil

from sd_core.const import STAGING
from sd_core.log import setup_logging

logger = logging.getLogger(__name__)


class ActiveWindowOCRText:
    def __init__(self, warmup=False) -> None:
        super().__init__()
        self._reader_cache = None

        if warmup:
            self._warmup()

    def _warmup(self):
        try:       
            #logging.getlogger("RapidOCR").setLevel(logging.ERROR)

            reader = self.get_cached_reader()
            warmup_img = np.ones((256, 256, 3), dtype=np.uint8) * 255
            cv2.putText(warmup_img, "Warmup", (10, 150),cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 0, 0), 3)
            _ = reader(warmup_img)
            del warmup_img
            #logger.info("[OCRText] Warmup completed")
        except Exception:
            #logger.exception("[OCRText] Warmup failed")
            raise


    def use_mps(self) -> bool:
        """Detect apple silicon"""
        try:
            if platform.machine() == "arm64":
                #logger.info(f"[OCRText] Detected Apple Silicon")
                return True
            else:
                return False
        except Exception:
            return False

    def has_intel_cpu(self) -> bool:
        """Rough check if CPU is Intel."""
        try:
            cpu_info = (platform.processor() or platform.machine() or "").lower()
            if "intel" in cpu_info:
                #logger.info(f"[OCRText] Detected Intel CPU: {cpu_info}")
                return True
            else:
                return False
        except Exception:
            return False

    def get_cached_reader(self):
        """
        Return a cached RapidOCR reader, chosen based on hardware.
        Apple Silicon -> Torch + MPS
        Intel -> OpenVINO
        Fallback -> ONNX Runtime 
        """
        if self._reader_cache is not None:
            return self._reader_cache

        #logger.info("[OCRText] Initializing RapidOCR reader")

        try:
            from rapidocr import RapidOCR, EngineType, OCRVersion
        except Exception as e:
            #logger.exception(f"[OCRText] Failed to import RapidOCR: {e}")
            raise RuntimeError(f"No suitable RapidOCR backend found. {e}")

        # # --- Apple Silicon (Torch) ---
        if self.use_mps():
            #logger.info("[OCRText] Apple Silicon detected, checking Torch + MPS support")
            if importlib.util.find_spec("torch") is None:
                print('Torch not installed')
                #logger.warning("[OCRText] Torch not installed, cannot use MPS backend")
            else:
                try:
                    import torch
                    if torch.backends.mps.is_built() and torch.backends.mps.is_available():
                        self._reader_cache = RapidOCR(params={
                            "Det.engine_type": EngineType.TORCH,
                            "Rec.engine_type": EngineType.TORCH,
                            "Cls.engine_type": EngineType.TORCH,
                            "Global.use_cls": False,
                            "EngineConfig.torch.use_mps": True,
                            "Cls.cls_batch_num": 16,
                            "Rec.rec_batch_num": 16,

                            "Rec.ocr_version": OCRVersion.PPOCRV5 ,
                        })
                        logger.info("[OCR] Backend: TORCH (MPS - Apple Silicon GPU)")
                        return self._reader_cache
                    else:
                        print('Torch MPS backend is NOT available')
                        # logger.warning(
                        #     "[OCRText] Torch installed but MPS backend is NOT available "
                        #     "(likely Intel Mac or unsupported macOS version)"
                        # )
                except Exception as e:
                    print(e)

        # --- Intel-based MacBook from 2006 to 2021 (OpenVINO) ---
        if self.has_intel_cpu():
            if importlib.util.find_spec("openvino") is not None:
                try:
                    self._reader_cache = RapidOCR(params={
                        "Det.engine_type": EngineType.OPENVINO,
                        "Rec.engine_type": EngineType.OPENVINO,
                        "Global.use_cls": False,
                        "Det.device_name": "AUTO",
                        "Cls.device_name": "AUTO",
                        "Rec.device_name": "AUTO",

                        "Rec.ocr_version": OCRVersion.PPOCRV5 ,
                    })
                    logger.info("[OCR] Backend: OPENVINO (Intel CPU)")
                    return self._reader_cache
                except Exception as e:
                    print(e)

        # --- Others (ONNX Runtime) ---
        try:
            self._reader_cache = RapidOCR(params={
                "Global.use_cls": False,
                "Rec.ocr_version": OCRVersion.PPOCRV5 ,
                })
            #logger.info("[OCRText] Loaded Engine: ONNX Runtime")
            # logger.info("[OCR] Backend: ONNX Runtime (CPU)")
            return self._reader_cache
        except Exception as e:
            logger.exception(f"[OCRText] ONNX Runtime backend failed to load: {e}")
            raise RuntimeError("All RapidOCR backends failed to initialize.")



    def run_ocr(self, img_path: str, min_conf=0.9, save_box_info=False, save_conf_info=False):

        # ---------------- Profiler Initialization ----------------
        process = psutil.Process(os.getpid())
        cpu_count = psutil.cpu_count(logical=True) 
        
        # Prime CPU calculation & get baseline memory
        process.cpu_percent(interval=None)
        start_cpu_time = process.cpu_times()
        ram_start_mb = process.memory_info().rss / (1024 * 1024)

        t_init = time.perf_counter()    

        img = cv2.imread(img_path, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to load image")

        # Crop top 30% 
        # h, w = img.shape[:2]
        # crop_height = int(h * 0.3)
        # img = img[0:crop_height, 0:w]

        # Exclude top 10%, crop next 30%
        h, w = img.shape[:2]
        start_height = int(h * 0.1)
        end_height = int(h * 0.4)
        img = img[start_height:end_height, 0:w]

        reader = self.get_cached_reader()

        try:
            output = reader(img)
        except Exception:
            raise

        ts = time.strftime("%Y-%m-%d_%H-%M-%S")

        # ---------------- Profiling Metrics ----------------
        elapsed_time = time.perf_counter() - t_init
        ram_end_mb = process.memory_info().rss / (1024 * 1024)
        ram_increase_mb = max(0.0, ram_end_mb - ram_start_mb)

        # Calculate total multi-threaded CPU usage across all cores during the run
        end_cpu_time = process.cpu_times()
        total_cpu_seconds = (end_cpu_time.user - start_cpu_time.user) + (end_cpu_time.system - start_cpu_time.system)
        cpu_usage_pct = ((total_cpu_seconds / elapsed_time * 100) / cpu_count) if elapsed_time > 0 else 0.0

        # GPU usage formatting
        gpu_usage = "N/A"

        # Print / Log formatted metrics
        metrics_summary = (
            f"\n--- Resource Usage ---"
            f"\nRuntime      : {elapsed_time:.2f} s"
            f"\nCPU Usage    : {cpu_usage_pct:.1f}%"
            f"\nRAM Usage    : {ram_end_mb:.1f} MB"
            f"\nRAM Increase : {ram_increase_mb:.1f} MB"
            f"\nGPU Usage    : {gpu_usage}"
            f"\n----------------------"
        )

        if STAGING == 1:
            setup_logging("sd-ocr-activity", log_file=True)
            print(metrics_summary)
            logger.info(metrics_summary)

        #No text detected 
        if not output:
            logger.info("[OCRText] No text detected")
            return {
                "timestamp": ts,
                "data": [{"text": "No text detected"}]
            }

        #text detected 
        json_output = {
            "timestamp": ts,
            "data": []
        }

        for box, text, conf in zip(output.boxes, output.txts, output.scores):
            if conf < min_conf:
                continue

            json_data = {"text": text}

            if save_conf_info:
                json_data["confidence"] = float(conf)

            if save_box_info:
                json_data["box"] = [[float(p[0]), float(p[1])] for p in box]

            json_output["data"].append(json_data)

        #If after filtering, no text is left.
        if not json_output["data"]:
            return {
                "timestamp": ts,
                "data": [{"text": "No text detected"}]
            }

        return json_output


# if __name__ == "__main__":
#     ocr = ActiveWindowOCRText(warmup=True)
#     ocr.run_ocr(
#     img_path=""
# )
