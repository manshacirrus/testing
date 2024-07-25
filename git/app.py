from flask import Flask, request, render_template, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os
import io
import fitz  # PyMuPDF
from flask_pymongo import PyMongo
import docx2txt
import spacy
from bson import ObjectId
from MediaWiki import get_search_results
import re
import requests

app = Flask(__name__)
app.secret_key = 'Resumescreening'

# MongoDB client setup
app.config['MONGO_URI'] = 'mongodb+srv://admin:admin@cluster0.na6om9v.mongodb.net/Project0'
mongo = PyMongo(app)

# Initialize MongoDB collections
resumeFetchedData = mongo.db.resumeFetchedData
JOBS = mongo.db.JOBS

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
        print("Parsed Resume Entities:", entities)  # Print resume entities
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
        print("Parsed Job Description Entities:", entities)  # Print job description entities
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
            print("Retrieved Resume Data:", resume_data)  # Print resume data
            return resume_data
        except Exception as e:
            print(f"Error retrieving resume data: {e}")
            raise

    def get_job_data(self):
        try:
            job_data = self.JOBS.find_one({"_id": ObjectId(self.job_id)})
            if not job_data:
                raise ValueError("Job data not found")
            print("Retrieved Job Data:", job_data)  # Print job description data
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

        print("Parsed Job Description Data:", dic_jd)  # Print job description parsed data
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
        print("Total Experience Calculated:", total_experience)  # Print calculated total experience
        return total_experience

    def extract_experience(experience_str):
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

        print("Job Post Similarity:", jdpost_similarity)  # Print job post similarity
        print("Experience Similarity:", experience_similarity)  # Print experience similarity

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

        print("Skills Similarity:", skills_similarity)  # Print skills similarity
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
        return results
    
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
        job_description_titles = self.job_description.get('JOB_TITLE', [])

        jdpost_similarity, experience_similarity = self.compare_job_titles(resume_workedAs, job_description_titles)
        skills_similarity = self.compare_skills(resume_skills, job_description_skills)
        print(f"JD Post Similarity: {jdpost_similarity}")
        print(f"Experience Similarity: {experience_similarity}")
        print(f"Skills Similarity: {skills_similarity}")
        
        final_score = jdpost_similarity + experience_similarity + skills_similarity
        final_score_percentage = round(final_score * 100, 2)

        return final_score_percentage
        print("Total Match Score:", final_score = jdpost_similarity + experience_similarity + skills_similarity)  # Print total match score
        return final_score_percentage
@app.route('/')
def index():
    resumes = resumeFetchedData.find()
    jobs = JOBS.find()

    return render_template('index.html', resumes=resumes, jobs=jobs)

@app.route('/upload', methods=['POST'])
def upload():
    resume_file = request.files['resume']
    job_file = request.files.get('job_description')
    job_text = request.form.get('job_text')

    if not resume_file or not (job_file or job_text):
        flash('Please upload both resume and job description', 'warning')
        return redirect(url_for('index'))

    if resume_file and resume_file.filename.endswith('.pdf'):
        filename = secure_filename(resume_file.filename)
        resume_path = os.path.join(app.config['UPLOAD_FOLDER_RESUME'], filename)
        resume_file.save(resume_path)
        
        with fitz.open(resume_path) as doc:
            resume_text = ""
            for page in doc:
                resume_text += page.get_text()

        resume_parser = ResumeModel(resume_model)
        resume_entities = resume_parser.parse_resume(resume_text)
        resume_id = resumeFetchedData.insert_one(resume_entities).inserted_id

    elif resume_file and resume_file.filename.endswith('.docx'):
        filename = secure_filename(resume_file.filename)
        resume_path = os.path.join(app.config['UPLOAD_FOLDER_RESUME'], filename)
        resume_file.save(resume_path)
        
        resume_text = docx2txt.process(resume_path)

        resume_parser = ResumeModel(resume_model)
        resume_entities = resume_parser.parse_resume(resume_text)
        resume_id = resumeFetchedData.insert_one(resume_entities).inserted_id

    else:
        flash('Unsupported resume file format', 'danger')
        return redirect(url_for('index'))

    jd_parser = Matching(resume_id, None)
    job_description = jd_parser.parse_job_description(job_file, job_text)
    job_id = JOBS.insert_one(job_description).inserted_id

    matching = Matching(resume_id, job_id)
    match_score = matching.match()
    print(f"Match Score: {match_score}")

    return render_template('result.html', resume_entities=resume_entities, job_description=job_description, match_score=match_score)

if __name__ == '__main__':
    app.run(debug=True)

