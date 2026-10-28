import api from './api';

const authService = {

  signup: async (email, password) => {
    const response = await api.post('/auth/signup', {
      email,
      password
    });
    return response.data;
  },

  login: async (email, password) => {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const response = await api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });

    // ✅ Auto-store token after login
    if (response.data?.access_token) {
      authService.setToken(response.data.access_token);
    }

    return response.data;
  },

  loginJson: async (email, password) => {
    const response = await api.post('/auth/login/json', {
      email,
      password
    });

    // ✅ Auto-store token after login
    if (response.data?.access_token) {
      authService.setToken(response.data.access_token);
    }

    return response.data;
  },

  // ── Email verification (one-time code sent at signup) ────────────────────
  verifyOtp: async (email, otp) => {
    const response = await api.post('/auth/verify-otp', { email, otp });
    return response.data;
  },

  resendOtp: async (email) => {
    const response = await api.post('/auth/resend-otp', { email });
    return response.data;
  },

  logout: () => {
    localStorage.removeItem('token');
  },

  getToken: () => {
    return localStorage.getItem('token');
  },

  setToken: (token) => {
    localStorage.setItem('token', token);
  },

  // ✅ ADDED: Was called in AuthContext but didn't exist
  isLoggedIn: () => {
    return !!localStorage.getItem('token');
  },

  // ✅ ADDED: Was called in AuthContext but didn't exist
  //           Fetches current user from /api/users/me
  getCurrentUser: async () => {
    const response = await api.get('/users/me');
    return response.data;
  },

};

export default authService;