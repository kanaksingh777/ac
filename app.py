import os
from flask import Flask, render_template, request, redirect
import pandas as pd
from datetime import datetime
import logging
import openpyxl

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

def perform_aging_summary(file_path):
    df = pd.read_excel(file_path,skiprows=3,header=1)
    df.drop_duplicates(inplace=True)
    df['Claim From Date'] = pd.to_datetime(df['Claim From Date'])
    df['Age in Days'] = (datetime.now() - df['Claim From Date']).dt.days
    df['Aging Bucket'] = pd.cut(
        df['Age in Days'],
        bins=[0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330, 365, float('inf')],
        labels=['0-30', '30-60', '60-90', '90-120', '120-150', '150-180', '180-210', '210-240', '240-270', '270-300', '300-330', '330-365', '365+'],
        right=False
    )
    df['Claim Balance'] = pd.to_numeric(df['Claim Balance'], errors='coerce')
    aging_bucket_summary = df.groupby('Aging Bucket').agg({
        'Claim Balance': 'sum',
        'Claim ID': 'nunique'
    }).reset_index()
    aging_bucket_summary['Average']=aging_bucket_summary['Claim Balance']/aging_bucket_summary['Claim ID']
    aging_bucket_summary['Average']=aging_bucket_summary['Average'].round(0)
    aging_bucket_summary['Claim Balance'] = aging_bucket_summary['Claim Balance'].round(0)
    grand_total = pd.DataFrame({
    'Aging Bucket': ['Grand Total'],
    'Claim Balance': aging_bucket_summary['Claim Balance'].sum(),
    'Claim ID': aging_bucket_summary['Claim ID'].sum(),
    'Average':''
    })
    grand_total['Claim Balance'] = grand_total['Claim Balance'].round(0)
    
    aging_bucket_summary = pd.concat([aging_bucket_summary, grand_total])
    aging_bucket_summary['Average'] = aging_bucket_summary['Average'].apply(lambda x: "${:,.0f}".format(x) if pd.notna(x) and isinstance(x, (int, float)) else x)

    aging_bucket_summary['Claim Balance']=  aging_bucket_summary['Claim Balance'].apply(lambda x: "${:,.0f}".format(x))

    
    #aging_bucket_summary['Claim Balance']= '$' + aging_bucket_summary['Claim Balance'].astype(str)

    results = aging_bucket_summary.to_dict(orient='records')

    return results

def perform_payer_balance_summary(file_path):
    df = pd.read_excel(file_path,skiprows=3,header=1)
    df.drop_duplicates(inplace=True)
    payer_type_summary = df.groupby('Claim Primary Payer Name').agg({
        'Claim Balance': 'sum',
        'Claim ID': 'nunique'
    }).reset_index()
    payer_type_summary['Average'] = payer_type_summary['Claim Balance'] / payer_type_summary['Claim ID']
    payer_type_summary['Claim Balance'] = payer_type_summary['Claim Balance'].round(0)
    payer_type_summary['Average'] = payer_type_summary['Average'].round(0)
    grand_total_payer = pd.DataFrame({
    'Claim Primary Payer Name': ['Grand Total'],
    'Claim Balance': payer_type_summary['Claim Balance'].sum(),
    'Claim ID': payer_type_summary['Claim ID'].sum(),
    'Average':''
    })
    grand_total_payer['Claim Balance'] = grand_total_payer['Claim Balance'].round(0)
    grand_total_payer['Average'] = grand_total_payer['Average'].round(0)
    payer_type_summary = pd.concat([payer_type_summary, grand_total_payer])
    payer_type_summary.sort_values(by='Claim Balance', ascending=False)
    payer_type_summary['Claim Balance'] = payer_type_summary['Claim Balance'].apply(lambda x: "${:,.0f}".format(x))
    payer_type_summary['Average'] = payer_type_summary['Average'].apply(lambda x: "${:,.0f}".format(x) if pd.notna(x) and isinstance(x, (int, float)) else x)
    
    results = payer_type_summary.to_dict(orient='records')
    return results

def perform_aging_summary_by_payer(file_path):
    df = pd.read_excel(file_path,skiprows=3,header=1)
    df.drop_duplicates(inplace=True)
    df['Claim From Date'] = pd.to_datetime(df['Claim From Date'])
    df['Age in Days'] = (datetime.now() - df['Claim From Date']).dt.days
    df['Aging Bucket'] = pd.cut(
        df['Age in Days'],
        bins=[0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330, 365, float('inf')],
        labels=['0-30', '30-60', '60-90', '90-120', '120-150', '150-180', '180-210', '210-240', '240-270', '270-300', '300-330', '330-365', '365+'],
        right=False
    )
    grouped_df = df.groupby(['Claim Primary Payer Name', 'Aging Bucket']).agg({'Claim ID': 'nunique', 'Claim Balance': 'sum'}).reset_index()
    grouped_df = grouped_df.rename(columns={'Claim ID': 'Unique Claims Count', 'Claim Balance': 'Total Claim Balance'})
    grouped_df['Balance and Count'] = grouped_df.apply(lambda x: f"{x['Total Claim Balance']:.0f} / {x['Unique Claims Count']}", axis=1)
    grouped_df['Total Claim Balance'] = grouped_df['Total Claim Balance'].round(2)
    grand_total_df = grouped_df.groupby('Claim Primary Payer Name').agg({'Unique Claims Count': 'sum', 'Total Claim Balance': 'sum'}).reset_index()
    grand_total_df['Balance and Count'] = grand_total_df.apply(lambda x: f"{x['Total Claim Balance']:.0f} / {x['Unique Claims Count']}", axis=1)


    grouped_df = pd.concat([grouped_df, grand_total_df], ignore_index=True, sort=False)
    pivot_table = pd.pivot_table(grouped_df, 
                             values='Balance and Count', 
                             index='Claim Primary Payer Name', 
                             columns='Aging Bucket', 
                             aggfunc='sum',  
                             fill_value='0.00 / 0').reset_index()
    pivot_table
    df_balances = pivot_table.apply(lambda x: pd.to_numeric(x.str.split('/').str[0].str.replace(',', ''), errors='coerce'))

    pivot_table['Total Balance'] = df_balances.sum(axis=1)

    pivot_table = pivot_table.sort_values(by='Total Balance',ascending = False)
    new_column_order = ['Claim Primary Payer Name', 'Total Balance', '0-30', '30-60', '60-90', '90-120', '120-150', '150-180', '180-210', '210-240', '240-270', '270-300', '300-330', '330-365', '365+']
    pivot_table = pivot_table[new_column_order]
    pivot_table['Total Balance'] = pivot_table['Total Balance'].apply(lambda x: "${:,.0f}".format(x))
    aging_buckets_columns = ['0-30', '30-60', '60-90', '90-120', '120-150', '150-180', '180-210', '210-240', '240-270', '270-300', '300-330', '330-365', '365+']
    for column in aging_buckets_columns:
        pivot_table[column] = pivot_table[column].apply(lambda x: "${:,.0f} / {}".format(float(x.split(' / ')[0]), int(x.split(' / ')[1])))




    results = pivot_table.to_dict(orient='records')

    return results

def claim_status_summary(file_path):
    df = pd.read_excel(file_path,skiprows=3,header=1)
    df.drop_duplicates(inplace=True)
    claim_status_summary = df.groupby('Claim Primary Payer Name')['Claim Balance'].sum().reset_index()
    claim_status_summary = claim_status_summary.sort_values(by='Claim Balance', ascending=False)

    def get_top_claim_statuses_with_balance(row):
        payer_name = row['Claim Primary Payer Name']
    
        filtered_df = df[(df['Claim Primary Payer Name'] == payer_name) & ~df['Claim Status'].isin(['PAID', 'DELETED'])]
    
        top_claim_statuses = filtered_df['Claim Status'].value_counts().head(5).index.tolist()
    
        claim_status_balances = {}

        for claim_status in top_claim_statuses:
            status_balance = filtered_df[filtered_df['Claim Status'] == claim_status]['Claim Balance'].sum()
            claim_status_balances[claim_status] = status_balance
    
        return claim_status_balances

    claim_status_summary['Top Claim Statuses with Balance'] = claim_status_summary.apply(get_top_claim_statuses_with_balance, axis=1)
    results = claim_status_summary.to_dict(orient='records')
    
    return results
def balance_bucket(file_path):
    df = pd.read_excel(file_path,skiprows=3,header=1)
    df.drop_duplicates(inplace=True)
    bins = [0,100,200,300,400,500,600, 700, 800, 900, 1000,1500,2000,3000,4000,5000]
    labels = [f'{start}-{end}' for start, end in zip(bins[:-1], bins[1:])]
    df['Balance Bucket'] = pd.cut(df['Claim Balance'], bins=bins, labels=labels, include_lowest=True)

    balance_bucket_info = df.groupby('Balance Bucket').agg({'Claim ID': 'nunique', 'Claim Balance': 'sum'}).reset_index()
    balance_bucket_info.columns = ['Balance Bucket', 'Unique Claims Count', 'Total Balance']
    grand_total = df['Claim Balance'].sum()
    grand_total_row = pd.DataFrame({'Balance Bucket': 'Grand Total', 'Unique Claims Count': df['Claim ID'].nunique(), 'Total Balance': grand_total}, index=[0])

    balance_bucket_info = pd.concat([balance_bucket_info, grand_total_row], ignore_index=True)

    balance_bucket_info['Percentage'] = ((balance_bucket_info['Total Balance'] / grand_total) * 100).round(2).astype(str) + '%'
    balance_bucket_info['Total Balance'] = balance_bucket_info['Total Balance'].round(0)
    balance_bucket_info['Total Balance']=balance_bucket_info['Total Balance'].apply(lambda x: "${:,.0f}".format(x))


    results = balance_bucket_info.to_dict(orient='records')
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
    file_name = os.path.splitext(file.filename)[0]

    return render_template('analysis_options.html', file_path=file_path,file_name=file_name)


def testingFunction(file_path):
    #this is the testing function x
    df = pd.read_excel(file_path)

@app.route('/analyze', methods=['POST'])
def analyze():
    file_path = request.form.get('file_path')
    df= pd.read_excel(file_path)
    complete_date_time_str=df.iloc[0,0]
    date_time_str = complete_date_time_str.split('Run Date: ')[1]
    run_date_time = f'Data Export Date: {date_time_str}'

    analysis_option = request.form.get('analysis_option')
    file_name = os.path.splitext(os.path.basename(file_path))[0]

    if analysis_option == 'payer_balance_summary':
        results = perform_payer_balance_summary(file_path)
    elif analysis_option == 'aging_summary':
        results = perform_aging_summary(file_path)
    elif analysis_option == 'aging_summary_by_payer':
        results = perform_aging_summary_by_payer(file_path)
    elif analysis_option == 'claim_status_summary':
        results = claim_status_summary(file_path)
    elif analysis_option=='balance_bucket':
        results=balance_bucket(file_path)

    else:
        return render_template('error.html', message='Invalid analysis option')

    print("Results:", results)

    if results is not None:
        return render_template('analysis_results.html', results=results, analysis_option=analysis_option,file_name=file_name,run_date_time=run_date_time)
    else:
        return render_template('error.html', message='Error in analysis')

if __name__ == '__main__':
    app.run(debug=True)
