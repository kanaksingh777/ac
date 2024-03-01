import os
from flask import Flask, render_template, request, redirect, jsonify
import pandas as pd
from datetime import datetime
import logging
import openpyxl

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

def perform_payer_balance_summary(file_path):
    df = pd.read_excel(file_path)
    payer_balance_summary = df.groupby('Claim Primary Payer Name')['Claim Balance'].sum().reset_index()
    payer_balance_summary_sorted = payer_balance_summary.sort_values(by='Claim Balance', ascending=False)
    results = payer_balance_summary_sorted.to_dict(orient='records')
    return results

def perform_aging_summary(file_path):
    df = pd.read_excel(file_path)
    df['Claim From Date'] = pd.to_datetime(df['Claim From Date'])
    df['Age in Days'] = (datetime.now() - df['Claim From Date']).dt.days
    aging_brackets = [30, 60, 90, 120, 365]
    df['Aging Bracket'] = pd.cut(df['Age in Days'], bins=[-1] + aging_brackets + [float('inf')], labels=['0-30', '30+', '60+', '90+', '120+', '365+'])
    aging_summary = df.groupby('Aging Bracket').agg({
        'Claim ID': 'nunique',
        'Claim Balance': 'sum'
    }).sort_index()
    results = aging_summary.to_dict(orient='records')
    return results

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return redirect(request.url)

    file = request.files['file']

    upload_folder = "C:\\AC"
    os.makedirs(upload_folder, exist_ok=True)

    file_path = os.path.join(upload_folder, file.filename)
    file.save(file_path)

    return render_template('analysis_options.html', file_path=file_path)

@app.route('/analyze', methods=['POST'])
def analyze():
    file_path = request.form.get('file_path')
    analysis_option = request.form.get('analysis_option')

    if analysis_option == 'payer_balance_summary':
        results = perform_payer_balance_summary(file_path)
    elif analysis_option == 'aging_summary':
        results = perform_aging_summary(file_path)
    else:
        return render_template('error.html', message='Invalid analysis option')
    print("Results:", results)
    if results is not None:

       
        if results is not None:
            return render_template('analysis_results.html', results=results, analysis_option=analysis_option)
    else:
        return render_template('error.html', message='Error in analysis')
if __name__ == '__main__':
    app.run(debug=True)
