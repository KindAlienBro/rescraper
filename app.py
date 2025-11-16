# app.py (Version with Corrected Percentage and Conditional Formatting)

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import pdfkit
import io
from scraper import fetch_vtu_results 
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, Border, Side, PatternFill

# --- CONFIGURATION ---
# IMPORTANT: Update this path to where you installed wkhtmltopdf on your system.
path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe' 
config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app, resources={r"/*": {"origins": "*"}})

# --- UTILITY FUNCTIONS ---
def generate_usn_range(start_usn, end_usn):
    """Generates a list of USNs within a given range."""
    try:
        start_prefix, end_prefix = start_usn[:-3], end_usn[:-3]
        if start_prefix != end_prefix: return []
        start_num, end_num = int(start_usn[-3:]), int(end_usn[-3:])
        return [f"{start_prefix}{str(i).zfill(3)}" for i in range(start_num, end_num + 1)]
    except (ValueError, IndexError): return []

# --- DATA FORMATTER (WITH MODIFIED PERCENTAGE LOGIC) ---
def format_data_for_wide_export(results_data):
    """
    Transforms scraper data into a wide format and calculates Percentage and Class.
    """
    if not results_data:
        return [], []

    all_subjects = set()
    for student in results_data:
        for subject in student.get('subjects', []):
            all_subjects.add(subject.get('subject_code'))
    
    sorted_subject_codes = sorted(list(filter(None, all_subjects)))
    
    processed_records = []
    for student in results_data:
        student_subjects = {s['subject_code']: s for s in student.get('subjects', [])}

        record = {
            'USN': student.get('usn', 'N/A'),
            'Name': student.get('student_name', 'N/A'),
            'subjects_data': {}
        }

        for code in sorted_subject_codes:
            subject_details = student_subjects.get(code)
            record['subjects_data'][code] = {
                'IA': subject_details.get('internal_marks', '-') if subject_details else '-',
                'Ex': subject_details.get('external_marks', '-') if subject_details else '-',
                'Total': subject_details.get('total', '-') if subject_details else '-',
                'Pass/Fail': subject_details.get('result', '-') if subject_details else '-'
            }

        # --- MODIFIED: More Accurate Percentage Calculation ---
        total_marks_obtained = 0
        subjects_for_percentage = 0
        has_failed_a_subject = False
        
        for subject in student.get('subjects', []):
            if subject.get('result') == 'F':
                has_failed_a_subject = True
            
            subject_total = 0
            has_valid_marks = False
            # Try to add internal marks
            try:
                subject_total += int(subject.get('internal_marks', '0'))
                has_valid_marks = True
            except (ValueError, TypeError): pass
            # Try to add external marks
            try:
                subject_total += int(subject.get('external_marks', '0'))
                has_valid_marks = True
            except (ValueError, TypeError): pass

            # Only count this subject if it had at least one valid mark component
            if has_valid_marks:
                total_marks_obtained += subject_total
                subjects_for_percentage += 1
        
        # Calculate Percentage
        if subjects_for_percentage > 0:
            max_possible_marks = subjects_for_percentage * 100
            percentage = (total_marks_obtained / max_possible_marks) * 100
            record['percentage'] = f"{percentage:.2f}%"
        else:
            percentage = 0
            record['percentage'] = "N/A"

        # Determine Class
        if has_failed_a_subject or percentage < 50:
            record['class'] = "FAIL"
        elif percentage >= 70:
            record['class'] = "FCD"
        elif percentage >= 60:
            record['class'] = "FC"
        elif percentage >= 50:
            record['class'] = "SC"
        else:
            record['class'] = "N/A" if record['percentage'] == "N/A" else "FAIL"
        
        # Calculate summary stats
        failed_count = sum(1 for s in student.get('subjects', []) if s.get('result') == 'F')
        absent_count = sum(1 for s in student.get('subjects', []) if s.get('result') == 'A')
        record['subjects_failed'] = failed_count
        record['subjects_absent'] = absent_count
        
        processed_records.append(record)

    return processed_records, sorted_subject_codes

# --- API ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    data = request.json
    start_usn, end_usn, vtu_url = data.get('start_usn', '').upper(), data.get('end_usn', '').upper(), data.get('vtu_url', '')
    if not all([start_usn, end_usn, vtu_url]): return jsonify({'error': 'Missing required fields.'}), 400
    usn_list = generate_usn_range(start_usn, end_usn)
    if not usn_list: return jsonify({'error': 'Invalid USN format or range.'}), 400
    results = fetch_vtu_results(usn_list, vtu_url)
    if not results: return jsonify({'error': 'No new results were found.'}), 500
    return jsonify(results)

@app.route('/download/excel', methods=['POST'])
def download_excel():
    results_data = request.json
    records, subject_codes = format_data_for_wide_export(results_data)
    if not records: return "No data to export", 400
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Results"

    # Define cell fill for failed subjects/class
    red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    header_font = Font(bold=True)
    center_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

    # --- HEADER ROWS ---
    ws.cell(row=1, column=1, value='USN').font = header_font
    ws.merge_cells(start_row=1, start_column=1, end_row=2, end_column=1)
    ws.cell(row=1, column=2, value='Name').font = header_font
    ws.merge_cells(start_row=1, start_column=2, end_row=2, end_column=2)
    col_idx = 3
    for code in subject_codes:
        ws.cell(row=1, column=col_idx, value=code).font = header_font
        ws.merge_cells(start_row=1, start_column=col_idx, end_row=1, end_column=col_idx + 3)
        col_idx += 4
    ws.cell(row=1, column=col_idx, value='NO OF SUBJECTS FAILED').font = header_font
    ws.merge_cells(start_row=1, start_column=col_idx, end_row=2, end_column=col_idx)
    ws.cell(row=1, column=col_idx + 1, value='NO OF SUBJECTS ABSENT').font = header_font
    ws.merge_cells(start_row=1, start_column=col_idx + 1, end_row=2, end_column=col_idx + 1)
    ws.cell(row=1, column=col_idx + 2, value='Percentage').font = header_font
    ws.merge_cells(start_row=1, start_column=col_idx + 2, end_row=2, end_column=col_idx + 2)
    ws.cell(row=1, column=col_idx + 3, value='Class').font = header_font
    ws.merge_cells(start_row=1, start_column=col_idx + 3, end_row=2, end_column=col_idx + 3)
    sub_headers = ['IA', 'Ex', 'Total', 'Pass/Fail']
    col_idx = 3
    for _ in subject_codes:
        for i, sub_header in enumerate(sub_headers): ws.cell(row=2, column=col_idx + i, value=sub_header).font = header_font
        col_idx += 4
    
    # --- DATA ROWS WITH CONDITIONAL FORMATTING ---
    row_idx = 3
    for record in records:
        ws.cell(row=row_idx, column=1, value=record['USN'])
        ws.cell(row=row_idx, column=2, value=record['Name'])
        
        col_idx = 3
        for code in subject_codes:
            subject_data = record['subjects_data'][code]
            ws.cell(row=row_idx, column=col_idx, value=subject_data['IA'])
            ws.cell(row=row_idx, column=col_idx+1, value=subject_data['Ex'])
            ws.cell(row=row_idx, column=col_idx+2, value=subject_data['Total'])
            
            pass_fail_cell = ws.cell(row=row_idx, column=col_idx+3, value=subject_data['Pass/Fail'])
            if subject_data['Pass/Fail'] == 'F':
                pass_fail_cell.fill = red_fill
            
            col_idx += 4
            
        ws.cell(row=row_idx, column=col_idx, value=record['subjects_failed'])
        ws.cell(row=row_idx, column=col_idx+1, value=record['subjects_absent'])
        ws.cell(row=row_idx, column=col_idx+2, value=record['percentage'])

        class_cell = ws.cell(row=row_idx, column=col_idx+3, value=record['class'])
        if record['class'] == 'FAIL':
            class_cell.fill = red_fill
            
        row_idx += 1
        
    # Apply default styles to all cells
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = center_align
            cell.border = thin_border

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='results.xlsx')

@app.route('/download/pdf', methods=['POST'])
def download_pdf():
    results_data = request.json
    records, subject_codes = format_data_for_wide_export(results_data)
    if not records: return "No data to export", 400
    rendered_html = render_template('results_template.html', results=records, subject_codes=subject_codes)
    try:
        options = {'orientation': 'Landscape', 'page-size': 'A2', 'margin-top': '0.5in', 'margin-right': '0.5in', 'margin-bottom': '0.5in', 'margin-left': '0.5in'}
        pdf = pdfkit.from_string(rendered_html, False, configuration=config, options=options)
        return send_file(io.BytesIO(pdf), mimetype='application/pdf', as_attachment=True, download_name='results.pdf')
    except Exception as e:
        print(f"PDF Generation Error: {e}")
        return jsonify({'error': 'Could not generate PDF.'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)