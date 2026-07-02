document.addEventListener('DOMContentLoaded', () => {
    const authOverlay = document.getElementById('auth-overlay');
    const mainDashboard = document.getElementById('main-dashboard');
    
    const tabLogin = document.getElementById('tab-login');
    const tabSignup = document.getElementById('tab-signup');
    
    const loginForm = document.getElementById('login-form');
    const signupForm = document.getElementById('signup-form');
    
    const title = document.getElementById('auth-title');
    const subtitle = document.getElementById('auth-subtitle');
    
    const loginMsg = document.getElementById('login-message');
    const signupMsg = document.getElementById('signup-message');

    // ===== TABS LOGIC =====
    function setTab(isLogin) {
        if (isLogin) {
            tabLogin.classList.add('active');
            tabSignup.classList.remove('active');
            loginForm.classList.add('active');
            signupForm.classList.remove('active');
            title.textContent = 'Welcome back';
            subtitle.textContent = 'Enter your details to sign in to your account';
        } else {
            tabSignup.classList.add('active');
            tabLogin.classList.remove('active');
            signupForm.classList.add('active');
            loginForm.classList.remove('active');
            title.textContent = 'Create an account';
            subtitle.textContent = 'Join Vorniity and start scraping today';
        }
        loginMsg.textContent = "";
        signupMsg.textContent = "";
    }

    tabLogin.addEventListener('click', () => setTab(true));
    tabSignup.addEventListener('click', () => setTab(false));

    // ===== PASSWORD VISIBILITY =====
    document.querySelectorAll('.eye-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const input = btn.parentElement.querySelector('input');
            const icon = btn.querySelector('i');
            if (input.type === 'password') {
                input.type = 'text';
                icon.className = 'ph ph-eye-slash';
            } else {
                input.type = 'password';
                icon.className = 'ph ph-eye';
            }
        });
    });

    // ===== PASSWORD STRENGTH METER =====
    const signupPassword = document.getElementById('signup-password');
    const pBars = document.querySelectorAll('.p-bar');
    const pText = document.querySelector('.pwd-text');

    if (signupPassword) {
        signupPassword.addEventListener('input', () => {
            const val = signupPassword.value;
            let score = 0;

            if (val.length >= 6) score++;
            if (val.length >= 10) score++;
            if (/[A-Z]/.test(val) && /[a-z]/.test(val)) score++;
            if (/[0-9]/.test(val) && /[^a-zA-Z0-9]/.test(val)) score++;

            pBars.forEach((bar, i) => {
                bar.className = 'p-bar';
                if (i < score) {
                    bar.classList.add('active');
                    if (score <= 1) bar.classList.add('weak');
                    else if (score === 2) bar.classList.add('fair');
                    else if (score === 3) bar.classList.add('good');
                    else bar.classList.add('strong');
                }
            });

            const labels = ['', 'Weak', 'Fair', 'Good', 'Strong'];
            const colors = ['', '#ef4444', '#f59e0b', '#3b82f6', '#10b981'];
            
            if (val) {
                pText.textContent = labels[score] || 'Too short';
                pText.style.color = colors[score] || '#71717a';
            } else {
                pText.textContent = '';
            }
        });
    }

    // ===== CHECK LOGIN STATE =====
    const isLoggedIn = localStorage.getItem('vorniity_logged_in');
    const userStr = localStorage.getItem('vorniity_user');
    
    if (isLoggedIn === 'true') {
        authOverlay.classList.add('hidden');
        mainDashboard.classList.remove('hidden');
        
        if (userStr) {
            try {
                const user = JSON.parse(userStr);
                const nameSpan = document.getElementById('topbar-username');
                if (nameSpan && user.name) {
                    nameSpan.textContent = user.name;
                }
            } catch (e) {
                console.error("Error parsing user profile");
            }
        }
    } else {
        authOverlay.classList.remove('hidden');
        mainDashboard.classList.add('hidden');
    }
    
    // ===== LOGOUT LOGIC =====
    const logoutBtn = document.getElementById('nav-logout');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            localStorage.removeItem('vorniity_logged_in');
            localStorage.removeItem('vorniity_user');
            
            // Switch back to login view
            authOverlay.style.opacity = '1';
            authOverlay.classList.remove('hidden');
            mainDashboard.classList.add('hidden');
            setTab(true);
            loginForm.reset();
            signupForm.reset();
        });
    }

    // ===== API LOGIC =====
    const getApiUrl = () => {
        return window.API_URLS ? window.API_URLS[0] : 'http://localhost:5000';
    };

    function setLoading(btn, isLoading) {
        if (isLoading) {
            btn.classList.add('loading');
            btn.disabled = true;
        } else {
            btn.classList.remove('loading');
            btn.disabled = false;
        }
    }

    function showMessage(el, text, type) {
        el.textContent = text;
        if (type === 'error') el.style.color = 'var(--color-error)';
        else if (type === 'success') el.style.color = 'var(--color-success)';
        else el.style.color = 'var(--text-secondary)';
    }

    // Login Submission
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = loginForm.querySelector('.auth-btn-primary');
        setLoading(submitBtn, true);
        showMessage(loginMsg, 'Signing in...', 'info');

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

            showMessage(loginMsg, 'Success! Redirecting...', 'success');
            localStorage.setItem('vorniity_logged_in', 'true');
            localStorage.setItem('vorniity_user', JSON.stringify(data.user));

            setTimeout(() => {
                authOverlay.style.opacity = '0';
                setTimeout(() => {
                    authOverlay.classList.add('hidden');
                    mainDashboard.classList.remove('hidden');
                }, 500);
            }, 500);

        } catch (err) {
            showMessage(loginMsg, err.message, 'error');
            setLoading(submitBtn, false);
            submitBtn.style.animation = 'shake 0.4s ease';
            setTimeout(() => submitBtn.style.animation = '', 400);
        }
    });

    // Signup Submission
    signupForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const password = document.getElementById('signup-password').value;
        const confirmPass = document.getElementById('signup-confirm').value;

        if (password !== confirmPass) {
            showMessage(signupMsg, 'Passwords do not match', 'error');
            return;
        }

        const submitBtn = signupForm.querySelector('.auth-btn-primary');
        setLoading(submitBtn, true);
        showMessage(signupMsg, 'Creating account...', 'info');

        const payload = {
            name: document.getElementById('signup-name').value.trim(),
            college: document.getElementById('signup-college').value.trim(),
            email: document.getElementById('signup-email').value.trim(),
            phone: document.getElementById('signup-phone').value.trim(),
            password: password
        };

        try {
            const res = await fetch(getApiUrl() + '/api/auth/signup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();

            if (!res.ok) throw new Error(data.message || 'Signup failed');

            showMessage(signupMsg, 'Account created! Switching to login...', 'success');
            signupForm.reset();
            pBars.forEach(b => b.className = 'p-bar');
            pText.textContent = '';

            setTimeout(() => {
                setTab(true);
                setLoading(submitBtn, false);
            }, 1500);

        } catch (err) {
            showMessage(signupMsg, err.message, 'error');
            setLoading(submitBtn, false);
            submitBtn.style.animation = 'shake 0.4s ease';
            setTimeout(() => submitBtn.style.animation = '', 400);
        }
    });
});

// Inject Shake Animation
if (!document.getElementById('auth-shake-anim')) {
    const style = document.createElement('style');
    style.id = 'auth-shake-anim';
    style.textContent = `
        @keyframes shake {
            0%, 100% { transform: translateX(0); }
            20% { transform: translateX(-5px); }
            40% { transform: translateX(5px); }
            60% { transform: translateX(-3px); }
            80% { transform: translateX(3px); }
        }
    `;
    document.head.appendChild(style);
}
