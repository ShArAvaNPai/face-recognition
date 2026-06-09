import os
import cv2
import numpy as np
from deepface import DeepFace


def load_known_faces(known_faces_dir, model_name='VGG-Face', detector_backend='opencv'):
    known_embeddings = []
    known_names = []

    for filename in os.listdir(known_faces_dir):
        filepath = os.path.join(known_faces_dir, filename)
        if not os.path.isfile(filepath):
            continue

        try:
            embedding = DeepFace.represent(filepath, model_name=model_name, detector_backend=detector_backend, enforce_detection=True)
            # DeepFace.represent may return a nested list or a flat vector depending on backend
            if isinstance(embedding, list) and len(embedding) > 0:
                emb_vec = np.array(embedding[0])
            else:
                emb_vec = np.array(embedding)

            known_embeddings.append(emb_vec)
            known_names.append(os.path.splitext(filename)[0])
        except Exception as e:
            print(f"Warning: couldn't process {filepath}: {e}")

    return known_embeddings, known_names


def cosine_distance(a, b):
    a = np.asarray(a)
    b = np.asarray(b)
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 1.0
    return 1.0 - np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def main():
    known_faces_dir = "known_faces"
    os.makedirs(known_faces_dir, exist_ok=True)

    known_embeddings, known_names = load_known_faces(known_faces_dir)

    if len(known_embeddings) == 0:
        print(f"No known faces found in '{known_faces_dir}'.")
        print("Add face images to the folder and rerun.")
        return

    video_capture = cv2.VideoCapture(0)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    print("Press 'q' to quit.")

    # cosine distance threshold (lower = more strict). Tweak as needed per model.
    threshold = 0.4

    while True:
        ret, frame = video_capture.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

        for (x, y, w, h) in faces:
            face_img = frame[y:y+h, x:x+w]
            rgb_face = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)

            name = "Unknown"
            try:
                embedding = DeepFace.represent(rgb_face, model_name='VGG-Face', detector_backend='opencv', enforce_detection=False)
                if isinstance(embedding, list) and len(embedding) > 0:
                    emb_vec = np.array(embedding[0])
                else:
                    emb_vec = np.array(embedding)

                if len(known_embeddings) > 0:
                    distances = [cosine_distance(emb_vec, ke) for ke in known_embeddings]
                    best_idx = int(np.argmin(distances))
                    if distances[best_idx] <= threshold:
                        name = known_names[best_idx]
            except Exception:
                # If embedding fails, leave as Unknown
                pass

            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.rectangle(frame, (x, y + h - 20), (x + w, y + h), (0, 255, 0), cv2.FILLED)
            cv2.putText(frame, name, (x + 5, y + h - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

        cv2.imshow('Face Recognition (DeepFace)', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    video_capture.release()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
