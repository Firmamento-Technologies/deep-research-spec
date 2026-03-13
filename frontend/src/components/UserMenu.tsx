import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { User, LogOut, Settings, Shield, ChevronDown } from '../lib/icons';

export const UserMenu: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  if (!user) return null;

  // Role badge color
  const roleColors = {
    admin: 'bg-drs-accent/20 text-drs-accent',
    user: 'bg-drs-accent/15 text-drs-accent',
    viewer: 'bg-drs-s3 text-drs-muted',
  };

  return (
    <div className="relative" ref={menuRef}>
      {/* Trigger button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Menu utente"
        aria-expanded={isOpen}
        className="flex items-center space-x-3 px-3 py-2 rounded-lg hover:bg-drs-s2 transition-colors"
      >
        {/* Avatar */}
        <div className="w-8 h-8 rounded-full bg-drs-accent flex items-center justify-center text-white font-medium">
          {user.username.charAt(0).toUpperCase()}
        </div>

        {/* User info */}
        <div className="text-left hidden sm:block">
          <div className="text-sm font-medium text-drs-text">{user.username}</div>
          <div className="text-xs text-drs-faint">{user.email}</div>
        </div>

        <ChevronDown className={`h-4 w-4 text-drs-faint transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown menu */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-64 bg-drs-s2 rounded-lg shadow-lg border border-drs-border py-2 z-50">
          {/* User info (mobile) */}
          <div className="px-4 py-3 border-b border-drs-border sm:hidden">
            <div className="text-sm font-medium text-drs-text">{user.username}</div>
            <div className="text-xs text-drs-faint mt-1">{user.email}</div>
          </div>

          {/* Role badge */}
          <div className="px-4 py-2 border-b border-drs-border">
            <div className="flex items-center justify-between">
              <span className="text-xs text-drs-faint">Role</span>
              <span className={`px-2 py-1 text-xs font-medium rounded-full ${roleColors[user.role]}`}>
                {user.role === 'admin' && <Shield className="inline h-3 w-3 mr-1" />}
                {user.role.charAt(0).toUpperCase() + user.role.slice(1)}
              </span>
            </div>
          </div>

          {/* Menu items */}
          <div className="py-1">
            <button
              onClick={() => {
                navigate('/settings');
                setIsOpen(false);
              }}
              className="w-full flex items-center px-4 py-2 text-sm text-drs-muted hover:bg-drs-s3 hover:text-drs-text"
            >
              <User className="h-4 w-4 mr-3" />
              Profile
            </button>

            <button
              onClick={() => {
                navigate('/settings');
                setIsOpen(false);
              }}
              className="w-full flex items-center px-4 py-2 text-sm text-drs-muted hover:bg-drs-s3 hover:text-drs-text"
            >
              <Settings className="h-4 w-4 mr-3" />
              Settings
            </button>
          </div>

          {/* Logout */}
          <div className="border-t border-drs-border py-1">
            <button
              onClick={handleLogout}
              className="w-full flex items-center px-4 py-2 text-sm text-drs-red hover:bg-drs-red/10"
            >
              <LogOut className="h-4 w-4 mr-3" />
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
