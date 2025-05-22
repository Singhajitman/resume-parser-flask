import os
import re
from flask import Flask, request, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from docx import Document
import PyPDF2
from unidecode import unidecode
import spacy

app = Flask(__name__)
app.secret_key = 'your-secret-key'  # Required for flashing messages
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg2://rpadmin:Wissen123@myrpappserver.postgres.database.azure.com:5432/postgres?sslmode=require'  
db = SQLAlchemy(app)

nlp = spacy.load("en_core_web_sm")

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

class Resume(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(50))
    skills = db.Column(db.Text)

with app.app_context():
    try:
        db.create_all()
        print("✅ Connected to the database and tables created.")
    except Exception as e:
        print("❌ Error connecting to the database:", e)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ['pdf', 'docx']

def extract_text_from_resume(file_path):
    if file_path.endswith('.pdf'):
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ''
            for page in reader.pages:
                text += page.extract_text() or ''
            return unidecode(text)
    elif file_path.endswith('.docx'):
        doc = Document(file_path)
        return unidecode('\n'.join([para.text for para in doc.paragraphs]))
    return ''

def extract_name(text):
    lines = text.strip().split('\n')
    for line in lines[:5]:
        doc = nlp(line)
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                return ent.text
    return 'Name not found'

def extract_email(text):
    match = re.search(r'\b[\w.-]+?@\w+?\.\w+?\b', text)
    return match.group() if match else 'Email not found'

def extract_phone(text):
    match = re.search(r'(\+?\d{1,3})?[\s-]?(\d{10})', text)
    return match.group() if match else 'Phone not found'

def extract_skills(text):
    # Load a simple skill set from a list (you can make this more advanced)
    common_skills = set(['python', 'java', 'sql', 'excel', 'flask', 'machine learning', 'ai', 'html', 'css', 'javascript', 'c++', 'c#', 'react', 'django'])
    extracted = set()
    words = set(re.findall(r'\b\w+\b', text.lower()))
    for skill in common_skills:
        if skill.lower() in words:
            extracted.add(skill)
    return ', '.join(sorted(extracted)) if extracted else 'Skills not found'

@app.route('/')
def home():
    return redirect(url_for('upload_resume'))

@app.route('/upload', methods=['GET', 'POST'])
def upload_resume():
    message = None
    if request.method == 'POST':
        file = request.files['resume']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            extracted_text = extract_text_from_resume(file_path)
            name = extract_name(extracted_text)
            email = extract_email(extracted_text)
            phone = extract_phone(extracted_text)
            skills = extract_skills(extracted_text)

            # Prevent duplicate by name/email combo (basic example)
            existing = Resume.query.filter_by(name=name, email=email).first()
            if existing:
                message = f"Candidate '{name}' already exists."
            else:
                new_resume = Resume(name=name, email=email, phone=phone, skills=skills)
                db.session.add(new_resume)
                db.session.commit()
                message = f"Resume for {name} ({email}) saved successfully."
        else:
            message = "Invalid file format. Please upload PDF or DOCX."
    return render_template('upload.html', message=message)

@app.route('/search', methods=['GET', 'POST'])
def search_resume():
    results = []
    if request.method == 'POST':
        keyword = request.form['keyword'].lower()
        results = Resume.query.filter(
            (Resume.name.ilike(f'%{keyword}%')) |
            (Resume.email.ilike(f'%{keyword}%')) |
            (Resume.phone.ilike(f'%{keyword}%')) |
            (Resume.skills.ilike(f'%{keyword}%'))
        ).all()
    return render_template('search.html', results=results)

@app.route('/edit/<int:resume_id>', methods=['GET', 'POST'])
def edit_resume(resume_id):
    resume = Resume.query.get_or_404(resume_id)
    if request.method == 'POST':
        resume.name = request.form['name']
        resume.email = request.form['email']
        resume.phone = request.form['phone']
        resume.skills = request.form['skills']
        db.session.commit()
        return redirect(url_for('search_resume'))
    return render_template('edit.html', resume=resume)

@app.route('/delete/<int:resume_id>', methods=['POST'])
def delete_resume(resume_id):
    resume = Resume.query.get_or_404(resume_id)
    db.session.delete(resume)
    db.session.commit()
    flash(f"Candidate '{resume.name}' deleted successfully.")
    return redirect(url_for('search_resume'))

if __name__ == '__main__':
    app.run(debug=True)
