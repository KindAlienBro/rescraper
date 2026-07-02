document.addEventListener('DOMContentLoaded', () => {

    // --- Navigation & Layout ---
    const navItems = {
        'OVERVIEW': { el: document.getElementById('nav-overview'), section: document.getElementById('overview-section'), title: 'Overview' },
        'SCRAPE': { el: document.getElementById('nav-live-scrape'), section: document.getElementById('scrape-section'), title: 'Live Scraper' },
        'ARCHIVE': { el: document.getElementById('nav-db-archive'), section: document.getElementById('results-container'), title: 'Student Database' },
        'CLASSES': { el: document.getElementById('nav-classes'), section: document.getElementById('classes-section'), title: 'Manage Classes' },
        'HISTORY': { el: document.getElementById('nav-history'), section: document.getElementById('history-section'), title: 'Scrape History' },
        'SETTINGS': { el: document.getElementById('nav-settings'), section: document.getElementById('settings-section'), title: 'Settings' }
    };

    const pageTitle = document.getElementById('page-title');
    let currentMode = 'OVERVIEW';

    function switchView(mode) {
        if (currentMode === mode && mode !== 'ARCHIVE' && mode !== 'CLASSES') return;

        // Remove active class and hide sections
        Object.values(navItems).forEach(item => {
            item.el.classList.remove('active');
            item.section.classList.add('hidden');
        });

        // Set new active class and show section
        navItems[mode].el.classList.add('active');
        navItems[mode].section.classList.remove('hidden');
        pageTitle.textContent = navItems[mode].title;
        currentMode = mode;

        // Trigger view-specific logic
        if (mode === 'OVERVIEW') fetchOverviewStats();
        if (mode === 'ARCHIVE') loadArchive();
        if (mode === 'CLASSES') fetchClasses();
        if (mode === 'HISTORY') fetchScrapeHistory();
        if (mode === 'SETTINGS') fetchCredits();
    }

    // Attach click listeners to nav items
    Object.keys(navItems).forEach(key => {
        navItems[key].el.addEventListener('click', () => {
            switchView(key);
            closeMobileSidebar(); // Close sidebar on mobile when navigating
        });
    });

    // --- Mobile Sidebar Logic ---
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const sidebar = document.querySelector('.sidebar');
    const sidebarOverlay = document.getElementById('sidebar-overlay');

    function openMobileSidebar() {
        if (sidebar && sidebarOverlay) {
            sidebar.classList.add('sidebar-open');
            sidebarOverlay.classList.add('visible');
            sidebarOverlay.classList.remove('hidden');
        }
    }

    function closeMobileSidebar() {
        if (sidebar && sidebarOverlay) {
            sidebar.classList.remove('sidebar-open');
            sidebarOverlay.classList.remove('visible');
            setTimeout(() => sidebarOverlay.classList.add('hidden'), 300); // Wait for transition
        }
    }

    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', openMobileSidebar);
    }
    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', closeMobileSidebar);
    }

    // --- State ---
    let resultsData = [];
    let currentFilteredData = [];

    // --- Overview Logic ---
    async function fetchOverviewStats() {
        try {
            const res = await fetch(API_URLS[0] + '/api/stats');
            const data = await res.json();
            document.getElementById('stat-students').textContent = data.total_students || 0;
            document.getElementById('stat-classes').textContent = data.total_classes || 0;
        } catch (err) {
            console.error("Failed to fetch stats", err);
        }
    }

    // --- Archive Logic ---
    async function loadArchive() {
        const grid = document.getElementById('student-grid');
        const badge = document.getElementById('total-count-badge');

        document.getElementById('results-title').textContent = 'Student Profiles';
        grid.innerHTML = '<div class="spinner"></div><p class="status-text" style="grid-column:1/-1; text-align:center;">Fetching database...</p>';
        badge.textContent = '...';

        try {
            const res = await fetch(API_URLS[0] + '/api/students/all');
            if (!res.ok) throw new Error("Failed to fetch archive");
            const data = await res.json();

            resultsData = data;
            currentFilteredData = [...resultsData];
            applyFilters();
        } catch (err) {
            grid.innerHTML = `<p class="status-text" style="color:var(--error); grid-column:1/-1; text-align:center;">Error: ${err.message}</p>`;
        }
    }

    // --- Distributed Scrape Orchestration Logic ---
    const API_URLS = [
        'https://vorniity-rescraper-api.onrender.com',
        'https://kindalien-vorniity-rescraper-api.hf.space'
    ];

    function generateUsnList(start, end) {
        const list = [];
        try {
            const prefix = start.slice(0, -3);
            if (prefix !== end.slice(0, -3)) return [];
            const startNum = parseInt(start.slice(-3), 10);
            const endNum = parseInt(end.slice(-3), 10);
            for (let i = startNum; i <= endNum; i++) {
                list.push(`${prefix}${i.toString().padStart(3, '0')}`);
            }
        } catch (e) { }
        return list;
    }

    let currentSkippedUsns = []; // Stores {usn: "...", reason: "..."}

    const scrapeForm = document.getElementById('usn-form');
    const fetchBtn = document.getElementById('fetch-btn');
    const loader = document.getElementById('loader');
    const statusMsg = document.getElementById('status-message');
    const progContainer = document.getElementById('progress-container');
    const progFill = document.getElementById('progress-fill');
    const progCount = document.getElementById('progress-count');
    const progPercent = document.getElementById('progress-percent');
    const progSpeed = document.getElementById('progress-speed');

    if (scrapeForm) {
        scrapeForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const url = document.getElementById('vtu-url').value;
            const start = document.getElementById('start-usn').value.toUpperCase();
            const end = document.getElementById('end-usn').value.toUpperCase();

            const allUsns = generateUsnList(start, end);
            if (allUsns.length === 0) {
                alert("Invalid USN range");
                return;
            }

            // UI Reset
            resultsData = [];
            currentFilteredData = [];
            currentSkippedUsns = []; // Reset skipped tracker
            if (btnDownloadSkipped) btnDownloadSkipped.classList.add('hidden');
            loader.classList.remove('hidden');
            progContainer.classList.remove('hidden');
            fetchBtn.disabled = true;
            statusMsg.textContent = "Starting distributed scrape...";
            progFill.style.width = '0%';
            progCount.textContent = `0 / ${allUsns.length}`;
            if (progSpeed) progSpeed.textContent = '0 USNs/s';
            progPercent.textContent = '0%';
            scrapeForm.dataset.startTime = Date.now();

            // Chunking
            const CHUNK_SIZE = 2;
            const chunks = [];
            for (let i = 0; i < allUsns.length; i += CHUNK_SIZE) {
                chunks.push(allUsns.slice(i, i + CHUNK_SIZE));
            }

            let completedUsns = 0;
            const totalUsns = allUsns.length;
            let currentApiIndex = 0;

            const processChunk = async (chunk, retryCount = 0) => {
                // Select an API via Round-Robin
                const apiUrl = API_URLS[currentApiIndex % API_URLS.length];
                currentApiIndex++;

                try {
                    statusMsg.textContent = `Scraping: ${chunk[0]}...`;
                    const res = await fetch(`${apiUrl}/api/scrape_chunk`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ usns: chunk, vtu_url: url })
                    });

                    if (!res.ok) throw new Error(`HTTP Error ${res.status}`);

                    const data = await res.json();

                    if (data.success && data.results) {
                        resultsData = resultsData.concat(data.results);
                    }
                    if (data.skipped && data.skipped.length > 0) {
                        currentSkippedUsns = currentSkippedUsns.concat(data.skipped);
                    }

                    completedUsns += chunk.length;

                    // Update Progress UI
                    const perc = Math.round((completedUsns / totalUsns) * 100);
                    progFill.style.width = `${perc}%`;
                    progCount.textContent = `${completedUsns} / ${totalUsns}`;
                    progPercent.textContent = `${perc}%`;

                    const timeElapsed = (Date.now() - scrapeForm.dataset.startTime) / 1000;
                    if (timeElapsed > 0) {
                        const speedVal = completedUsns / timeElapsed;
                        if (speedVal < 1 && speedVal > 0) {
                            const secsPerUsn = (1 / speedVal).toFixed(1);
                            if (progSpeed) progSpeed.textContent = `${secsPerUsn}s / USN`;
                        } else {
                            if (progSpeed) progSpeed.textContent = `${speedVal.toFixed(1)} USNs/s`;
                        }
                    } else {
                        if (progSpeed) progSpeed.textContent = `0 USNs/s`;
                    }

                } catch (err) {
                    console.error(`Chunk failed on ${apiUrl}:`, err);
                    if (retryCount < 2) {
                        console.log(`Retrying chunk (attempt ${retryCount + 1})...`);
                        await processChunk(chunk, retryCount + 1);
                    } else {
                        // Max retries reached, still consider it processed to avoid infinite hang
                        completedUsns += chunk.length;
                    }
                }
            };

            // Process maximum 3 chunks concurrently across the APIs
            const CONCURRENCY_LIMIT = Math.min(3, API_URLS.length * 2);
            let chunkIndex = 0;

            const worker = async () => {
                while (chunkIndex < chunks.length) {
                    const chunk = chunks[chunkIndex++];
                    await processChunk(chunk);
                }
            };

            const workers = [];
            for (let i = 0; i < CONCURRENCY_LIMIT; i++) {
                workers.push(worker());
            }

            await Promise.all(workers);

            // Completion
            const timeTaken = ((Date.now() - scrapeForm.dataset.startTime) / 1000).toFixed(1);
            statusMsg.textContent = `Distributed scrape completed in ${timeTaken}s!`;
            statusMsg.style.color = "var(--success)";

            // Save Scrape History
            try {
                const apiToSave = API_URLS[0]; // Just use the first API for saving state
                await fetch(`${apiToSave}/api/history/save`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        start_usn: start,
                        end_usn: end,
                        total_usns: totalUsns,
                        completed: completedUsns,
                        time_taken: timeTaken,
                        status: 'Completed'
                    })
                });
                fetchScrapeHistory(); // Refresh history view
            } catch (err) {
                console.error("Failed to save history", err);
            }

            currentFilteredData = [...resultsData];
            fetchOverviewStats();
            applyFilters();

            setTimeout(() => {
                fetchBtn.disabled = false;
                loader.classList.add('hidden');
                document.getElementById('results-title').textContent = 'Live Scrape Results';

                // Show PDF Download button if there are skipped USNs
                if (currentSkippedUsns.length > 0 && btnDownloadSkipped) {
                    btnDownloadSkipped.classList.remove('hidden');
                }

                navItems['SCRAPE'].section.classList.add('hidden');
                navItems['ARCHIVE'].section.classList.remove('hidden');
            }, 2000);
        });
    }

    // PDF Generation for Skipped USNs
    const btnDownloadSkipped = document.getElementById('btn-download-skipped');
    if (btnDownloadSkipped) {
        btnDownloadSkipped.addEventListener('click', () => {
            if (currentSkippedUsns.length === 0) {
                alert("No skipped USNs to report!");
                return;
            }

            const { jsPDF } = window.jspdf;
            const doc = new jsPDF();

            doc.setFontSize(16);
            doc.text('Skipped USNs Report', 14, 20);

            doc.setFontSize(10);
            doc.setTextColor(100);
            doc.text(`Generated on: ${new Date().toLocaleString()}`, 14, 28);

            const tableData = currentSkippedUsns.map(item => [item.usn, item.reason]);

            doc.autoTable({
                startY: 35,
                head: [['USN', 'Reason for Failure']],
                body: tableData,
                theme: 'striped',
                headStyles: { fillColor: [43, 62, 235] },
                styles: { fontSize: 10, cellPadding: 3 }
            });

            doc.save('Skipped_USNs_Report.pdf');
        });
    }

    // --- Grid Rendering & Filters ---
    const studentGrid = document.getElementById('student-grid');
    const badge = document.getElementById('total-count-badge');
    const searchInput = document.getElementById('search-input');
    const statusFilter = document.getElementById('status-filter');

    if (searchInput) {
        searchInput.addEventListener('input', applyFilters);
        statusFilter.addEventListener('change', applyFilters);
    }

    function applyFilters() {
        const q = (searchInput.value || '').toLowerCase();
        const stat = (statusFilter.value || 'ALL');

        currentFilteredData = resultsData.filter(st => {
            const matchName = (st.student_name || '').toLowerCase().includes(q);
            const matchUSN = (st.usn || '').toLowerCase().includes(q);
            const matchStatus = (stat === 'ALL') || ((st.class || '') === stat);
            return (matchName || matchUSN) && matchStatus;
        });

        renderStudentGrid(currentFilteredData);
    }

    function renderStudentGrid(data) {
        badge.textContent = `${data.length} Students`;

        if (data.length === 0) {
            studentGrid.innerHTML = `<p class="status-text" style="grid-column: 1/-1; text-align:center;">No profiles match your filter.</p>`;
            return;
        }

        studentGrid.innerHTML = data.map(st => {
            const sgpa = st.sgpa || 'N/A';
            const statusClass = st.class ? st.class.toLowerCase() : 'fail';
            const safeName = (st.student_name || '').replace(/'/g, "\\'");

            return `
            <div class="profile-card" onclick="openHistoryModal('${st.usn}', '${safeName}')">
                <div class="profile-header">
                    <div class="profile-info">
                        <h3>${st.student_name || 'Unknown'}</h3>
                        <span class="usn">${st.usn}</span>
                    </div>
                    <div style="display:flex; gap:8px; align-items:center;">
                        <span class="status-badge ${statusClass}">${st.class || 'N/A'}</span>
                        <button onclick="deleteStudent(event, '${st.usn}')" class="icon-btn" style="color:var(--error); padding:2px;"><i class="ph ph-trash"></i></button>
                    </div>
                </div>
                <div class="profile-stats">
                    <div class="stat-item">
                        <span class="label">SGPA</span>
                        <span class="value">${sgpa}</span>
                    </div>
                    <div class="stat-item">
                        <span class="label">Total</span>
                        <span class="value">${st.total_marks || 0}</span>
                    </div>
                    <div class="stat-item">
                        <span class="label">Result</span>
                        <span class="value">${st.percentage || '-'}</span>
                    </div>
                </div>
            </div>`;
        }).join('');
    }

    // --- Modal Logic ---
    const historyModal = document.getElementById('history-modal');
    const closeModalBtn = document.getElementById('close-modal');

    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', () => historyModal.classList.add('hidden'));
    }

    window.openHistoryModal = async (usn, name) => {
        document.getElementById('modal-student-name').textContent = name;
        document.getElementById('modal-student-usn').textContent = usn;
        const tabsContainer = document.getElementById('history-tabs');
        const contentContainer = document.getElementById('history-tab-content');

        tabsContainer.innerHTML = '';
        contentContainer.innerHTML = '<div class="spinner"></div>';
        historyModal.classList.remove('hidden');

        try {
            const res = await fetch(`${API_URLS[0]}/api/student/${usn}`);
            if (!res.ok) throw new Error("Failed to load history");
            const historyData = await res.json();

            if (historyData.length === 0) {
                contentContainer.innerHTML = '<p class="text-muted">No cached history found.</p>';
                return;
            }

            // Render Tabs
            tabsContainer.innerHTML = historyData.map((d, i) =>
                `<button class="modal-tab ${i === 0 ? 'active' : ''}" onclick="switchModalTab(${i}, this)">Sem ${d.semester}</button>`
            ).join('');

            // Store data globally for tab switching
            window.currentHistoryData = historyData;

            // Render first tab content
            renderModalContent(historyData[0]);

        } catch (err) {
            contentContainer.innerHTML = `<p class="form-msg" style="color:var(--error);">${err.message}</p>`;
        }
    };

    window.switchModalTab = (index, tabEl) => {
        document.querySelectorAll('.modal-tab').forEach(t => t.classList.remove('active'));
        tabEl.classList.add('active');
        if (window.currentHistoryData && window.currentHistoryData[index]) {
            renderModalContent(window.currentHistoryData[index]);
        }
    };

    function renderModalContent(data) {
        const contentContainer = document.getElementById('history-tab-content');
        let html = `
            <div class="semester-summary">
                <div>SGPA: ${data.sgpa || 'N/A'}</div>
                <div>Total Marks: ${data.total_marks || 0}</div>
                <div>Status: ${data.class || 'N/A'}</div>
            </div>
            
            <div class="semester-result">
                <div class="subject-grid-header">
                    <div>Subject</div>
                    <div>Int</div>
                    <div>Ext</div>
                    <div>Total</div>
                    <div>Result</div>
                </div>
        `;

        if (data.subjects && data.subjects.length > 0) {
            data.subjects.forEach(sub => {
                html += `
                <div class="subject-row">
                    <div style="font-weight:500; color:var(--text-primary);">${sub.subject_name || sub.subject_code} <br><span class="text-muted" style="font-size:11px; font-family:var(--font-mono);">${sub.subject_code}</span></div>
                    <div>${sub.internal_marks}</div>
                    <div>${sub.external_marks}</div>
                    <div style="font-weight:600;">${sub.total}</div>
                    <div style="color:${sub.result === 'P' ? 'var(--success)' : 'var(--error)'}; font-weight:600;">${sub.result}</div>
                </div>`;
            });
        } else {
            html += `<div class="subject-row" style="grid-column:1/-1;">No subject data.</div>`;
        }

        html += `</div>`;
        contentContainer.innerHTML = html;
    }

    // --- Excel Export ---
    const excelBtn = document.getElementById('download-excel');
    if (excelBtn) {
        excelBtn.addEventListener('click', async () => {
            if (currentFilteredData.length === 0) {
                alert("No data to export.");
                return;
            }
            const originalText = excelBtn.innerHTML;
            excelBtn.innerHTML = 'Exporting...';
            excelBtn.disabled = true;

            try {
                const response = await fetch(API_URLS[0] + '/download/excel', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(currentFilteredData)
                });
                if (!response.ok) throw new Error('Failed to generate Excel.');

                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = 'vtu_results.xlsx';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                a.remove();
            } catch (error) {
                alert(`Error: ${error.message}`);
            } finally {
                excelBtn.innerHTML = originalText;
                excelBtn.disabled = false;
            }
        });
    }

    // --- Classes Logic ---
    const classesGrid = document.getElementById('classes-grid');
    async function fetchClasses() {
        try {
            const res = await fetch(API_URLS[0] + '/api/classes');
            const data = await res.json();
            document.getElementById('total-classes-badge').textContent = data.length;

            if (data.length === 0) {
                classesGrid.innerHTML = '<p class="text-muted" style="text-align:center; padding:16px;">No classes created yet.</p>';
                return;
            }

            classesGrid.innerHTML = data.map(cls => `
                <div class="subject-item clickable" onclick="loadClassStudents(${cls.id}, '${cls.name}')">
                    <div class="card-header-flex" style="margin-bottom:8px;">
                        <h3 style="margin:0; font-size:15px; color:var(--text-primary); text-transform:none;">${cls.name}</h3>
                        <div style="display:flex; gap:8px;">
                            <button onclick="openEditClassModal(event, ${cls.id}, '${cls.name}', '${cls.start_usn}', '${cls.end_usn}')" class="badge badge-subtle" style="border:none; cursor:pointer;">Edit</button>
                            <button onclick="deleteClass(event, ${cls.id})" class="badge" style="background:var(--error); color:#fff; border:none; cursor:pointer;">Delete</button>
                        </div>
                    </div>
                    <span class="text-muted" style="font-family:var(--font-mono); font-size:12px;">${cls.start_usn} &rarr; ${cls.end_usn}</span>
                </div>
            `).join('');
        } catch (err) {
            classesGrid.innerHTML = `<p class="form-msg" style="color:var(--error);">Error: ${err.message}</p>`;
        }
    }

    window.deleteStudent = async (e, usn) => {
        e.stopPropagation();
        if (!confirm("Are you sure you want to delete this student from the database?")) return;
        try {
            const res = await fetch(`${API_URLS[0]}/api/student/${usn}`, { method: 'DELETE' });
            if (!res.ok) throw new Error("Failed to delete student");
            // Remove from resultsData
            resultsData = resultsData.filter(st => st.usn !== usn);
            applyFilters();
        } catch (err) {
            alert(err.message);
        }
    };

    window.loadClassStudents = async (id, name) => {
        // Show Results view without changing nav active state
        navItems['CLASSES'].section.classList.add('hidden');
        navItems['ARCHIVE'].section.classList.remove('hidden');
        document.getElementById('results-title').textContent = `Class: ${name}`;

        studentGrid.innerHTML = `<div class="spinner"></div>`;
        document.getElementById('total-count-badge').textContent = '...';

        try {
            const res = await fetch(`${API_URLS[0]}/api/class/${id}/students`);
            if (!res.ok) throw new Error("Failed to fetch class");
            resultsData = await res.json();
            currentFilteredData = [...resultsData];
            applyFilters();
        } catch (err) {
            studentGrid.innerHTML = `<p class="form-msg" style="color:var(--error);">${err.message}</p>`;
        }
    };

    window.deleteClass = async (e, id) => {
        e.stopPropagation();
        if (!confirm("Delete this class?")) return;
        try {
            await fetch(`${API_URLS[0]}/api/classes/${id}`, { method: 'DELETE' });
            fetchClasses();
        } catch (err) { }
    }

    const addClassForm = document.getElementById('add-class-form');
    if (addClassForm) {
        addClassForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const msg = document.getElementById('class-status-msg');
            msg.textContent = 'Saving...';
            msg.style.color = 'var(--text-secondary)';

            const payload = {
                name: document.getElementById('new-class-name').value.trim(),
                start_usn: document.getElementById('new-class-start').value.trim(),
                end_usn: document.getElementById('new-class-end').value.trim()
            };

            try {
                const res = await fetch(API_URLS[0] + '/api/classes', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (!res.ok) throw new Error("Failed to create class");

                msg.textContent = 'Class created!';
                msg.style.color = 'var(--success)';
                addClassForm.reset();
                fetchClasses();
                setTimeout(() => msg.textContent = '', 3000);
            } catch (err) {
                msg.textContent = err.message;
                msg.style.color = 'var(--error)';
            }
        });
    }

    // --- Settings / Credits Logic ---
    const subjectsGrid = document.getElementById('subjects-grid');
    async function fetchCredits() {
        try {
            const res = await fetch(API_URLS[0] + '/api/credits');
            const data = await res.json();
            const ObjectKeys = Object.keys(data).sort();
            document.getElementById('total-subjects-badge').textContent = ObjectKeys.length;

            if (ObjectKeys.length === 0) {
                subjectsGrid.innerHTML = '<p class="text-muted" style="text-align:center; padding:16px;">No subjects found.</p>';
                return;
            }

            subjectsGrid.innerHTML = ObjectKeys.map(code => `
                <div class="subject-item" style="flex-direction:row; justify-content:space-between; align-items:center;">
                    <div style="display:flex; align-items:center; gap:12px;">
                        <span style="font-family:var(--font-mono); font-weight:600; font-size:14px;">${code}</span>
                        <span class="badge badge-subtle">${data[code]} CR</span>
                    </div>
                    <button onclick="deleteCredit(event, '${code}')" class="icon-btn" style="color:var(--error);"><i class="ph ph-trash"></i></button>
                </div>
            `).join('');
        } catch (err) {
            subjectsGrid.innerHTML = `<p class="form-msg" style="color:var(--error);">Error: ${err.message}</p>`;
        }
    }

    window.deleteCredit = async (e, code) => {
        e.stopPropagation();
        if (!confirm(`Delete subject ${code}?`)) return;
        try {
            await fetch(`${API_URLS[0]}/api/credits/${code}`, { method: 'DELETE' });
            fetchCredits();
        } catch (err) {
            alert(err.message);
        }
    };

    const editClassModal = document.getElementById('edit-class-modal');
    document.querySelector('.close-edit-class')?.addEventListener('click', () => {
        editClassModal.classList.add('hidden');
    });

    window.openEditClassModal = (e, id, name, start, end) => {
        e.stopPropagation();
        document.getElementById('edit-class-id').value = id;
        document.getElementById('edit-class-name').value = name;
        document.getElementById('edit-class-start').value = start;
        document.getElementById('edit-class-end').value = end;
        document.getElementById('edit-class-status-msg').textContent = '';
        editClassModal.classList.remove('hidden');
    };

    const editClassForm = document.getElementById('edit-class-form');
    if (editClassForm) {
        editClassForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const msg = document.getElementById('edit-class-status-msg');
            msg.textContent = 'Updating...';

            const id = document.getElementById('edit-class-id').value;
            const payload = {
                name: document.getElementById('edit-class-name').value.trim(),
                start_usn: document.getElementById('edit-class-start').value.trim(),
                end_usn: document.getElementById('edit-class-end').value.trim()
            };

            try {
                const res = await fetch(`${API_URLS[0]}/api/classes/${id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (!res.ok) throw new Error("Failed to update class");

                msg.textContent = 'Class updated!';
                msg.style.color = 'var(--success)';
                fetchClasses();
                setTimeout(() => editClassModal.classList.add('hidden'), 1000);
            } catch (err) {
                msg.textContent = err.message;
                msg.style.color = 'var(--error)';
            }
        });
    }

    const addCreditForm = document.getElementById('add-credit-form');
    if (addCreditForm) {
        addCreditForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const msg = document.getElementById('credit-status-msg');
            const code = document.getElementById('new-subject-code').value.trim();
            const credits = document.getElementById('new-subject-credits').value;

            msg.textContent = 'Saving...';
            msg.style.color = 'var(--text-secondary)';

            try {
                const res = await fetch(API_URLS[0] + '/api/credits', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ subject_code: code, credits: parseInt(credits) })
                });
                if (!res.ok) throw new Error("Failed to save");

                msg.textContent = 'Subject saved!';
                msg.style.color = 'var(--success)';
                addCreditForm.reset();
                fetchCredits();
                setTimeout(() => msg.textContent = '', 3000);
            } catch (err) {
                msg.textContent = err.message;
                msg.style.color = 'var(--error)';
            }
        });
    }

    // --- Clear Database Logic ---
    const clearDbBtn = document.getElementById('clear-db-btn');
    if (clearDbBtn) {
        clearDbBtn.addEventListener('click', async () => {
            const msg = document.getElementById('clear-db-msg');
            const confirmWipe = confirm("WARNING: This will permanently delete ALL scraped student data, results, and scrape history.\n\nYour saved classes and subjects will NOT be deleted.\n\nAre you absolutely sure you want to proceed?");

            if (!confirmWipe) return;

            clearDbBtn.disabled = true;
            clearDbBtn.textContent = 'Clearing...';
            msg.textContent = '';

            try {
                const res = await fetch(API_URLS[0] + '/api/database/clear', {
                    method: 'DELETE'
                });
                const data = await res.json();

                if (!res.ok) throw new Error(data.message || "Failed to clear database");

                msg.textContent = 'Database cleared successfully!';
                msg.style.color = 'var(--success)';

                // Refresh data globally
                resultsData = [];
                currentFilteredData = [];
                fetchOverviewStats();

            } catch (err) {
                msg.textContent = err.message;
                msg.style.color = 'var(--error)';
            } finally {
                clearDbBtn.disabled = false;
                clearDbBtn.textContent = 'Clear Database';
            }
        });
    }

    // Initialize default view
    fetchOverviewStats();

    // --- Scrape History Logic ---
    window.fetchScrapeHistory = async function () {
        const grid = document.getElementById('history-grid');
        grid.innerHTML = '<div class="spinner"></div>';
        try {
            const res = await fetch(API_URLS[0] + '/api/history/scrapes');
            if (!res.ok) throw new Error("Failed to fetch scrape history");
            const data = await res.json();

            if (data.length === 0) {
                grid.innerHTML = '<p class="text-muted" style="text-align:center; padding: 20px; grid-column:1/-1;">No scrape history found.</p>';
                return;
            }

            grid.innerHTML = data.map(job => {
                const statusClass = job.status === 'completed' ? 'fcd' : (job.status === 'error' ? 'fail' : 'sc');
                const timeStr = job.time_taken ? `${job.time_taken.toFixed(1)}s` : '-';

                // Format in IST
                const dateObj = new Date(job.timestamp + "Z"); // Add Z to specify UTC input from SQLite
                const dateStr = dateObj.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });

                return `
                <div class="profile-card" style="cursor: default;">
                    <div class="profile-header">
                        <div class="profile-info">
                            <h3>${job.start_usn} to ${job.end_usn}</h3>
                            <span class="usn">${dateStr}</span>
                        </div>
                        <span class="status-badge ${statusClass}">${job.status.toUpperCase()}</span>
                    </div>
                    <div class="profile-stats">
                        <div class="stat-item">
                            <span class="label">Total USNs</span>
                            <span class="value">${job.total_usns}</span>
                        </div>
                        <div class="stat-item">
                            <span class="label">Completed</span>
                            <span class="value">${job.completed}</span>
                        </div>
                        <div class="stat-item">
                            <span class="label">Time</span>
                            <span class="value">${timeStr}</span>
                        </div>
                    </div>
                </div>`;
            }).join('');
        } catch (err) {
            grid.innerHTML = `<p class="status-text" style="color:var(--error); text-align:center; grid-column:1/-1;">Error: ${err.message}</p>`;
        }
    };

});