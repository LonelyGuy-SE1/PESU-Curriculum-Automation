import { supabase } from '../shared/supabase-client.js';

const form = document.getElementById('login-form');
const emailInput = document.getElementById('email');
const passwordInput = document.getElementById('password');
const submitBtn = document.getElementById('submit-btn');
const errorEl = document.getElementById('auth-error');
const toggleBtn = document.querySelector('.toggle-password');

toggleBtn.addEventListener('click', () => {
  const type = passwordInput.type === 'password' ? 'text' : 'password';
  passwordInput.type = type;
  toggleBtn.classList.toggle('active', type === 'text');
});

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  errorEl.hidden = true;
  errorEl.textContent = '';
  submitBtn.disabled = true;
  submitBtn.textContent = 'Signing in...';

  const email = emailInput.value.trim();
  const password = passwordInput.value;

  const { error } = await supabase.auth.signInWithPassword({ email, password });

  if (error) {
    errorEl.textContent = error.message;
    errorEl.hidden = false;
    submitBtn.disabled = false;
    submitBtn.textContent = 'Sign In';
    return;
  }

  location.href = '/';
});

// Check if already signed in
supabase.auth.getSession().then(({ data: { session } }) => {
  if (session) {
    location.href = '/';
  }
});