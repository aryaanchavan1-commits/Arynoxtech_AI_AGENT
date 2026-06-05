# MIT License
#
# Copyright (c) 2026 Aryan Chavan
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""ArynoxTech AI Agent - Camera Tool
====================================
Complete camera/vision tool:
- Capture photos, record video
- Object detection (90 classes via MobileNet-SSD)
- Face detection & recognition with saved identities
- Human detection - detect, recognize, learn new people
- Object identification - "what is this?" with AI explanation
- Cross-platform (works on Windows/macOS/Linux)
"""

import asyncio
import time
import os
import json
import pickle
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from tools.base_tool import BaseTool, ToolResult
from config.settings import TOOL_CONFIG


COCO_CLASSES = [
    "background", "person", "bicycle", "car", "motorcycle", "airplane", "bus",
    "train", "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag",
    "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana",
    "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza",
    "donut", "cake", "chair", "couch", "potted plant", "bed", "dining table",
    "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone",
    "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock",
    "vase", "scissors", "teddy bear", "hair drier", "toothbrush",
]

MOBILENET_URL = "https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/deploy.prototxt"
CAFFEMODEL_URL = "https://github.com/chuanqi305/MobileNet-SSD/raw/master/mobilenet_iter_73000.caffemodel"


class CameraTool(BaseTool):
    name: str = "camera_tool"
    description: str = (
        "Webcam & vision: capture photos, record video, detect objects, "
        "recognize faces & known people, identify objects ('what is this?'), "
        "and learn new people."
    )
    version: str = "1.0.0"

    def __init__(self) -> None:
        super().__init__()
        cfg = TOOL_CONFIG.get("camera", {})
        self._output_dir = Path(cfg.get("output_dir", "assets/captures"))
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._known_faces_dir = Path("data/known_faces")
        self._known_faces_dir.mkdir(parents=True, exist_ok=True)

        self._model_dir = Path("models/object_detection")
        self._model_dir.mkdir(parents=True, exist_ok=True)

        self._cv2 = None
        self._net = None
        self._face_recognizer = None
        self._llm = None

    @property
    def cv2(self):
        if self._cv2 is None:
            import cv2
            self._cv2 = cv2
        return self._cv2

    @property
    def llm(self):
        if self._llm is None:
            try:
                from utils.llm_factory import get_llm_client
                self._llm = get_llm_client()
            except Exception:
                self._llm = None
        return self._llm

    @property
    def detection_net(self):
        if self._net is not None:
            return self._net
        prototxt = self._model_dir / "deploy.prototxt"
        caffemodel = self._model_dir / "mobilenet_iter_73000.caffemodel"

        if not prototxt.exists():
            self.logger.info("Downloading MobileNet-SSD prototxt...")
            try:
                urllib.request.urlretrieve(MOBILENET_URL, str(prototxt))
            except Exception as e:
                self.logger.warning(f"Cannot download prototxt: {e}")
                return None
        if not caffemodel.exists():
            self.logger.info("Downloading MobileNet-SSD model (~23MB)...")
            try:
                urllib.request.urlretrieve(CAFFEMODEL_URL, str(caffemodel))
            except Exception as e:
                self.logger.warning(f"Cannot download caffemodel: {e}")
                return None

        try:
            self._net = self.cv2.dnn.readNetFromCaffe(str(prototxt), str(caffemodel))
            self.logger.info("MobileNet-SSD loaded for object detection")
        except Exception as e:
            self.logger.warning(f"Failed to load detection model: {e}")
            return None
        return self._net

    def _open_camera(self, camera_id: int = 0):
        cap = self.cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open camera {camera_id}. Is it connected?")
        return cap

    def _get_face_cascade(self):
        return self.cv2.CascadeClassifier(
            self.cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

    # ── Face Recognition DB ─────────────────────────────────────────────────

    def _get_known_people(self) -> Dict[str, List[str]]:
        people = {}
        for person_dir in self._known_faces_dir.iterdir():
            if person_dir.is_dir():
                images = [str(p) for p in person_dir.glob("*.jpg")]
                if images:
                    people[person_dir.name] = images
        return people

    def _train_face_recognizer(self):
        people = self._get_known_people()
        if not people:
            return None, []
        faces = []
        labels = []
        label_map = {}
        for idx, (name, img_paths) in enumerate(people.items()):
            label_map[idx] = name
            for img_path in img_paths:
                img = self.cv2.imread(img_path, self.cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    faces.append(img)
                    labels.append(idx)
        if not faces:
            return None, []
        recognizer = self.cv2.face.LBPHFaceRecognizer_create()
        recognizer.train(faces, self.cv2_arrays_to_numpy(labels))
        return recognizer, label_map

    def cv2_arrays_to_numpy(self, arr):
        import numpy as np
        return np.array(arr, dtype=np.int32)

    def _predict_face(self, face_gray):
        recognizer, label_map = self._train_face_recognizer()
        if recognizer is None:
            return None, None
        try:
            label_id, confidence = recognizer.predict(face_gray)
            name = label_map.get(label_id, "Unknown")
            return name, confidence
        except:
            return None, None

    # ── Object Detection ────────────────────────────────────────────────────

    def _detect_objects_in_frame(self, frame, confidence_threshold: float = 0.4):
        net = self.detection_net
        if net is None:
            return []
        h, w = frame.shape[:2]
        blob = self.cv2.dnn.blobFromImage(
            self.cv2.resize(frame, (300, 300)), 0.007843, (300, 300), 127.5
        )
        net.setInput(blob)
        detections = net.forward()
        results = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > confidence_threshold:
                class_id = int(detections[0, 0, i, 1])
                label = COCO_CLASSES[class_id] if class_id < len(COCO_CLASSES) else f"class_{class_id}"
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                (x1, y1, x2, y2) = box.astype("int")
                results.append({
                    "label": label,
                    "confidence": round(float(confidence), 3),
                    "bbox": {"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2)},
                })
        return results

    # ── Execute ─────────────────────────────────────────────────────────────

    async def execute(self, **kwargs: Any) -> ToolResult:
        start_time = time.time()
        action = kwargs.get("action", "capture_photo")

        try:
            import numpy as np

            if action == "capture_photo":
                return await self._capture_photo(kwargs, start_time)
            elif action == "record_video":
                return await self._record_video(kwargs, start_time)
            elif action == "detect_faces":
                return await self._detect_faces(kwargs, start_time)
            elif action == "detect_objects":
                return await self._detect_objects(kwargs, start_time)
            elif action == "identify_object":
                return await self._identify_object(kwargs, start_time)
            elif action == "recognize_person":
                return await self._recognize_person(kwargs, start_time)
            elif action == "save_face":
                return await self._save_face(kwargs, start_time)
            elif action == "learn_new_person":
                return await self._learn_new_person(kwargs, start_time)
            elif action == "list_known_people":
                return await self._list_known_people(start_time)
            elif action == "list_cameras":
                return await self._list_cameras(start_time)
            else:
                return ToolResult.failure(
                    f"Unknown action: {action}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
        except ImportError:
            return ToolResult.failure(
                "OpenCV not installed. Install: pip install opencv-python-headless",
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            self.logger.exception(f"Camera tool error: {e}")
            return ToolResult.error_result(
                f"Camera operation failed: {str(e)}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    # ── Capture Photo ──────────────────────────────────────────────────────

    async def _capture_photo(self, kwargs: Dict, start_time: float) -> ToolResult:
        camera_id = int(kwargs.get("camera_id", 0))
        filename = kwargs.get("filename", f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")

        cap = await asyncio.to_thread(self._open_camera, camera_id)
        try:
            await asyncio.sleep(0.5)
            ret, frame = await asyncio.to_thread(cap.read)
            if not ret:
                return ToolResult.failure(
                    "Failed to capture frame",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            filepath = self._output_dir / filename
            await asyncio.to_thread(self.cv2.imwrite, str(filepath), frame)
            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Photo captured: {filename}",
                data={
                    "path": str(filepath.resolve()), "filename": filename,
                    "resolution": f"{frame.shape[1]}x{frame.shape[0]}",
                    "file_size_kb": round(filepath.stat().st_size / 1024, 2) if filepath.exists() else 0,
                },
                execution_time_ms=elapsed,
            )
        finally:
            cap.release()

    # ── Record Video ───────────────────────────────────────────────────────

    async def _record_video(self, kwargs: Dict, start_time: float) -> ToolResult:
        camera_id = int(kwargs.get("camera_id", 0))
        duration = float(kwargs.get("duration", 5))
        fps = int(kwargs.get("fps", 20))
        filename = kwargs.get("filename", f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.avi")

        cap = await asyncio.to_thread(self._open_camera, camera_id)
        try:
            ret, frame = await asyncio.to_thread(cap.read)
            if not ret:
                return ToolResult.failure("Failed to start video capture", execution_time_ms=...)
            fourcc = self.cv2.VideoWriter_fourcc(*"XVID")
            h, w = frame.shape[:2]
            filepath = self._output_dir / filename
            out = self.cv2.VideoWriter(str(filepath), fourcc, fps, (w, h))
            frames_to_capture = int(fps * duration)
            for _ in range(frames_to_capture):
                ret, frame = cap.read()
                if ret:
                    out.write(frame)
                await asyncio.sleep(1 / fps)
            out.release()
            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Video recorded: {filename} ({duration}s)",
                data={"path": str(filepath.resolve()), "filename": filename, "duration_seconds": duration},
                execution_time_ms=elapsed,
            )
        finally:
            cap.release()

    # ── Face Detection ─────────────────────────────────────────────────────

    async def _detect_faces(self, kwargs: Dict, start_time: float) -> ToolResult:
        camera_id = int(kwargs.get("camera_id", 0))
        filename = kwargs.get("filename", f"face_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")

        cap = await asyncio.to_thread(self._open_camera, camera_id)
        try:
            await asyncio.sleep(0.5)
            ret, frame = await asyncio.to_thread(cap.read)
            if not ret:
                return ToolResult.failure("Failed to capture frame", execution_time_ms=...)
            gray = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2GRAY)
            face_cascade = self._get_face_cascade()
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)

            # Also try object detection for person
            detections = self._detect_objects_in_frame(frame)
            people_count = sum(1 for d in detections if d["label"] == "person")

            for (x, y, w, h) in faces:
                self.cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                self.cv2.putText(frame, "Face", (x, y - 10),
                                 self.cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            filepath = self._output_dir / filename
            await asyncio.to_thread(self.cv2.imwrite, str(filepath), frame)

            msg = f"Detected {len(faces)} face(s)"
            if people_count > len(faces):
                msg += f", {people_count} person(s) in frame"

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                msg if len(faces) > 0 else "No faces detected in frame",
                data={
                    "path": str(filepath.resolve()), "filename": filename,
                    "faces_detected": len(faces), "people_detected": people_count,
                    "face_locations": [{"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
                                       for (x, y, w, h) in faces],
                },
                execution_time_ms=elapsed,
            )
        finally:
            cap.release()

    # ── Object Detection (General) ─────────────────────────────────────────

    async def _detect_objects(self, kwargs: Dict, start_time: float) -> ToolResult:
        camera_id = int(kwargs.get("camera_id", 0))
        filename = kwargs.get("filename", f"objects_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
        confidence_threshold = float(kwargs.get("confidence", 0.4))

        cap = await asyncio.to_thread(self._open_camera, camera_id)
        try:
            await asyncio.sleep(0.5)
            ret, frame = await asyncio.to_thread(cap.read)
            if not ret:
                return ToolResult.failure("Failed to capture frame", execution_time_ms=...)

            import numpy as np
            objects = self._detect_objects_in_frame(frame, confidence_threshold)

            for obj in objects:
                b = obj["bbox"]
                self.cv2.rectangle(frame, (b["x1"], b["y1"]), (b["x2"], b["y2"]), (0, 255, 0), 2)
                label = f"{obj['label']}: {obj['confidence']:.2f}"
                self.cv2.putText(frame, label, (b["x1"], b["y1"] - 5),
                                 self.cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            filepath = self._output_dir / filename
            await asyncio.to_thread(self.cv2.imwrite, str(filepath), frame)

            labels = [o["label"] for o in objects]
            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"Detected {len(objects)} object(s): {', '.join(labels)}" if objects
                else "No objects detected",
                data={
                    "path": str(filepath.resolve()), "filename": filename,
                    "objects_detected": len(objects),
                    "objects": objects,
                    "labels": labels,
                },
                execution_time_ms=elapsed,
            )
        finally:
            cap.release()

    # ── Identify Object ("What is this?") ──────────────────────────────────

    async def _identify_object(self, kwargs: Dict, start_time: float) -> ToolResult:
        camera_id = int(kwargs.get("camera_id", 0))
        filename = kwargs.get("filename", f"identify_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")

        cap = await asyncio.to_thread(self._open_camera, camera_id)
        try:
            await asyncio.sleep(0.5)
            ret, frame = await asyncio.to_thread(cap.read)
            if not ret:
                return ToolResult.failure("Failed to capture frame", execution_time_ms=...)

            import numpy as np
            objects = self._detect_objects_in_frame(frame, confidence_threshold=0.35)

            if not objects:
                elapsed = (time.time() - start_time) * 1000
                return ToolResult.success(
                    "No objects detected in frame. Try pointing the camera at something.",
                    data={"objects_found": 0, "identification": None},
                    execution_time_ms=elapsed,
                )

            # Get dominant object (highest confidence)
            dominant = max(objects, key=lambda o: o["confidence"])
            b = dominant["bbox"]
            self.cv2.rectangle(frame, (b["x1"], b["y1"]), (b["x2"], b["y2"]), (0, 255, 0), 2)
            label = f"{dominant['label']}: {dominant['confidence']:.2f}"
            self.cv2.putText(frame, label, (b["x1"], b["y1"] - 5),
                             self.cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            filepath = self._output_dir / filename
            await asyncio.to_thread(self.cv2.imwrite, str(filepath), frame)

            # Ask LLM for detailed info about the detected object
            obj_label = dominant["label"]
            explanation = ""
            try:
                prompt = (
                    f"The camera just detected a '{obj_label}' (confidence: {dominant['confidence']:.2f}). "
                    f"Explain what this object is in a friendly, conversational way. "
                    f"If it's a common object, describe what it's used for. "
                    f"If it's a person/animal, describe that. Keep it under 100 words."
                )
                explanation = await self.llm.generate_async(
                    prompt=prompt, temperature=0.7, max_tokens=200
                )
            except Exception:
                explanation = f"It appears to be a {obj_label}."

            all_labels = [o["label"] for o in objects if o["label"] != obj_label]
            extra = f" Also detected: {', '.join(all_labels[:3])}." if all_labels else ""

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"I see a {obj_label}! {explanation}{extra}",
                data={
                    "path": str(filepath.resolve()), "filename": filename,
                    "objects_found": len(objects),
                    "dominant_object": dominant,
                    "all_objects": objects,
                    "ai_explanation": explanation,
                },
                execution_time_ms=elapsed,
            )
        finally:
            cap.release()

    # ── Recognize Person ───────────────────────────────────────────────────

    async def _recognize_person(self, kwargs: Dict, start_time: float) -> ToolResult:
        camera_id = int(kwargs.get("camera_id", 0))
        filename = kwargs.get("filename", f"recognize_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")

        cap = await asyncio.to_thread(self._open_camera, camera_id)
        try:
            await asyncio.sleep(0.5)
            ret, frame = await asyncio.to_thread(cap.read)
            if not ret:
                return ToolResult.failure("Failed to capture frame", execution_time_ms=...)

            gray = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2GRAY)
            face_cascade = self._get_face_cascade()
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)

            if len(faces) == 0:
                elapsed = (time.time() - start_time) * 1000
                return ToolResult.success(
                    "No faces detected in frame.",
                    data={"faces_detected": 0, "known_people": [], "unknown_count": 0},
                    execution_time_ms=elapsed,
                )

            known_people = []
            unknown_count = 0

            for (x, y, w, h) in faces:
                face_roi = gray[y:y + h, x:x + w]
                face_resized = self.cv2.resize(face_roi, (200, 200))
                name, confidence = self._predict_face(face_resized)

                if name and confidence is not None and confidence < 80:
                    color = (0, 255, 0)
                    label_text = f"{name} ({100 - confidence:.0f}%)"
                    known_people.append({"name": name, "confidence": 100 - confidence})
                else:
                    color = (0, 0, 255)
                    label_text = "Unknown Person"
                    unknown_count += 1

                self.cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                self.cv2.putText(frame, label_text, (x, y - 10),
                                 self.cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            filepath = self._output_dir / filename
            await asyncio.to_thread(self.cv2.imwrite, str(filepath), frame)

            known_names = [p["name"] for p in known_people]
            msg_parts = []
            if known_names:
                msg_parts.append(f"Recognized: {', '.join(known_names)}")
            if unknown_count:
                msg_parts.append(f"{unknown_count} unknown person(s)")
                msg_parts.append("Say 'learn this person' to save their name.")

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                "; ".join(msg_parts) if msg_parts else "No known people recognized",
                data={
                    "path": str(filepath.resolve()), "filename": filename,
                    "faces_detected": len(faces),
                    "known_people": known_people,
                    "unknown_count": unknown_count,
                },
                execution_time_ms=elapsed,
            )
        finally:
            cap.release()

    # ── Save Current Face ──────────────────────────────────────────────────

    async def _save_face(self, kwargs: Dict, start_time: float) -> ToolResult:
        camera_id = int(kwargs.get("camera_id", 0))
        person_name = kwargs.get("name", "").strip()
        if not person_name:
            return ToolResult.success(
                "What is this person's name? Say or type their name to save.",
                data={"action_required": "ask_name"},
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        cap = await asyncio.to_thread(self._open_camera, camera_id)
        try:
            await asyncio.sleep(0.5)
            ret, frame = await asyncio.to_thread(cap.read)
            if not ret:
                return ToolResult.failure("Failed to capture frame", execution_time_ms=...)

            gray = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2GRAY)
            face_cascade = self._get_face_cascade()
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)

            if len(faces) == 0:
                return ToolResult.failure("No face detected to save", execution_time_ms=...)

            person_dir = self._known_faces_dir / person_name.replace(" ", "_")
            person_dir.mkdir(parents=True, exist_ok=True)

            saved_count = 0
            for (x, y, w, h) in faces:
                face_roi = gray[y:y + h, x:x + w]
                face_resized = self.cv2.resize(face_roi, (200, 200))
                face_path = person_dir / f"{person_name}_{int(time.time())}_{saved_count}.jpg"
                self.cv2.imwrite(str(face_path), face_resized)
                saved_count += 1

                self.cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                self.cv2.putText(frame, person_name, (x, y - 10),
                                 self.cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            filepath = self._output_dir / f"learned_{person_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            self.cv2.imwrite(str(filepath), frame)

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                f"I've learned {person_name}! Saved {saved_count} face image(s). "
                f"I'll recognize them next time.",
                data={
                    "person_name": person_name, "images_saved": saved_count,
                    "total_images": len(list(person_dir.glob("*.jpg"))),
                    "face_image_path": str(filepath),
                },
                execution_time_ms=elapsed,
            )
        finally:
            cap.release()

    # ── Learn New Person (detect → ask name → save) ────────────────────────

    async def _learn_new_person(self, kwargs: Dict, start_time: float) -> ToolResult:
        camera_id = int(kwargs.get("camera_id", 0))
        person_name = kwargs.get("name", "").strip()

        if person_name:
            kwargs["name"] = person_name
            return await self._save_face(kwargs, start_time)

        cap = await asyncio.to_thread(self._open_camera, camera_id)
        try:
            await asyncio.sleep(0.5)
            ret, frame = await asyncio.to_thread(cap.read)
            if not ret:
                return ToolResult.failure("Failed to access camera", execution_time_ms=...)

            gray = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2GRAY)
            face_cascade = self._get_face_cascade()
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)

            if len(faces) == 0:
                return ToolResult.failure(
                    "No face detected. Look at the camera and try again.",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            for (x, y, w, h) in faces:
                self.cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            filepath = self._output_dir / f"new_person_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            self.cv2.imwrite(str(filepath), frame)

            elapsed = (time.time() - start_time) * 1000
            return ToolResult.success(
                "I see a new face! Please tell me their name by saying or typing "
                "'save face as [name]' or 'this is [name]'.",
                data={
                    "action_required": "provide_name",
                    "captured_image": str(filepath),
                    "faces_detected": len(faces),
                },
                execution_time_ms=elapsed,
            )
        finally:
            cap.release()

    # ── List Known People ──────────────────────────────────────────────────

    async def _list_known_people(self, start_time: float) -> ToolResult:
        people = self._get_known_people()
        people_list = []
        for name, images in people.items():
            people_list.append({
                "name": name.replace("_", " "),
                "saved_images": len(images),
                "last_image": max(images, key=os.path.getmtime) if images else None,
            })

        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"I know {len(people_list)} person(s): {', '.join(p['name'] for p in people_list)}"
            if people_list else "I don't know anyone yet. Say 'learn this person' to teach me.",
            data={
                "known_people": people_list,
                "total": len(people_list),
            },
            execution_time_ms=elapsed,
        )

    # ── List Cameras ───────────────────────────────────────────────────────

    async def _list_cameras(self, start_time: float) -> ToolResult:
        available = []
        for i in range(5):
            try:
                cap = self.cv2.VideoCapture(i)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret:
                        available.append({
                            "camera_id": i,
                            "resolution": f"{frame.shape[1]}x{frame.shape[0]}",
                        })
                    cap.release()
            except:
                pass
        elapsed = (time.time() - start_time) * 1000
        return ToolResult.success(
            f"Found {len(available)} camera(s)",
            data={"cameras": available, "count": len(available)},
            execution_time_ms=elapsed,
        )
