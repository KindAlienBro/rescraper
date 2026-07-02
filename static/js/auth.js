document.addEventListener('DOMContentLoaded', () => {
    const authOverlay = document.getElementById('auth-overlay');
    const mainDashboard = document.getElementById('main-dashboard');
    const authContainer = document.getElementById('auth-container');
    const btnLogin = document.getElementById('btn-show-login');
    const btnSignup = document.getElementById('btn-show-signup');
    const authHeaderP = document.querySelector('.auth-header p');

    // Forms
    const loginForm = document.getElementById('login-form');
    const signupForm = document.getElementById('signup-form');
    const loginMsg = document.getElementById('login-msg');
    const signupMsg = document.getElementById('signup-msg');

    // Check Login State
    const isLoggedIn = localStorage.getItem('vorniity_logged_in');
    
    if (isLoggedIn === 'true') {
        authOverlay.classList.add('hidden');
        mainDashboard.classList.remove('hidden');
    } else {
        authOverlay.classList.remove('hidden');
        mainDashboard.classList.add('hidden');
    }

    // Toggle Slider Logic
    btnLogin.addEventListener('click', () => {
        authContainer.classList.remove('signup-mode');
        btnLogin.classList.add('active');
        btnSignup.classList.remove('active');
        authHeaderP.textContent = "Welcome back, please sign in below.";
        loginMsg.textContent = "";
        signupMsg.textContent = "";
    });

    btnSignup.addEventListener('click', () => {
        authContainer.classList.add('signup-mode');
        btnSignup.classList.add('active');
        btnLogin.classList.remove('active');
        authHeaderP.textContent = "Create your account to get started.";
        loginMsg.textContent = "";
        signupMsg.textContent = "";
    });

    // Helper to get API URL
    const getApiUrl = () => {
        // Find the API array from script.js if possible, else fallback
        return window.API_URLS ? window.API_URLS[0] : 'http://localhost:5000';
    };

    // Login Submit
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        loginMsg.textContent = "Logging in...";
        loginMsg.style.color = "var(--text-secondary)";

        const email = document.getElementById('login-email').value.trim();
        const password = document.getElementById('login-password').value;

        try {
            const res = await fetch(getApiUrl() + '/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            const data = await res.json();

            if (!res.ok) throw new Error(data.message || 'Login failed');

            // Success
            loginMsg.textContent = "Success! Redirecting...";
            loginMsg.style.color = "var(--success)";
            localStorage.setItem('vorniity_logged_in', 'true');
            localStorage.setItem('vorniity_user', JSON.stringify(data.user));

            setTimeout(() => {
                authOverlay.style.opacity = '0';
                setTimeout(() => {
                    authOverlay.classList.add('hidden');
                    mainDashboard.classList.remove('hidden');
                    // Trigger a re-render/fetch in dashboard if needed
                }, 500);
            }, 800);

        } catch (err) {
            loginMsg.textContent = err.message;
            loginMsg.style.color = "var(--error)";
        }
    });

    // Signup Submit
    signupForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const name = document.getElementById('signup-name').value.trim();
        const college = document.getElementById('signup-college').value.trim();
        const email = document.getElementById('signup-email').value.trim();
        const phone = document.getElementById('signup-phone').value.trim();
        const password = document.getElementById('signup-password').value;
        const confirmPass = document.getElementById('signup-confirm').value;

        if (password !== confirmPass) {
            signupMsg.textContent = "Passwords do not match!";
            signupMsg.style.color = "var(--error)";
            return;
        }

        signupMsg.textContent = "Creating account...";
        signupMsg.style.color = "var(--text-secondary)";

        try {
            const res = await fetch(getApiUrl() + '/api/auth/signup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, college, email, phone, password })
            });
            const data = await res.json();

            if (!res.ok) throw new Error(data.message || 'Signup failed');

            // Success
            signupMsg.textContent = "Account created successfully! Please login.";
            signupMsg.style.color = "var(--success)";
            signupForm.reset();
            
            setTimeout(() => {
                btnLogin.click(); // Switch to login
            }, 2000);

        } catch (err) {
            signupMsg.textContent = err.message;
            signupMsg.style.color = "var(--error)";
        }
    });
});
