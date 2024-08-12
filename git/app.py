import os
import io
import fitz  # PyMuPDF
from flask_pymongo import PyMongo
from flask import Flask, render_template
import docx2txt
import spacy
from bson import ObjectId
from flask import Flask, request, render_template, redirect, url_for
from werkzeug.utils import secure_filename

#from mediawiki import MediaWiki
#from MediaWiki import get_search_results
import re
import requests
import torch
app = Flask(__name__, template_folder=r'./templates')

app.secret_key = 'Resumescreening'

# MongoDB client setup
app.config['MONGO_URI'] = 'mongodb+srv://admin:admin@cluster0.na6om9v.mongodb.net/Project0'
mongo = PyMongo(app)

resumeFetchedData = mongo.db.resumeFetchedData
JOBS = mongo.db.JOBS
users = mongo.db.IRS_USERS  # Collection for user management

# File upload paths
UPLOAD_FOLDER_RESUME = 'static/uploaded_resumes'
UPLOAD_FOLDER_JOB = 'static/job_description'
app.config['UPLOAD_FOLDER_RESUME'] = UPLOAD_FOLDER_RESUME
app.config['UPLOAD_FOLDER_JOB'] = UPLOAD_FOLDER_JOB

# Load models
print("Loading Resume Parser model...")
resume_model = spacy.load(r"C:/Users/Mansha/Desktop/test/asstes/ResumeModel/ResumeModel/output/model-best")
print("Resume Parser model loaded")
print("Loading JD Parser model...")
jd_model = spacy.load(r"C:/Users/Mansha/Desktop/test/asstes/JdModel/JdModel/output/model-best")
print("JD Parser model loaded")

class ResumeModel:
    def __init__(self, model):
        self.nlp = model

    def parse_resume(self, resume_text):
        doc = self.nlp(resume_text)
        entities = {
            "NAME": [],
            "LINKEDIN LINK": [],
            "SKILLS": [],
            "CERTIFICATION": [],
            "WORKED AS": [],
            "YEARS OF EXPERIENCE": []
        }
        for ent in doc.ents:
            if ent.label_ in entities:
                entities[ent.label_].append(ent.text)
        return entities

class JDModel:
    def __init__(self, model):
        self.nlp = model

    def parse_job_description(self, jd_text):
        doc = self.nlp(jd_text)
        entities = {
            "JOB_TITLE": [],
            "COMPANY_NAME": [],
            "SKILLS_REQUIRED": [],
            "EXPERIENCE_REQUIRED": [],
            "SALARY": []
        }
        for ent in doc.ents:
            if ent.label_ in entities:
                entities[ent.label_].append(ent.text)
        return entities

class Matching:
    def __init__(self, resume_id, job_id):
        self.resume_id = resume_id
        self.job_id = job_id
        self.resumeFetchedData = resumeFetchedData
        self.JOBS = JOBS
        self.jd_model = jd_model
        self.resume = self.get_resume_data()  # Fetch resume data
        self.job_description = self.get_job_data() 

    def get_resume_data(self):
        try:
            resume_data = self.resumeFetchedData.find_one({"_id": ObjectId(self.resume_id)})
            if not resume_data:
                raise ValueError("Resume data not found")
            return resume_data
        except Exception as e:
            print(f"Error retrieving resume data: {e}")
            raise

    def get_job_data(self):
        try:
            job_data = self.JOBS.find_one({"_id": ObjectId(self.job_id)})
            if not job_data:
                raise ValueError("Job data not found")
            return job_data
        except Exception as e:
            print(f"Error retrieving job data: {e}")
            raise

    def parse_job_description(self, job_file=None, job_text=None):
        jd_text_parsed = None
        dic_jd = {}

        if job_file and job_file.filename.endswith('.pdf'):
            job_filename = secure_filename(job_file.filename)
            job_path = os.path.join(app.config['UPLOAD_FOLDER_JOB'], job_filename)
            job_file.save(job_path)
            
            with fitz.open(job_path) as doc:
                jd_text = ""
                for page in doc:
                    jd_text += page.get_text()
            
            jd_text_parsed = jd_text
            flash('Job description file uploaded successfully', 'success')
        elif job_text:
            jd_text_parsed = job_text
            flash('Job description text received successfully', 'success')
        else:
            flash('Job description file or text not provided', 'warning')

        if jd_text_parsed:
            try:
                doc_jd = self.jd_model(jd_text_parsed)
                for ent in doc_jd.ents:
                    if ent.label_ not in dic_jd:
                        dic_jd[ent.label_] = []
                    dic_jd[ent.label_].append(ent.text)
                
                JOBS.insert_one(dic_jd)
                flash('Job description text processed and saved successfully', 'success')
            except Exception as e:
                print(f"Exception during spaCy processing: {e}")
                flash('Error processing job description', 'danger')
        else:
            flash('No job description data to process', 'warning')

        return dic_jd

    def calculate_experience(self, experience_list):
        total_experience = 0
        for entry in experience_list:
            try:
                parts = entry.split()
                if "years" in entry or "year" in entry:
                    years = int(parts[0])
                    if "months" in entry or "month" in entry:
                        years += int(parts[2]) / 12
                else:
                    years = int(parts[0]) / 12
                total_experience += round(years, 2)
            except Exception as e:
                print(f"Error converting experience entry '{entry}': {e}")
        return total_experience

   


    def extract_experience(self, experience_str):
        """Extracts the numeric part from a string with years of experience."""
        match = re.search(r'\d+', experience_str)  # Find the first occurrence of one or more digits
        if match:
            return float(match.group(0))  # Convert the found digits to float
        return 0.0  # Return 0 if no numeric part is found

    def compare_job_titles(self, resume_titles, job_titles):
        job_titles = [item.lower() for item in job_titles]
        experience_similarity = 0
        jdpost_similarity = 0
        match_index = -1

        if resume_titles:
            resume_titles = [item.lower() for item in resume_titles]
            for i, item in enumerate(resume_titles):
                if item in job_titles:
                    match_index = i
                    jdpost_similarity = 1
                    if self.resume.get('YEARS OF EXPERIENCE') and self.job_description.get('EXPERIENCE'):
                        jd_experience_str = self.job_description['EXPERIENCE'][0]
                        resume_experience_str = self.resume['YEARS OF EXPERIENCE'][match_index]
                        
                        jd_experience = self.extract_experience(jd_experience_str)
                        resume_experience = self.extract_experience(resume_experience_str)
                        
                        experience_difference = jd_experience - resume_experience

                        if experience_difference <= 0:
                            experience_similarity = 1
                        elif 0 < experience_difference <= 1:
                            experience_similarity = 0.7
                        else:
                            experience_similarity = 0
                    break

        jdpost_similarity *= 0.3
        experience_similarity *= 0.2

        return jdpost_similarity, experience_similarity
    def compare_skills(self, resume_skills, job_skills):
        new_resume_skills = []
        count = 0
        if resume_skills:
            for skill in resume_skills:
                search_query = f"{skill} in technology"
                results = self.get_search_results(search_query)
                if results:
                    new_resume_skills.append(results)
                else:
                    print("No matching articles found")

        if job_skills:
            for skill in job_skills:
                for resume_skill in new_resume_skills:
                    if skill in resume_skill:
                        count += 1
                        break

            skills_similarity = 1 - ((len(job_skills) - count) / len(job_skills)) if job_skills else 0
            skills_similarity *= 0.5
        else:
            skills_similarity = 0

        return skills_similarity
    

    def get_search_results(self,search_query):
        endpoint = f"https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&utf8=1&redirects=1&srprop=size&origin=*&srsearch={search_query}"
        response = requests.get(endpoint)
        data = response.json()
        results = data.get("query", {}).get("search", [])
        if results:
            title = results[0].get("title", "")
            if title:
                return self.get_summary(title)
        return None
    
    def get_summary(self,title):
        endpoint = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&format=json&exsentences=5&explaintext=&origin=*&titles={title}"
        response = requests.get(endpoint)
        data = response.json()
        results = data.get("query", {}).get("pages", {})
        for result in results.values():
            return result.get("extract", "")
        return None
    


    def match(self):
        resume_workedAs = self.resume.get("WORKED AS", [])
        resume_experience_list = self.resume.get("YEARS OF EXPERIENCE", [])
        resume_skills = self.resume.get("SKILLS", [])

        job_description_skills = self.job_description.get('SKILLS', [])
        jd_experience_list = self.job_description.get('EXPERIENCE', [])
        jd_post = self.job_description.get('JOBPOST', [])

        jd_experience = [self.calculate_experience([exp]) for exp in jd_experience_list]
        resume_experience = [self.calculate_experience([exp]) for exp in resume_experience_list]

        jdpost_similarity, experience_similarity = self.compare_job_titles(resume_workedAs, jd_post)
        skills_similarity = self.compare_skills(resume_skills, job_description_skills)

        matching = (jdpost_similarity + experience_similarity + skills_similarity) * 100
        matching = round(matching, 2)

        print("Overall Similarity between resume and JD is", matching)
        return matching

@app.route('/')
def index():

    # Fetch resumes and job descriptions from MongoDB
    resumes = resumeFetchedData.find()  # Fetch all resumes
    job_descriptions = JOBS.find()  # Fetch all job descriptions

    # Convert MongoDB cursors to lists of dictionaries for easy access in the template
    resumes = list(resumes)
    job_descriptions = list(job_descriptions)

    # Ensure that documents are properly formatted
    print("Resumes:", resumes)
    print("Job Descriptions:", job_descriptions)

    return render_template('index.html', resumes=resumes, job_descriptions=job_descriptions)

@app.route('/match', methods=['POST'])
def match_route():
    resume_id = request.form.get('resume_id')
    job_id = request.form.get('job_id')

    if not resume_id or not job_id:
        flash('Please select both a resume and a job description', 'warning')
        return redirect(url_for('index'))

    try:
        # Fetch the selected resume and job description from the database
        selected_resume = resumeFetchedData.find_one({'_id': ObjectId(resume_id)})
        selected_job = JOBS.find_one({'_id': ObjectId(job_id)})

        if not selected_resume or not selected_job:
            flash('Invalid resume or job description selected', 'danger')
            return redirect(url_for('index'))
        
        print("Selected Resume:", selected_resume)
        print("Selected Job:", selected_job)


        # Create an instance of Matching and calculate the score
        matching = Matching(resume_id, job_id)
        score = matching.match()

        flash(f'Match score: {score}%', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('index'))


    '''job_id = request.form['job_id']
    resume = resumeFetchedData.find_one({"UserId": ObjectId(session['user_id'])}, sort=[('_id', -1)])

    if not resume:
        flash('Resume not found for the logged-in user', 'danger')
        return redirect(url_for('index'))

    try:
        matching = Matching(str(resume['_id']), job_id)
        score = matching.match()
        flash(f'Match score: {score}%', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('index'))'''

'''@app.route('/upload', methods=['POST'])
def upload():
    if 'user_id' not in session:
        flash('Please log in to continue', 'warning')
        return redirect(url_for('login'))

    # Retrieve form data
    resume_file = request.files.get('resume')
    job_file = request.files.get('job_description_file')
    job_text = request.form.get('job_description_text')
    company_name = request.form.get('company_name')
    salary = request.form.get('salary')
    job_post = request.form.get('job_post')

    # Debug print statements
    print("Received resume file:", resume_file.filename if resume_file else "No resume file")
    print("Received job file:", job_file.filename if job_file else "No job file")
    print("Received job text:", job_text if job_text else "No job text")
    
    # Handle resume file upload
    if resume_file and resume_file.filename.endswith('.pdf'):
        resume_filename = secure_filename(resume_file.filename)
        resume_path = os.path.join(app.config['UPLOAD_FOLDER_RESUME'], resume_filename)
        resume_file.save(resume_path)
        
        with fitz.open(resume_path) as doc:
            resume_text = ""
            for page in doc:
                resume_text += page.get_text()

        resume_parser = ResumeModel(resume_model)
        resume_data = resume_parser.parse_resume(resume_text)
        resume_data["UserId"] = ObjectId(session['user_id'])
        resumeFetchedData.insert_one(resume_data)
        flash('Resume uploaded successfully', 'success')
    else:
        flash('Resume file not provided or not a PDF', 'warning')

    # Initialize variables for job description
    jd_text_parsed = None

    # Handle job description file
    if job_file and job_file.filename.endswith('.pdf'):
        job_filename = secure_filename(job_file.filename)
        job_path = os.path.join(app.config['UPLOAD_FOLDER_JOB'], job_filename)
        job_file.save(job_path)
        
        with fitz.open(job_path) as doc:
            jd_text = ""
            for page in doc:
                jd_text += page.get_text()
        
        jd_text_parsed = jd_text
        flash('Job description file uploaded successfully', 'success')
    elif job_text:
    
        # Process job description text
        with io.BytesIO(job_text.encode('utf-8')) as data:
            text_of_jd = ""
            try:
                doc = fitz.open(stream=data)
                for page in doc:
                    text_of_jd += page.get_text()
            except Exception as e:
                text_of_jd = job_text

        label_list_jd = []
        text_list_jd = []
        dic_jd = {}

        doc_jd = jd_model(text_of_jd)
        for ent in doc_jd.ents:
            label_list_jd.append(ent.label_)
            text_list_jd.append(ent.text)

        for i in range(len(label_list_jd)):
            if label_list_jd[i] in dic_jd:
                dic_jd[label_list_jd[i]].append(text_list_jd[i])
            else:
                dic_jd[label_list_jd[i]] = [text_list_jd[i]]

        print("JD dictionary:", dic_jd)

        jd_text_parsed = job_text
        flash('Job description text received successfully', 'success')
    else:
        flash('Job description file or text not provided', 'warning')

    # Process job description
    if jd_text_parsed:
        job_parser = JDModel(jd_model)
        job_data = job_parser.parse_job_description(jd_text_parsed)
        job_data.update({
            'company_name': company_name,
            'salary': salary,
            'job_post': job_post,
            'JobFile': job_file.read() if job_file else None
        })
        JOBS.insert_one(job_data)
    else:
        flash('No job description data to process', 'warning')

    return redirect(url_for('index'))'''
@app.route('/upload', methods=['POST'])
def upload():
    # Retrieve form data
    resume_file = request.files.get('resume')
    job_file = request.files.get('job_description_file')
    job_text = request.form.get('job_description_text')
    company_name = request.form.get('company_name')
    salary = request.form.get('salary')
    job_post = request.form.get('job_post')

    # Handle resume file upload
    if resume_file and resume_file.filename.endswith('.pdf'):
        resume_filename = secure_filename(resume_file.filename)
        resume_path = os.path.join(app.config['UPLOAD_FOLDER_RESUME'], resume_filename)
        resume_file.save(resume_path)
        
        with fitz.open(resume_path) as doc:
            resume_text = ""
            for page in doc:
                resume_text += page.get_text()

        resume_parser = ResumeModel(resume_model)
        resume_data = resume_parser.parse_resume(resume_text)
       # resume_data["UserId"] = ObjectId(session['user_id'])
        resumeFetchedData.insert_one(resume_data)
        flash('Resume uploaded successfully', 'success')
    else:
        flash('Resume file not provided or not a PDF', 'warning')

    # Initialize variables for job description
    jd_text_parsed = None
    dic_jd = {}

    # Handle job description file
    if job_file and job_file.filename.endswith('.pdf'):
        job_filename = secure_filename(job_file.filename)
        job_path = os.path.join(app.config['UPLOAD_FOLDER_JOB'], job_filename)
        job_file.save(job_path)
        
        with fitz.open(job_path) as doc:
            jd_text = ""
            for page in doc:
                jd_text += page.get_text()
        
        jd_text_parsed = jd_text
        flash('Job description file uploaded successfully', 'success')
    elif job_text:
        # Process job description text directly
        jd_text_parsed = job_text
        flash('Job description text received successfully', 'success')
    else:
        flash('Job description file or text not provided', 'warning')

    # Process the job description with spaCy model
    if jd_text_parsed:
        try:
            doc_jd = jd_model(jd_text_parsed)
            print("spaCy doc:", doc_jd)
            print("Entities found:", [ent.text for ent in doc_jd.ents])

            label_list_jd = []
            text_list_jd = []

            for ent in doc_jd.ents:
                label_list_jd.append(ent.label_)
                text_list_jd.append(ent.text)
                print(f"Entity: {ent.text}, Label: {ent.label_}")

            for i in range(len(label_list_jd)):
                if label_list_jd[i] in dic_jd:
                    dic_jd[label_list_jd[i]].append(text_list_jd[i])
                else:
                    dic_jd[label_list_jd[i]] = [text_list_jd[i]]

            print("JD dictionary:", dic_jd)
        except Exception as e:
            print(f"Exception during spaCy processing: {e}")

        # Save job description data to MongoDB
        dic_jd.update({
            'company_name': company_name,
            'salary': salary,
            'job_post': job_post
        })
        JOBS.insert_one(dic_jd)
        flash('Job description text processed and saved successfully', 'success')
    else:
        flash('No job description data to process', 'warning')

    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)


