# 🏥 Smart Health Assistant

An AI-powered, bilingual healthcare web application designed to provide **symptom assessment, emergency detection, appointment booking, and healthcare discovery** in a safe and user-friendly manner.

---

## 🚀 Features

### 🧠 AI Chat & Symptom Assessment
- Real-time chat-based health assistant  
- NLP-based symptom extraction using spaCy  
- AI-generated health guidance using Google Gemini API  
- Triage severity scoring (0–10 scale)  
- Recommendations: Home care / Doctor visit / Emergency  

### 🚨 Emergency Detection
- Identifies critical symptoms (e.g., chest pain, stroke signs)  
- Displays emergency alerts instantly  
- One-click **108 ambulance call support**  
- Nearby hospital suggestions  

### 📅 Appointment Booking System
- Doctor search by specialization & rating  
- Available time-slot selection  
- Multi-step booking form  
- Unique appointment confirmation code  
- Email notifications to patient & doctor  

### 📍 Healthcare Locator
- Find nearby clinics and hospitals  
- Location-based filtering  
- Displays address, contact, and directions  

### 💡 Health Tips & Feedback
- Category-based bilingual health tips  
- User feedback collection system  

### 🎤 Voice Interaction
- Voice input (Speech Recognition)  
- Supports English & Hindi  

---

## 🏗️ System Architecture

- **Frontend:** React 18, TypeScript, Tailwind CSS  
- **Backend:** FastAPI (Python)  
- **Database:** SQLite (SQLAlchemy ORM)  
- **AI/NLP:** spaCy, Google Gemini API  
- **Voice:** Web Speech API  

---

## ⚙️ Installation & Setup

### 🔹 Backend Setup

cd backend
pip install -r requirements.txt
python main.py

Backend will run at:
http://localhost:8000

Swagger Docs:
http://localhost:8000/docs

---

## 🔹 Frontend Setup

cd frontend
npm install
npm start

---

### Author

- Nensi Chavda 
- Computer Engineering Student
- LinkedIn: https://www.linkedin.com/in/nensi-chavda-b7baa3253/
