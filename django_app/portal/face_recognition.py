"""
Face Recognition Module for Django Attendance System
Sử dụng InsightFace với model buffalo_l
"""

import cv2
import numpy as np
import pickle
import os
from insightface.app import FaceAnalysis
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

# Cấu hình
MODEL_NAME = 'buffalo_l'  # Hoặc 'buffalo_s' nếu muốn nhẹ hơn
THRESHOLD = 0.55  # Ngưỡng nhận diện

# Sử dụng database từ project gốc (đã có Thang và Viet)
# Có thể thay đổi thành đường dẫn riêng cho Django app
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DATABASE_FILE = os.path.join(BASE_DIR, 'face_database.pkl')
MY_FACES_DIR = os.path.join(BASE_DIR, 'my_faces')  # Thư mục lưu ảnh khuôn mặt

# Singleton pattern cho FaceAnalysis app
_face_app = None

def get_face_app():
    """Lấy instance FaceAnalysis (singleton để tránh load model nhiều lần)"""
    global _face_app
    if _face_app is None:
        print("Đang tải model InsightFace...")
        try:
            _face_app = FaceAnalysis(name=MODEL_NAME, providers=['CUDAExecutionProvider'])
        except:
            print("Không tìm thấy GPU, sử dụng CPU...")
            _face_app = FaceAnalysis(name=MODEL_NAME, providers=['CPUExecutionProvider'])
        _face_app.prepare(ctx_id=0, det_size=(640, 640))
        print("Tải model thành công!")
    return _face_app


def load_database():
    """Đọc database embeddings từ file"""
    if os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, 'rb') as f:
            return pickle.load(f)
    return {}


def save_database(database):
    """Lưu database embeddings vào file"""
    with open(DATABASE_FILE, 'wb') as f:
        pickle.dump(database, f)


def register_face(name, image):
    """
    Đăng ký khuôn mặt mới từ ảnh
    Args:
        name: Tên người
        image: numpy array (BGR image từ OpenCV)
    Returns:
        (success: bool, message: str)
    """
    app = get_face_app()
    faces = app.get(image)
    
    if len(faces) == 0:
        return False, "Không tìm thấy khuôn mặt trong ảnh"
    
    if len(faces) > 1:
        # Chọn khuôn mặt lớn nhất
        faces = sorted(faces, key=lambda x: (x.bbox[2]-x.bbox[0]) * (x.bbox[3]-x.bbox[1]), reverse=True)
    
    embedding = faces[0].embedding
    
    # Lưu ảnh vào thư mục my_faces/{tên_người}
    person_dir = os.path.join(MY_FACES_DIR, name)
    os.makedirs(person_dir, exist_ok=True)
    
    # Đếm số ảnh hiện có để đặt tên file
    existing_images = [f for f in os.listdir(person_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
    img_index = len(existing_images) + 1
    img_path = os.path.join(person_dir, f"{name}_{img_index}.jpg")
    cv2.imwrite(img_path, image)
    
    # Lưu vào database
    database = load_database()
    if name in database:
        database[name].append(embedding)
    else:
        database[name] = [embedding]
    
    save_database(database)
    return True, f"Đã đăng ký thành công cho {name}"


def recognize_face(image):
    """
    Nhận diện khuôn mặt trong ảnh
    Args:
        image: numpy array (BGR image từ OpenCV)
    Returns:
        list of dict: [{'name': str, 'confidence': float, 'bbox': [x1,y1,x2,y2]}]
    """
    app = get_face_app()
    database = load_database()
    
    if not database:
        return []
    
    faces = app.get(image)
    results = []
    
    for face in faces:
        current_embedding = face.embedding
        best_name = "Unknown"
        best_score = 0.0
        
        for db_name, embeddings_list in database.items():
            for db_embedding in embeddings_list:
                sim = np.dot(current_embedding, db_embedding) / (
                    np.linalg.norm(current_embedding) * np.linalg.norm(db_embedding)
                )
                if sim > best_score:
                    best_score = sim
                    if sim > THRESHOLD:
                        best_name = db_name
        
        bbox = face.bbox.astype(int).tolist()
        results.append({
            'name': best_name,
            'confidence': float(best_score * 100),
            'bbox': bbox
        })
    
    return results


def recognize_frame(frame, scale=0.5):
    """
    Nhận diện khuôn mặt trong frame video (tối ưu cho realtime)
    Args:
        frame: numpy array (BGR image từ OpenCV)
        scale: tỉ lệ resize để tăng tốc (0.5 = 50%)
    Returns:
        list of dict với bbox đã scale về kích thước gốc
    """
    # Resize để xử lý nhanh hơn
    small_frame = cv2.resize(frame, (0, 0), fx=scale, fy=scale)
    
    app = get_face_app()
    database = load_database()
    
    if not database:
        return []
    
    faces = app.get(small_frame)
    results = []
    
    for face in faces:
        current_embedding = face.embedding
        best_name = "Unknown"
        best_score = 0.0
        
        for db_name, embeddings_list in database.items():
            for db_embedding in embeddings_list:
                sim = np.dot(current_embedding, db_embedding) / (
                    np.linalg.norm(current_embedding) * np.linalg.norm(db_embedding)
                )
                if sim > best_score:
                    best_score = sim
                    if sim > THRESHOLD:
                        best_name = db_name
        
        # Scale bbox về kích thước gốc
        bbox = (face.bbox / scale).astype(int).tolist()
        results.append({
            'name': best_name,
            'confidence': float(best_score * 100),
            'bbox': bbox
        })
    
    return results


def draw_results(frame, results):
    """
    Vẽ kết quả nhận diện lên frame
    Args:
        frame: numpy array (BGR image)
        results: list từ recognize_frame()
    Returns:
        frame với annotations
    """
    for result in results:
        x1, y1, x2, y2 = result['bbox']
        name = result['name']
        conf = result['confidence']
        
        # Màu: xanh nếu nhận diện được, đỏ nếu Unknown
        color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
        
        # Vẽ khung
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        
        # Vẽ label
        label = f"{name} ({conf:.0f}%)"
        (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(frame, (x1, y1 - 25), (x1 + w, y1), color, -1)
        cv2.putText(frame, label, (x1, y1 - 5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    return frame


# Hàm ghi nhận điểm danh vào Django database
def record_attendance_to_db(name, confidence, session_id=None):
    """
    Ghi nhận điểm danh vào database Django
    Args:
        name: Tên sinh viên
        confidence: Độ tin cậy
        session_id: ID buổi điểm danh (optional)
    """
    try:
        # Import Django models
        import django
        import os
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_system.settings')
        if not django.apps.apps.ready:
            django.setup()
        
        from django.utils import timezone
        from portal.models import Student, AttendanceRecord, AttendanceSession
        
        student = Student.objects.filter(full_name=name).first()
        if not student:
            print(f"Không tìm thấy sinh viên: {name}")
            return False
        
        current_time = timezone.now()
        
        if session_id:
            # Điểm danh theo buổi
            try:
                session = AttendanceSession.objects.get(id=session_id)
                record, created = AttendanceRecord.objects.get_or_create(
                    session=session,
                    student=student,
                    date=current_time.date(),
                    defaults={
                        'time_in': current_time.time(),
                        'status': 'present',
                        'confidence': confidence,
                    }
                )
                if created:
                    print(f"✅ {name} - Điểm danh buổi #{session_id} lúc {current_time.strftime('%H:%M:%S')}")
                return True
            except AttendanceSession.DoesNotExist:
                print(f"Không tìm thấy buổi điểm danh: {session_id}")
                return False
        else:
            # Điểm danh chung (không theo buổi)
            record, created = AttendanceRecord.objects.get_or_create(
                student=student,
                date=current_time.date(),
                session=None,
                defaults={
                    'time_in': current_time.time(),
                    'status': 'present',
                    'confidence': confidence,
                }
            )
            if created:
                print(f"✅ {name} - Điểm danh lúc {current_time.strftime('%H:%M:%S')}")
            return True
            
    except Exception as e:
        print(f"Lỗi ghi nhận điểm danh: {e}")
        return False


class VideoCamera:
    """Class để stream video từ camera với hỗ trợ điểm danh theo buổi"""
    
    def __init__(self, camera_id=0, session_id=None):
        self.video = cv2.VideoCapture(camera_id)
        self.video.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.session_id = session_id
        self.recognized_names = set()  # Lưu tên đã điểm danh để tránh trùng
    
    def __del__(self):
        if self.video.isOpened():
            self.video.release()
    
    def get_frame(self, recognize=True):
        """
        Lấy frame từ camera
        Args:
            recognize: có nhận diện khuôn mặt không
        Returns:
            JPEG encoded bytes
        """
        ret, frame = self.video.read()
        if not ret:
            return None
        
        if recognize:
            results = recognize_frame(frame)
            
            # Tự động ghi nhận điểm danh
            for result in results:
                name = result['name']
                conf = result['confidence']
                
                if name != "Unknown" and name not in self.recognized_names:
                    # Ghi nhận điểm danh
                    success = record_attendance_to_db(name, conf / 100.0, self.session_id)
                    if success:
                        self.recognized_names.add(name)
            
            frame = draw_results(frame, results)
        
        ret, jpeg = cv2.imencode('.jpg', frame)
        return jpeg.tobytes()
    
    def get_frame_with_results(self):
        """
        Lấy frame và kết quả nhận diện
        Returns:
            (JPEG bytes, results list)
        """
        ret, frame = self.video.read()
        if not ret:
            return None, []
        
        results = recognize_frame(frame)
        annotated_frame = draw_results(frame.copy(), results)
        
        ret, jpeg = cv2.imencode('.jpg', annotated_frame)
        return jpeg.tobytes(), results
