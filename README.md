# testing
# Resume Screening Flask Application

## Overview

This is a Flask-based web application designed for resume screening and job description matching. The application allows users to upload resumes and job descriptions, parse the content using spaCy models, and calculate match scores between resumes and job descriptions.

## Features

- **Resume Upload**: Upload and parse resumes in PDF format.
- **Job Description Upload**: Upload and parse job descriptions in PDF format or provide text input.
- **Matching Engine**: Calculate match scores between uploaded resumes and job descriptions.
- **Data Storage**: Store resumes and job descriptions in MongoDB.


## Technologies Used

- **Flask**: Web framework for Python.
- **spaCy**: NLP library for parsing resumes and job descriptions.
- **MongoDB**: NoSQL database for storing resumes and job descriptions.
- **PyMuPDF (fitz)**: Library for extracting text from PDF files.
- **docx2txt**: Library for extracting text from DOCX files.


### Prerequisites

- Python 3.10 or higher
- spacy model loaded into assets folder


