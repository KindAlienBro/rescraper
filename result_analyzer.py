import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO

def analyze_results(input_file):
    """
    Analyzes a VTU result Excel file with multi-level headers.

    Args:
        input_file: A file path or a file-like object (e.g., from a file uploader).

    Returns:
        BytesIO: An in-memory Excel file containing the analysis report.
    """
    try:
        # Step 1: Read the Excel file, telling pandas the first two rows are the header.
        # This creates a MultiIndex for the columns.
        df = pd.read_excel(input_file, header=[0, 1])

        # Step 2: Clean and flatten the multi-level column headers.
        # e.g., ('BCS401', 'IA') becomes 'BCS401_IA'
        # e.g., ('Class', 'Unnamed: ...') becomes 'Class'
        new_cols = []
        for col in df.columns:
            if 'Unnamed' in str(col[1]):
                # This handles single-level headers like 'USN', 'Name', 'Class'
                new_cols.append(col[0])
            else:
                # This joins multi-level headers like ('BCS401', 'Pass/Fail')
                new_cols.append(f"{col[0]}_{col[1]}")
        
        df.columns = new_cols

    except Exception as e:
        raise ValueError(f"Could not read the Excel file. Please ensure it has the correct two-level header format. Error: {e}")

    # --- 1. Analyze Pass Percentage for Each Subject ---
    analysis_data = []
    total_students = len(df)

    # Find all columns that represent a subject's pass/fail status
    pass_fail_columns = [col for col in df.columns if col.endswith('_Pass/Fail')]

    if not pass_fail_columns:
        raise ValueError("Could not find any 'Pass/Fail' columns. Please check the Excel file headers.")

    for pf_col in pass_fail_columns:
        # Extract subject code from the column name (e.g., 'BCS401_Pass/Fail' -> 'BCS401')
        subject_code = pf_col.split('_')[0]
        
        pass_count = (df[pf_col] == 'P').sum()
        pass_percentage = (pass_count / total_students) * 100 if total_students > 0 else 0
        
        analysis_data.append({
            "Subject": subject_code,
            "Total Students": total_students,
            "Pass Count": pass_count,
            "Pass Percentage": f"{pass_percentage:.2f}%"
        })

    pass_percentage_df = pd.DataFrame(analysis_data)
    pass_percentage_df['Pass Percentage (Numeric)'] = pass_percentage_df['Pass Percentage'].str.replace('%', '').astype(float)

    # --- 2. Analyze Class Distribution ---
    # This part will now work because the 'Class' column is correctly identified.
    class_distribution = df['Class'].value_counts().reset_index()
    class_distribution.columns = ['Class', 'Number of Students']

    # --- 3. Create Charts in Memory (No changes needed here) ---
    # Bar Chart for Pass Percentage
    plt.figure(figsize=(10, 6))
    bars = plt.bar(pass_percentage_df['Subject'], pass_percentage_df['Pass Percentage (Numeric)'], color='skyblue')
    plt.title('Pass Percentage per Subject', fontsize=16)
    plt.ylabel('Pass Percentage (%)', fontsize=12)
    plt.xlabel('Subject', fontsize=12)
    plt.xticks(rotation=45, ha='right')
    plt.ylim(0, 105)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2.0, yval + 1, f'{yval:.1f}%', ha='center', va='bottom')
    plt.tight_layout()
    bar_chart_buffer = BytesIO()
    plt.savefig(bar_chart_buffer, format='png')
    plt.close()

    # Pie Chart for Class Distribution
    plt.figure(figsize=(8, 8))
    plt.pie(
        class_distribution['Number of Students'],
        labels=class_distribution['Class'],
        autopct='%1.1f%%',
        startangle=140,
        colors=['#66b3ff','#ff9999','#99ff99','#ffcc99']
    )
    plt.title('Overall Class Distribution', fontsize=16)
    plt.axis('equal')
    pie_chart_buffer = BytesIO()
    plt.savefig(pie_chart_buffer, format='png')
    plt.close()

    # --- 4. Write Everything to an In-Memory Excel File (No changes needed here) ---
    output_buffer = BytesIO()
    with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
        pass_percentage_df[['Subject', 'Total Students', 'Pass Count', 'Pass Percentage']].to_excel(
            writer, sheet_name='Dashboard', startrow=1, index=False
        )
        class_distribution.to_excel(
            writer, sheet_name='Dashboard', startrow=1, startcol=6, index=False
        )

        workbook = writer.book
        worksheet = writer.sheets['Dashboard']
        worksheet['A1'] = "Subject Pass/Fail Analysis"
        worksheet['G1'] = "Class Distribution"

        from openpyxl.drawing.image import Image
        bar_chart_img = Image(bar_chart_buffer)
        worksheet.add_image(bar_chart_img, 'A10')
        pie_chart_img = Image(pie_chart_buffer)
        worksheet.add_image(pie_chart_img, 'J10')

        # We will write the cleaned data back to the report
        df.to_excel(writer, sheet_name='Raw Data', index=False)
    
    output_buffer.seek(0)
    return output_buffer