import os
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, session
import pdfplumber
import docx
from werkzeug.utils import secure_filename
import google.generativeai as genai
from fpdf import FPDF
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure Google API
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment variables")

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['RESULTS_FOLDER'] = 'results/'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'txt', 'docx'}
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your_secret_key')  # Use environment variable with fallback

# Ensure folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text_from_file(file_path):
    ext = file_path.rsplit('.', 1)[1].lower()
    try:
        if ext == 'pdf':
            with pdfplumber.open(file_path) as pdf:
                text = ''.join([page.extract_text() for page in pdf.pages if page.extract_text()])
            return text
        elif ext == 'docx':
            doc = docx.Document(file_path)
            return '\n'.join([para.text for para in doc.paragraphs])
        elif ext == 'txt':
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
    except Exception as e:
        print(f"Error extracting text: {e}")
    return None

def generate_mcqs(input_text, num_questions, difficulty="easy"):
    difficulty_prompts = {
        "easy": "Generate simple, straightforward questions suitable for beginners. Focus on basic concepts and definitions.",
        "intermediate": "Generate moderately challenging questions that test understanding and application of concepts.",
        "hard": "Generate complex questions that test deep understanding, analysis, and synthesis of concepts."
    }
    
    prompt = f"""
    Generate {num_questions} multiple-choice questions from the following text:
    '{input_text}'
    
    {difficulty_prompts[difficulty]}
    
    Format exactly like this for each question:
    ## MCQ
    Question: [question text]
    A) [option A]
    B) [option B]
    C) [option C]
    D) [option D]
    Correct Answer: [letter of correct option]
    
    Ensure each question has exactly 4 options and one correct answer.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating MCQs: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    file = request.files.get('file')
    topic = request.form.get('topic')
    difficulty = request.form.get('difficulty', 'easy')  # Default to easy if not specified

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        input_text = extract_text_from_file(file_path)
    elif topic:
        input_text = topic
    else:
        return "Please provide either a file or a topic."

    try:
        num_questions = int(request.form['num_questions'])
        mcqs = generate_mcqs(input_text, num_questions, difficulty)

        if not mcqs:
            return "Failed to generate MCQs. Try again."

        questions = []
        for mcq in mcqs.split("## MCQ"):
            if not mcq.strip():
                continue
                
            lines = [line.strip() for line in mcq.split('\n') if line.strip()]
            if len(lines) < 6:
                continue

            question = lines[0].replace("Question:", "").strip()
            options = [
                lines[1][3:].strip(),  # A) option
                lines[2][3:].strip(),  # B) option
                lines[3][3:].strip(),  # C) option
                lines[4][3:].strip()   # D) option
            ]
            correct_answer = lines[5].replace("Correct Answer:", "").strip()

            questions.append({
                'question': question,
                'options': options,
                'correct_answer': options[ord(correct_answer.upper()) - 65]  # Convert A,B,C,D to index
            })

        session['questions'] = questions  # Store questions in session
        return redirect(url_for('quiz'))

    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    if 'questions' not in session:
        return redirect(url_for('index'))

    questions = session['questions']

    if request.method == 'POST':
        user_answers = []
        score = 0

        for i, q in enumerate(questions):
            user_answer = request.form.get(f"question_{i}")
            correct = user_answer == q['correct_answer']

            if correct:
                score += 1

            user_answers.append({
                'question': q['question'],
                'options': q['options'],
                'correct_answer': q['correct_answer'],
                'user_answer': user_answer
            })

        session['user_answers'] = user_answers
        create_pdf(user_answers, score, len(questions))
        return redirect(url_for('scoreboard', score=score, total=len(questions)))

    return render_template('quiz.html', questions=questions, enumerate=enumerate)

@app.route('/scoreboard')
def scoreboard():
    score = request.args.get('score', 0, type=int)
    total = request.args.get('total', 0, type=int)
    user_answers = session.get('user_answers', [])
    return render_template('scoreboard.html', 
                         user_answers=user_answers, 
                         score=score, 
                         total=total,
                         chr=chr)  # Pass the chr function to template

@app.route('/get_reasoning', methods=['POST'])
def get_reasoning():
    try:
        data = request.get_json()
        question = data.get('question')
        correct_answer = data.get('correct_answer')
        
        prompt = f"""
        Explain why '{correct_answer}' is the correct answer to:
        '{question}'
        
        Provide a clear, concise explanation in 2-3 sentences.
        """
        
        response = model.generate_content(prompt)
        return jsonify({
            'reasoning': response.text,
            'status': 'success'
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@app.route('/generate_notes', methods=['POST'])
def generate_notes():
    try:
        # Get the original input text from session or request
        input_text = session.get('original_input_text', '')
        questions = session.get('questions', [])
        
        # Prepare questions text
        questions_text = "\n".join([f"Q: {q['question']}\nA: {q['correct_answer']}" for q in questions])
        
        prompt = f"""
        Create comprehensive study notes (minimum 500 words) based on:
        1. Original topic/content: {input_text}
        2. Generated questions: {questions_text}
        
        Format requirements:
        - Organize by topics/subtopics
        - Use clear headings 
        - Present key points in bullet lists
        - Include explanations for important concepts
        - Maintain academic tone but keep it readable
        - Minimum 500 words
        
        Output should be well-structured for effective studying. It should not contain any bold words or symbols
        """
        
        response = model.generate_content(prompt)
        notes_content = response.text
        
        # Create PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        
        # Add title
        pdf.cell(200, 10, txt="Study Notes", ln=1, align='C')
        pdf.ln(10)
        
        # Add content (with basic formatting)
        for line in notes_content.split('\n'):
            if line.strip().endswith(':'):  # Likely a heading
                pdf.set_font('', 'U')  # Underline
                pdf.cell(0, 10, txt=line, ln=1)
                pdf.set_font('', '')  # Regular
            else:
                pdf.multi_cell(0, 10, txt=line)
        
        notes_path = os.path.join(app.config['RESULTS_FOLDER'], 'study_notes.pdf')
        pdf.output(notes_path)
        
        return jsonify({
            'status': 'success',
            'notes_path': 'study_notes.pdf'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

def create_pdf(user_answers, score, total):
    pdf = FPDF()
    pdf.add_page()
    
    # Use Helvetica font with Unicode support
    pdf.set_font("Helvetica", size=12)

    # Add score
    pdf.cell(0, 10, f"Score: {score}/{total}", ln=True)
    pdf.ln(10)

    # Add questions and answers
    for ans in user_answers:
        # Question
        pdf.multi_cell(0, 10, f"Q: {ans['question']}")
        
        # Options
        for i, option in enumerate(ans['options']):
            status = ""
            if option == ans['correct_answer']:
                status = "(Correct Answer)"
            elif option == ans['user_answer']:
                status = "(Your Answer)"
            pdf.multi_cell(0, 10, f"{chr(65+i)}) {option} {status}")
        
        pdf.ln(10)

    pdf_path = os.path.join(app.config['RESULTS_FOLDER'], 'results.pdf')
    pdf.output(pdf_path)
    return pdf_path

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['RESULTS_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return "File not found"

if __name__ == "__main__":
    app.run(debug=True)