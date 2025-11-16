from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import pdfkit
import io
from scraper import fetch_vtu_results

app = Flask(__name__)

# --- ⚠️ IMPORTANT CONFIGURATION ---
# Update this path to where your wkhtmltopdf executable is located.
#   - Windows example: r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
#   - Linux example: r'/usr/bin/wkhtmltopdf'
path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe' # <--- UPDATE THIS PATH
config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)

def generate_usn_range(start_usn, end_usn):
    """Generates a list of USNs from a start and end USN string."""
    try:
        start_prefix, end_prefix = start_usn[:-3], end_usn[:-3]
        if start_prefix != end_prefix:
            return []
        start_num, end_num = int(start_usn[-3:]), int(end_usn[-3:])
        return [f"{start_prefix}{str(i).zfill(3)}" for i in range(start_num, end_num + 1)]
    except (ValueError, IndexError):
        return []

@app.route('/')
def index():
    """Renders the main homepage (index.html)."""
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    """API endpoint to handle the scraping request."""
    data = request.json
    start_usn, end_usn, vtu_url = data.get('start_usn', '').upper(), data.get('end_usn', '').upper(), data.get('vtu_url', '')

    if not all([start_usn, end_usn, vtu_url]):
        return jsonify({'error': 'Please provide Start USN, End USN, and the Result Link.'}), 400
    if not vtu_url.startswith('http'):
         return jsonify({'error': 'Please provide a valid Result Link (starting with http/https).'}), 400
        
    usn_list = generate_usn_range(start_usn, end_usn)
    if not usn_list:
        return jsonify({'error': 'Invalid USN format or range. The prefix (e.g., 1CR20CS) must be the same.'}), 400

    print(f"Starting scrape for {len(usn_list)} USNs on URL: {vtu_url}")
    results = fetch_vtu_results(usn_list, vtu_url)
    
    if not results:
        return jsonify({'error': 'No results with subject marks were found for the given range.'}), 500
        
    print(f"Scraping complete. Found {len(results)} results.")
    return jsonify(results)

def format_data_for_export(results_data):
    """
    Dynamically prepares data for export with detailed columns for each subject.
    """
    records = []
    # Find all unique subject codes across ALL students to create consistent columns
    all_subject_codes = sorted(list(set(
        sub['code'] for student in results_data for sub in student.get('subjects', []) if sub
    )))
    
    for student in results_data:
        record = { 'USN': student.get('usn'), 'Name': student.get('student_name', '').replace(':','').strip() }

        # Create a dictionary of this student's subjects for easy lookup
        student_subjects = {sub['code']: sub for sub in student.get('subjects', []) if sub}
        
        # Loop through the master list of subjects to build columns in a consistent order
        for code in all_subject_codes:
            if code in student_subjects:
                subject_data = student_subjects[code]
                record[f'{code} - Internal'] = subject_data.get('internal', 'N/A')
                record[f'{code} - External'] = subject_data.get('external', 'N/A')
                record[f'{code} - Total'] = subject_data.get('total', 'N/A')
                record[f'{code} - Result'] = subject_data.get('result', 'N/A')
            else:
                # If student does not have this subject, fill with placeholders
                record[f'{code} - Internal'] = '-'
                record[f'{code} - External'] = '-'
                record[f'{code} - Total'] = '-'
                record[f'{code} - Result'] = '-'

        # Add the final summary columns at the end
        record['Total Marks'] = student.get('total_marks', 'N/A')
        record['Result Class'] = student.get('result_class', 'N/A')
        
        records.append(record)
    return records

@app.route('/download/excel', methods=['POST'])
def download_excel():
    """API endpoint to generate and send an Excel file."""
    results_data = request.json
    records = format_data_for_export(results_data)
    if not records: return "No data to export", 400
        
    df = pd.DataFrame(records)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='VTU Results')
    output.seek(0)
    
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='vtu_results.xlsx')

@app.route('/download/pdf', methods=['POST'])
def download_pdf():
    """API endpoint to generate and send a PDF file."""
    results_data = request.json
    records = format_data_for_export(results_data)
    if not records: return "No data to export", 400
        
    rendered_html = render_template('results_template.html', results=records)
    try:
        # PDF options for landscape mode and larger page size to fit more columns
        options = {
            'orientation': 'Landscape',
            'page-size': 'A3',
            'margin-top': '0.5in',
            'margin-right': '0.5in',
            'margin-bottom': '0.5in',
            'margin-left': '0.5in',
            'encoding': "UTF-8"
        }
        pdf = pdfkit.from_string(rendered_html, False, configuration=config, options=options)
        return send_file(io.BytesIO(pdf), mimetype='application/pdf', as_attachment=True, download_name='vtu_results.pdf')
    except Exception as e:
        print(f"PDF Generation Error: {e}")
        return jsonify({'error': 'Could not generate PDF. Check if wkhtmltopdf is installed and the path is correct in app.py.'}), 500

if __name__ == '__main__':
    app.run(debug=True)