# app.py (Final Version with Analysis Dashboard and Analysis Export)

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import pdfkit
import io
import re
import pandas as pd
import json
from scraper import fetch_vtu_results 
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
from openpyxl.utils import get_column_letter

# --- (All configurations, helper functions, and data formatters remain the same) ---
path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe' 
config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app, resources={r"/*": {"origins": "*"}})
CREDIT_MAP = {
    'BCS401': 3, # ADA
    'BAD402': 4, # AI
    'BCS403': 4, # DBMS
    'BCS405A': 3, #DMS
    'BCS405C': 3, #OT
    
    
    'BCSL404': 1, #ADAL
    'BDSL456B': 1, #MONGO
    'BDSL456C': 1, #MERN
    
    
    'BBOC407': 2, #BIO
    'BUHK408': 1, #UHV
    'BPEK459': 0, #PE
    'BYOK459': 0, #YOGA
    'BNSK459': 0, #NSS
    
    
}
def get_grade_point(marks_str, result_str):
    if result_str in ['F', 'A', 'NE']: return 0
    try:
        marks = int(marks_str)
        if 90 <= marks <= 100: return 10
        elif 80 <= marks <= 89: return 9
        elif 70 <= marks <= 79: return 8
        elif 60 <= marks <= 69: return 7
        elif 55 <= marks <= 59: return 6
        elif 50 <= marks <= 54: return 5
        elif 40 <= marks <= 49: return 4
        else: return 0
    except (ValueError, TypeError): return 0
def generate_usn_range(start_usn, end_usn):
    try:
        start_prefix, end_prefix = start_usn[:-3], end_usn[:-3]
        if start_prefix != end_prefix: return []
        start_num, end_num = int(start_usn[-3:]), int(end_usn[-3:])
        return [f"{start_prefix}{str(i).zfill(3)}" for i in range(start_num, end_num + 1)]
    except (ValueError, IndexError): return []
def format_data_for_wide_export(results_data):
    if not results_data: return [], []
    all_subject_codes = set(sub['subject_code'] for student in results_data for sub in student.get('subjects', []))
    elective_groups = {}
    for code in all_subject_codes:
        if not code: continue
        match = re.search(r'\d+', code)
        if match:
            group_key = match.group(0)
            if group_key not in elective_groups: elective_groups[group_key] = []
            elective_groups[group_key].append(code)
    display_headers = []
    for key, codes in sorted(elective_groups.items()):
        is_elective = len(codes) > 1
        header_info = {"header": key if is_elective else codes[0], "is_elective": is_elective}
        display_headers.append(header_info)
    processed_records = []
    for student in results_data:
        student_subjects = {s['subject_code']: s for s in student.get('subjects', [])}
        record = {'USN': student.get('usn', 'N/A'),'Name': student.get('student_name', 'N/A'),'subjects_data': {}}
        for header_info in display_headers:
            header_key = header_info["header"]
            found_subject = None
            if header_info["is_elective"]:
                for elective_code in elective_groups[header_key]:
                    if elective_code in student_subjects: found_subject = student_subjects[elective_code]; break
            else:
                if header_key in student_subjects: found_subject = student_subjects[header_key]
            if found_subject:
                record['subjects_data'][header_key] = {'Course': found_subject.get('subject_code', '-'), 'IA': found_subject.get('internal_marks', '-'),'Ex': found_subject.get('external_marks', '-'), 'Total': found_subject.get('total', '-'), 'Pass/Fail': found_subject.get('result', '-')}
            else:
                record['subjects_data'][header_key] = {'Course': '-', 'IA': '-', 'Ex': '-', 'Total': '-', 'Pass/Fail': '-'}
        total_credit_points, total_grade_credit_product = 0, 0
        for subject in student.get('subjects', []):
            credits = CREDIT_MAP.get(subject.get('subject_code'))
            if credits is None: continue
            grade_point = get_grade_point(subject.get('total'), subject.get('result'))
            total_credit_points += credits
            total_grade_credit_product += (grade_point * credits)
        record['sgpa'] = f"{(total_grade_credit_product / total_credit_points):.2f}" if total_credit_points > 0 else "N/A"
        num_subjects_for_student = len(student.get('subjects', []))
        max_possible_marks = num_subjects_for_student * 100
        total_marks_obtained, has_failed_a_subject = 0, False
        for subject in student.get('subjects', []):
            if subject.get('result') == 'F': has_failed_a_subject = True
            try: total_marks_obtained += int(subject.get('internal_marks', '0'))
            except: pass
            try: total_marks_obtained += int(subject.get('external_marks', '0'))
            except: pass
        percentage = (total_marks_obtained / max_possible_marks) * 100 if max_possible_marks > 0 else 0
        record['percentage'] = f"{percentage:.2f}%" if max_possible_marks > 0 else "N/A"
        if has_failed_a_subject or percentage < 50: record['class'] = "FAIL"
        elif percentage >= 70: record['class'] = "FCD"
        elif percentage >= 60: record['class'] = "FC"
        elif percentage >= 50: record['class'] = "SC"
        else: record['class'] = "N/A" if record['percentage'] == "N/A" else "FAIL"
        record['subjects_failed'] = sum(1 for s in student.get('subjects', []) if s.get('result') == 'F')
        record['subjects_absent'] = sum(1 for s in student.get('subjects', []) if s.get('result') == 'A')
        processed_records.append(record)
    return processed_records, display_headers
# ... (all routes up to /analyze are the same) ...
@app.route('/')
def index(): return render_template('index.html')
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
    records, display_headers = format_data_for_wide_export(results_data)
    if not records: return "No data to export", 400
    wb = Workbook()
    ws = wb.active; ws.title = "Results"
    red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    header_font = Font(bold=True)
    center_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    ws.cell(row=1, column=1, value='USN').font = header_font; ws.merge_cells('A1:A2')
    ws.cell(row=1, column=2, value='Name').font = header_font; ws.merge_cells('B1:B2')
    col_idx = 3
    for header_info in display_headers:
        is_elective = header_info["is_elective"]
        colspan = 5 if is_elective else 4
        ws.cell(row=1, column=col_idx, value=header_info["header"]).font = header_font
        ws.merge_cells(start_row=1, start_column=col_idx, end_row=1, end_column=col_idx + colspan - 1)
        sub_headers = ['Course', 'IA', 'Ex', 'Total', 'Pass/Fail'] if is_elective else ['IA', 'Ex', 'Total', 'Pass/Fail']
        for i, sub_header in enumerate(sub_headers):
            ws.cell(row=2, column=col_idx + i, value=sub_header).font = header_font
        col_idx += colspan
    summary_start_col = col_idx
    summary_headers = ['NO OF SUBJECTS FAILED', 'NO OF SUBJECTS ABSENT', 'Percentage', 'Class', 'SGPA']
    for i, h in enumerate(summary_headers):
        ws.cell(row=1, column=summary_start_col + i, value=h).font = header_font
        ws.merge_cells(start_row=1, start_column=summary_start_col + i, end_row=2, end_column=summary_start_col + i)
    row_idx = 3
    for record in records:
        ws.cell(row=row_idx, column=1, value=record['USN'])
        ws.cell(row=row_idx, column=2, value=record['Name'])
        col_idx = 3
        for header_info in display_headers:
            header_key, is_elective = header_info["header"], header_info["is_elective"]
            data = record['subjects_data'][header_key]
            if is_elective:
                ws.cell(row=row_idx, column=col_idx, value=data['Course']); ws.cell(row=row_idx, column=col_idx + 1, value=data['IA']); ws.cell(row=row_idx, column=col_idx + 2, value=data['Ex']); ws.cell(row=row_idx, column=col_idx + 3, value=data['Total']); pf_cell = ws.cell(row=row_idx, column=col_idx + 4, value=data['Pass/Fail'])
                if data['Pass/Fail'] == 'F': pf_cell.fill = red_fill
                col_idx += 5
            else:
                ws.cell(row=row_idx, column=col_idx, value=data['IA']); ws.cell(row=row_idx, column=col_idx + 1, value=data['Ex']); ws.cell(row=row_idx, column=col_idx + 2, value=data['Total']); pf_cell = ws.cell(row=row_idx, column=col_idx + 3, value=data['Pass/Fail'])
                if data['Pass/Fail'] == 'F': pf_cell.fill = red_fill
                col_idx += 4
        ws.cell(row=row_idx, column=col_idx, value=record['subjects_failed']); ws.cell(row=row_idx, column=col_idx + 1, value=record['subjects_absent']); ws.cell(row=row_idx, column=col_idx + 2, value=record['percentage']); ws.cell(row=row_idx, column=col_idx + 4, value=record['sgpa']); class_cell = ws.cell(row=row_idx, column=col_idx + 3, value=record['class'])
        if record['class'] == 'FAIL': class_cell.fill = red_fill
        row_idx += 1
    for row in ws.iter_rows():
        for cell in row: cell.alignment = center_align; cell.border = thin_border
    output = io.BytesIO(); wb.save(output); output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='results.xlsx')
@app.route('/download/pdf', methods=['POST'])
def download_pdf():
    results_data = request.json
    records, display_headers = format_data_for_wide_export(results_data)
    if not records: return "No data to export", 400
    rendered_html = render_template('results_template.html', results=records, display_headers=display_headers)
    try:
        options = {'orientation': 'Landscape', 'page-size': 'A3', 'margin-top': '0.5in', 'margin-right': '0.5in', 'margin-bottom': '0.5in', 'margin-left': '0.5in'}
        pdf = pdfkit.from_string(rendered_html, False, configuration=config, options=options)
        return send_file(io.BytesIO(pdf), mimetype='application/pdf', as_attachment=True, download_name='results.pdf')
    except Exception as e:
        print(f"PDF Generation Error: {e}"); return jsonify({'error': 'Could not generate PDF.'}), 500
def calculate_statistics(df):
    stats = {}
    class_col_name = [col for col in df.columns if 'Class' in col[0]][0]
    class_series = df[class_col_name]
    stats['overall'] = {"fcd": int((class_series == 'FCD').sum()),"fc": int((class_series == 'FC').sum()),"sc": int((class_series == 'SC').sum()),"fail": int((class_series == 'FAIL').sum())}
    subject_stats = {}
    subject_headers = [col[0] for col in df.columns if col[0] not in ['USN', 'Name'] and not col[0].startswith('Unnamed')]
    unique_subject_headers = sorted(list(set(subject_headers)))
    for header in unique_subject_headers:
        if header in subject_stats: continue
        subject_df = df[header]
        pass_fail_series = subject_df['Pass/Fail']
        passes = (pass_fail_series == 'P').sum()
        fails = (pass_fail_series == 'F').sum()
        absent = (pass_fail_series == 'A').sum()
        withheld = (pass_fail_series == 'NE').sum()
        appeared = passes + fails
        pass_percentage = (passes / appeared) * 100 if appeared > 0 else 0
        subject_stats[header] = {"appeared": int(appeared),"pass": int(passes),"fail": int(fails),"absent": int(absent),"withheld": int(withheld),"pass_percentage": pass_percentage}
    stats['subject_wise'] = subject_stats
    return stats
@app.route('/analyze', methods=['GET', 'POST'])
def analyze():
    if request.method == 'POST':
        if 'results_file' not in request.files: return "No file part", 400
        file = request.files['results_file']
        if file.filename == '' or not file.filename.endswith('.xlsx'): return "Please upload a valid .xlsx file", 400
        try:
            df = pd.read_excel(file, header=[0, 1])
            stats = calculate_statistics(df)
            return render_template('analyze.html', stats=stats, stats_json=json.dumps(stats))
        except Exception as e:
            print(f"Error processing Excel file: {e}")
            return "Error processing Excel file. Ensure it is in the correct format.", 500
    return render_template('analyze.html', stats=None)

# --- NEW: Function to Create the Analysis Excel Workbook ---
def create_analysis_workbook(stats):
    wb = Workbook()
    
    # --- Sheet 1: Overall Summary ---
    ws_overall = wb.active
    ws_overall.title = "Overall Summary"
    
    header_font = Font(bold=True)
    center_align = Alignment(horizontal='center', vertical='center')

    # Add Overall Class Distribution
    ws_overall.append(['Overall Class Distribution'])
    ws_overall['A1'].font = header_font
    headers1 = ['FCD', 'First Class', 'Second Class', 'Fail', 'Total Pass', 'Total Appeared']
    for i, header in enumerate(headers1):
        cell = ws_overall.cell(row=2, column=i+1, value=header)
        cell.font = header_font
        cell.alignment = center_align

    o = stats['overall']
    total_pass = o['fcd'] + o['fc'] + o['sc']
    total_appeared = total_pass + o['fail']
    ws_overall.append([o['fcd'], o['fc'], o['sc'], o['fail'], total_pass, total_appeared])

    # --- Sheet 2: Subject-Wise Analysis ---
    ws_subject = wb.create_sheet("Subject-Wise Analysis")
    
    headers2 = ["Subject", "Appeared", "Pass", "Fail", "Absent", "Withheld / NE", "Pass %"]
    for i, header in enumerate(headers2):
        cell = ws_subject.cell(row=1, column=i+1, value=header)
        cell.font = header_font
        cell.alignment = center_align

    for code, data in stats['subject_wise'].items():
        pass_percent = f"{data['pass_percentage']:.2f}%"
        ws_subject.append([code, data['appeared'], data['pass'], data['fail'], data['absent'], data['withheld'], pass_percent])

    # Auto-fit column widths for both sheets
    for sheet in wb.sheetnames:
        for col in wb[sheet].columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try: 
                    if len(str(cell.value)) > max_length:
                        max_length = len(cell.value)
                except: pass
            adjusted_width = (max_length + 2)
            wb[sheet].column_dimensions[column].width = adjusted_width

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

# --- NEW: Route to Handle Downloading the Analysis ---
@app.route('/download/analysis', methods=['POST'])
def download_analysis():
    stats_data = request.json
    if not stats_data:
        return "No analysis data provided", 400
    
    try:
        output = create_analysis_workbook(stats_data)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='results_analysis.xlsx'
        )
    except Exception as e:
        print(f"Error creating analysis workbook: {e}")
        return "Error creating analysis file", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)