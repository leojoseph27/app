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
model = genai.GenerativeModel("gemini-2.0-flash")

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
        print(f"Attempting to extract text from {file_path} with extension {ext}")  # Debug log
        if ext == 'pdf':
            with pdfplumber.open(file_path) as pdf:
                text = ''
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + '\n'
                print(f"Successfully extracted {len(text)} characters from PDF")  # Debug log
                return text
        elif ext == 'docx':
            doc = docx.Document(file_path)
            text = '\n'.join([para.text for para in doc.paragraphs])
            print(f"Successfully extracted {len(text)} characters from DOCX")  # Debug log
            return text
        elif ext == 'txt':
            with open(file_path, 'r', encoding='utf-8') as file:
                text = file.read()
                print(f"Successfully extracted {len(text)} characters from TXT")  # Debug log
                return text
    except Exception as e:
        print(f"Error extracting text from {file_path}: {str(e)}")  # Debug log
        return None

def generate_mcqs(input_data, num_questions, difficulty="easy", is_file=False):
    difficulty_prompts = {
        "easy": "Generate simple, straightforward questions suitable for beginners. Focus on basic concepts and definitions.",
        "intermediate": "Generate moderately challenging questions that test understanding and application of concepts.",
        "hard": "Generate complex questions that test deep understanding, analysis, and synthesis of concepts."
    }
    
    if is_file:
        content = input_data['content']
        prompt = f"""
        Generate {num_questions} multiple-choice questions from the following text content:
        {content}
        
        {difficulty_prompts[difficulty]}
        
        Additional instructions for file-based questions:
        1. Use ONLY the information from the provided text content
        2. Focus on key concepts and important details from the text
        3. Include questions about specific facts, figures, or data mentioned in the text
        4. Create questions that test comprehension of the main ideas and supporting details
        5. Ensure questions are directly related to the content in the file
        6. Include at least one question about any tables, lists, or structured data if present
        7. Cover a broad range of topics from the text
        8. Ensure questions are well-distributed across different sections of the content
        
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
    else:  # topic_only scenario
        prompt = f"""
        Generate {num_questions} multiple-choice questions from the following topic:
        {input_data['content']}
        
        {difficulty_prompts[difficulty]}
        
        Additional instructions for topic-based questions:
        1. Create questions that cover the main aspects of the topic
        2. Include both theoretical and practical questions
        3. Ensure questions are relevant to the given topic
        4. Create a good mix of definition, concept, and application questions
        5. Cover fundamental concepts and advanced aspects of the topic
        6. Include questions about key terminology and important principles
        7. Ensure questions test both understanding and application
        8. Create questions that help build a comprehensive understanding of the topic
        
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
    # Clear all session data when accessing the home page
    session.clear()
    return render_template('index.html')

@app.route('/home')
def home():
    # Clear all session data and redirect to index
    session.clear()
    return redirect(url_for('index'))

@app.route('/generate', methods=['POST'])
def generate():
    file = request.files.get('file')
    topic = request.form.get('topic')
    difficulty = request.form.get('difficulty', 'easy')

    print(f"File received: {file}")  # Debug log
    print(f"Topic received: {topic}")  # Debug log
    print(f"Request files: {request.files}")  # Debug log
    print(f"Request form: {request.form}")  # Debug log

    try:
        num_questions = int(request.form['num_questions'])
        print(f"Generating {num_questions} questions")  # Debug log
    except ValueError:
        return "Please enter a valid number of questions."

    # Scenario 1: Topic input only
    if not file and topic:
        print("Processing topic input only")  # Debug log
        input_data = {
            'content': topic,
            'is_file': False
        }
    
    # Scenario 2: File upload only
    elif file and allowed_file(file.filename):
        print("Processing file upload only")  # Debug log
        try:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            print(f"Saving file to: {file_path}")  # Debug log
            
            # Ensure the upload folder exists
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            
            # Save the file
            file.save(file_path)
            print(f"File saved successfully")  # Debug log
            
            # Extract text from the file
            file_content = extract_text_from_file(file_path)
            if not file_content:
                print("Failed to extract text from file")  # Debug log
                return "Error: Could not extract text from the uploaded file. Please try again."
            
            print(f"Extracted text length: {len(file_content)}")  # Debug log
            
            input_data = {
                'content': file_content,
                'is_file': True
            }
        except Exception as e:
            print(f"Error processing file: {str(e)}")  # Debug log
            return f"Error processing file: {str(e)}"
    
    else:
        print(f"Invalid input: file={file}, topic={topic}")  # Debug log
        return "Please provide either a file or a topic."

    # Generate MCQs based on the input data
    mcqs = generate_mcqs(input_data, num_questions, difficulty)
    if not mcqs:
        print("Failed to generate MCQs")  # Debug log
        return "Failed to generate MCQs. Please try again."

    print(f"Generated MCQs: {mcqs[:200]}...")  # Debug log (first 200 chars)

    # Process the generated MCQs
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

    print(f"Processed {len(questions)} questions")  # Debug log

    if not questions:
        print("No valid questions generated")  # Debug log
        return "No valid questions could be generated. Please try again."

    # Store the necessary data in session
    session['questions'] = questions
    
    if input_data['is_file']:
        session['original_input_text'] = input_data['content']
    
    return redirect(url_for('quiz'))

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

            # Generate explanation for the question
            prompt = f"""
            Explain why '{q['correct_answer']}' is the correct answer to:
            '{q['question']}'
            
            Provide a clear, concise explanation in 2-3 sentences.
            """
            try:
                response = model.generate_content(prompt)
                explanation = response.text
            except Exception as e:
                explanation = "Explanation not available."

            user_answers.append({
                'question': q['question'],
                'options': q['options'],
                'correct_answer': q['correct_answer'],
                'user_answer': user_answer,
                'is_correct': correct,
                'explanation': explanation
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
                         chr=chr,
                         enumerate=enumerate)  # Add enumerate function to template context

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