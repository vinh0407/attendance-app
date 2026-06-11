import cv2
import numpy as np
import pickle
import os
from insightface.app import FaceAnalysis

# Khởi tạo model
print('Đang tải model...')
app = FaceAnalysis(name='buffalo_s', providers=['CUDAExecutionProvider'])
app.prepare(ctx_id=0, det_size=(160, 160))  # Giảm det_size cho ảnh nhỏ

# Đọc ảnh và lấy embedding
embeddings = []
folder = 'viet_temp'
for i in range(1, 6):
    img_path = os.path.join(folder, f'{i}.jpg')
    img = cv2.imread(img_path)
    if img is None:
        print(f'Khong doc duoc: {img_path}')
        continue
    
    # Resize ảnh lên để AI detect được
    img = cv2.resize(img, (400, 400))
    print(f'Anh {i}: {img.shape}')
    
    faces = app.get(img)
    if len(faces) > 0:
        embeddings.append(faces[0].embedding)
        print(f'OK - Anh {i}: Tim thay {len(faces)} khuon mat')
    else:
        print(f'LOI - Anh {i}: Khong tim thay khuon mat')

# Lưu vào database
if embeddings:
    db_file = 'face_database.pkl'
    if os.path.exists(db_file):
        with open(db_file, 'rb') as f:
            database = pickle.load(f)
    else:
        database = {}
    
    database['Viet'] = embeddings
    
    with open(db_file, 'wb') as f:
        pickle.dump(database, f)
    
    print(f'\nDang ky thanh cong Viet voi {len(embeddings)} anh!')
    print(f'Database hien co: {list(database.keys())}')
else:
    print('Khong co anh nao hop le!')
