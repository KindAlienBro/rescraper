document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('usn-form');
    const fetchBtn = document.getElementById('fetch-btn');
    const loader = document.getElementById('loader');
    const statusMessage = document.getElementById('status-message');
    const resultsContainer = document.getElementById('results-container');
    const excelBtn = document.getElementById('download-excel');
    const pdfBtn = document.getElementById('download-pdf');
    const tableHead = document.querySelector('#results-table thead');
    const tableBody = document.querySelector('#results-table tbody');

    // This variable will store the detailed results from your scraper
    let resultsData = [];

    // --- Main Fetch Logic ---
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Reset UI for a new fetch
        resultsContainer.style.display = 'none';
        statusMessage.textContent = '';
        tableHead.innerHTML = '';
        tableBody.innerHTML = '';
        loader.style.display = 'block';
        fetchBtn.disabled = true;
        statusMessage.textContent = 'Fetching results... This can take a few moments.';
        statusMessage.style.color = 'blue';

        const formData = new FormData(form);
        const data = {
            vtu_url: formData.get('vtu_url'),
            start_usn: formData.get('start_usn'),
            end_usn: formData.get('end_usn')
        };

        try {
            const response = await fetch('/scrape', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'An unknown error occurred.');
            }

            resultsData = await response.json();
            
            // This is the function that builds the correct, multi-level table
            displayWideResults(resultsData); 

            statusMessage.textContent = `Successfully fetched ${resultsData.length} results.`;
            statusMessage.style.color = 'green';
            resultsContainer.style.display = 'block';

        } catch (error) {
            statusMessage.textContent = `Error: ${error.message}`;
            statusMessage.style.color = 'red';
        } finally {
            loader.style.display = 'none';
            fetchBtn.disabled = false;
        }
    });

    // --- THIS IS THE CORRECT TABLE-BUILDING FUNCTION ---
    function displayWideResults(data) {
        if (!data || data.length === 0) {
            statusMessage.textContent = 'No results found for the given range.';
            statusMessage.style.color = 'orange';
            return;
        }

        // Step 1: Find all unique subject codes from all students
        const allSubjects = new Set();
        data.forEach(student => {
            // It expects each student object to have an array called 'subjects'
            if (student.subjects && Array.isArray(student.subjects)) {
                // It correctly looks for 'subject_code' which your scraper provides
                student.subjects.forEach(subject => allSubjects.add(subject.subject_code));
            }
        });
        const subjectCodes = Array.from(allSubjects).sort();

        // Step 2: Build the complex two-row header
        tableHead.innerHTML = ''; // Clear any old header
        const headerRow1 = document.createElement('tr');
        const headerRow2 = document.createElement('tr');

        // USN and Name headers (span 2 rows)
        headerRow1.innerHTML = `<th rowspan="2">USN</th><th rowspan="2">Name</th>`;

        // Create main subject code headers in the first row
        subjectCodes.forEach(code => {
            const th = document.createElement('th');
            th.setAttribute('colspan', '4'); // Span 4 columns: IA, Ex, Total, Pass/Fail
            th.textContent = code;
            headerRow1.appendChild(th);

            // Create the sub-headers in the second row for each subject
            headerRow2.innerHTML += `<th>IA</th><th>Ex</th><th>Total</th><th>Pass/Fail</th>`;
        });
        
        // Create summary headers (span 2 rows)
        headerRow1.innerHTML += `<th rowspan="2">Subjects Failed</th><th rowspan="2">Subjects Absent</th>`;

        tableHead.appendChild(headerRow1);
        tableHead.appendChild(headerRow2);

        // Step 3: Build the table body with student data
        tableBody.innerHTML = ''; // Clear old data
        data.forEach(student => {
            const row = document.createElement('tr');
            
            // Add USN and Name
            row.innerHTML = `<td>${student.usn}</td><td>${student.student_name}</td>`;

            // Create a quick lookup map of the student's subjects by their code
            const studentSubjects = new Map(student.subjects.map(s => [s.subject_code, s]));
            
            let failedCount = 0;
            let absentCount = 0;

            // Loop through the master list of all subject codes to ensure columns align correctly
            subjectCodes.forEach(code => {
                const subject = studentSubjects.get(code);
                if (subject) {
                    // If the student has this subject, add their marks using the correct keys
                    row.innerHTML += `<td>${subject.internal_marks}</td><td>${subject.external_marks}</td><td>${subject.total}</td><td>${subject.result}</td>`;
                    // Calculate summary stats
                    if (subject.result === 'F') failedCount++;
                    if (subject.result === 'A') absentCount++;
                } else {
                    // If the student does not have this subject (e.g. an elective), add placeholder cells
                    row.innerHTML += `<td>-</td><td>-</td><td>-</td><td>-</td>`;
                }
            });

            // Add the final summary counts to the end of the row
            row.innerHTML += `<td>${failedCount}</td><td>${absentCount}</td>`;
            tableBody.appendChild(row);
        });
    }

    // --- Download Logic ---
    async function downloadFile(format) {
        if (resultsData.length === 0) {
            alert("No data available to download.");
            return;
        }

        statusMessage.textContent = `Generating ${format.toUpperCase()} file...`;
        statusMessage.style.color = 'blue';

        try {
            const response = await fetch(`/download/${format}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(resultsData)
            });

            if (!response.ok) {
                 const errorData = await response.json();
                throw new Error(errorData.error || `Failed to generate ${format}.`);
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `results.${format === 'excel' ? 'xlsx' : 'pdf'}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();
            statusMessage.textContent = 'Download complete!';
            statusMessage.style.color = 'green';

        } catch (error) {
            statusMessage.textContent = `Error: ${error.message}`;
            statusMessage.style.color = 'red';
        }
    }

    excelBtn.addEventListener('click', () => downloadFile('excel'));
    pdfBtn.addEventListener('click', () => downloadFile('pdf'));
});