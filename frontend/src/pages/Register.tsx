import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Lock, Mail, User, AlertCircle, CheckCircle } from '../lib/icons';

const inputClass =
  'appearance-none block w-full pl-10 pr-3 py-2 bg-drs-s1 border border-drs-border rounded-md placeholder-drs-faint text-drs-text focus:outline-none focus:ring-drs-accent focus:border-drs-accent sm:text-sm';

const inputClassNoIcon =
  'appearance-none block w-full px-3 py-2 bg-drs-s1 border border-drs-border rounded-md placeholder-drs-faint text-drs-text focus:outline-none focus:ring-drs-accent focus:border-drs-accent sm:text-sm';

export const RegisterPage: React.FC = () => {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    email: '',
    username: '',
    password: '',
    confirmPassword: '',
    full_name: '',
  });
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Form validation
  const isFormValid =
    formData.email.length > 0 &&
    formData.username.length >= 3 &&
    formData.password.length >= 8 &&
    formData.password === formData.confirmPassword;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (formData.password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setIsLoading(true);

    try {
      await register({
        email: formData.email,
        username: formData.username,
        password: formData.password,
        full_name: formData.full_name || undefined,
      });
      navigate('/dashboard');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Registration failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-drs-bg py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        {/* Header */}
        <div className="text-center">
          <h2 className="text-3xl font-extrabold text-drs-text">Create your account</h2>
          <p className="mt-2 text-sm text-drs-muted">Get started with Deep Research System</p>
        </div>

        {/* Form */}
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          {error && (
            <div className="rounded-md bg-drs-red/15 border border-drs-red/30 p-4 flex items-start">
              <AlertCircle className="h-5 w-5 text-drs-red mr-2 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-drs-red">{error}</p>
            </div>
          )}

          <div className="space-y-4">
            {/* Email */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-drs-muted">
                Email address *
              </label>
              <div className="mt-1 relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Mail className="h-5 w-5 text-drs-faint" />
                </div>
                <input
                  id="email"
                  type="email"
                  required
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className={inputClass}
                  placeholder="you@example.com"
                />
              </div>
            </div>

            {/* Username */}
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-drs-muted">
                Username *
              </label>
              <div className="mt-1 relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <User className="h-5 w-5 text-drs-faint" />
                </div>
                <input
                  id="username"
                  type="text"
                  required
                  minLength={3}
                  maxLength={50}
                  value={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                  className={inputClass}
                  placeholder="johndoe"
                />
              </div>
            </div>

            {/* Full Name */}
            <div>
              <label htmlFor="full_name" className="block text-sm font-medium text-drs-muted">
                Full Name (optional)
              </label>
              <input
                id="full_name"
                type="text"
                value={formData.full_name}
                onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                className={`mt-1 ${inputClassNoIcon}`}
                placeholder="John Doe"
              />
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-drs-muted">
                Password *
              </label>
              <div className="mt-1 relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5 text-drs-faint" />
                </div>
                <input
                  id="password"
                  type="password"
                  required
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className={inputClass}
                  placeholder="••••••••"
                />
              </div>
            </div>

            {/* Confirm Password */}
            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-drs-muted">
                Confirm Password *
              </label>
              <div className="mt-1 relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5 text-drs-faint" />
                </div>
                <input
                  id="confirmPassword"
                  type="password"
                  required
                  value={formData.confirmPassword}
                  onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                  className={inputClass}
                  placeholder="••••••••"
                />
              </div>
            </div>

            {/* Password requirements */}
            {formData.password && (
              <div className="text-sm space-y-1">
                <div className={`flex items-center ${formData.password.length >= 8 ? 'text-drs-green' : 'text-drs-faint'}`}>
                  <CheckCircle className="h-4 w-4 mr-2" />
                  At least 8 characters
                </div>
                {formData.confirmPassword && (
                  <div className={`flex items-center ${formData.password === formData.confirmPassword ? 'text-drs-green' : 'text-drs-red'}`}>
                    {formData.password === formData.confirmPassword ? (
                      <CheckCircle className="h-4 w-4 mr-2" />
                    ) : (
                      <AlertCircle className="h-4 w-4 mr-2" />
                    )}
                    Passwords match
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={isLoading || !isFormValid}
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-drs-accent hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-drs-accent disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? 'Creating account...' : 'Create account'}
          </button>

          {/* Login link */}
          <p className="text-center text-sm text-drs-muted">
            Already have an account?{' '}
            <Link to="/login" className="font-medium text-drs-accent hover:brightness-110">
              Sign in here
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
};
