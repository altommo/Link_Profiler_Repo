import React, { useState } from 'react';
import { 
  User, 
  Mail, 
  Key, 
  Bell, 
  Settings, 
  Save,
  Eye,
  EyeOff,
  Shield,
  Globe,
  CreditCard
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const Profile: React.FC = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState('profile');
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // Form states
  const [profileForm, setProfileForm] = useState({
    username: user?.username || '',
    email: user?.email || '',
    firstName: '',
    lastName: '',
    company: '',
    jobTitle: '',
    timezone: 'UTC',
    language: 'en'
  });

  const [passwordForm, setPasswordForm] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  });

  const [notificationSettings, setNotificationSettings] = useState({
    emailNotifications: true,
    jobCompletionEmails: true,
    weeklyReports: true,
    securityAlerts: true,
    marketingEmails: false
  });

  const tabs = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'security', label: 'Security', icon: Shield },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'preferences', label: 'Preferences', icon: Settings }
  ];

  const handleProfileSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log('Profile updated:', profileForm);
    // API call to update profile
  };

  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      alert('New passwords do not match');
      return;
    }
    console.log('Password updated');
    // API call to update password
    setPasswordForm({ currentPassword: '', newPassword: '', confirmPassword: '' });
  };

  const handleNotificationSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log('Notifications updated:', notificationSettings);
    // API call to update notification settings
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-neutral-900">Profile & Settings</h1>
        <p className="text-neutral-600">Manage your account settings and preferences</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar Navigation */}
        <div className="lg:col-span-1">
          <div className="card">
            <div className="card-body p-0">
              <nav className="space-y-1">
                {tabs.map((tab) => {
                  const Icon = tab.icon;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`w-full flex items-center px-4 py-3 text-sm font-medium transition-colors ${
                        activeTab === tab.id
                          ? 'bg-brand-primary text-white'
                          : 'text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900'
                      }`}
                    >
                      <Icon className="mr-3 h-5 w-5" />
                      {tab.label}
                    </button>
                  );
                })}
              </nav>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="lg:col-span-3">
          {/* Profile Tab */}
          {activeTab === 'profile' && (
            <div className="card">
              <div className="card-header">
                <h3 className="text-lg font-semibold text-neutral-900">Profile Information</h3>
              </div>
              <div className="card-body">
                <form onSubmit={handleProfileSubmit} className="space-y-6">
                  <div className="flex items-center space-x-6">
                    <div className="w-20 h-20 bg-brand-primary rounded-full flex items-center justify-center">
                      <User className="h-10 w-10 text-white" />
                    </div>
                    <div>
                      <button className="btn-secondary btn-sm">
                        Change Photo
                      </button>
                      <p className="text-xs text-neutral-500 mt-1">
                        JPG, GIF or PNG. 1MB max.
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label className="form-label">Username</label>
                      <input
                        type="text"
                        className="form-input"
                        value={profileForm.username}
                        onChange={(e) => setProfileForm({ ...profileForm, username: e.target.value })}
                      />
                    </div>
                    <div>
                      <label className="form-label">Email</label>
                      <input
                        type="email"
                        className="form-input"
                        value={profileForm.email}
                        onChange={(e) => setProfileForm({ ...profileForm, email: e.target.value })}
                      />
                    </div>
                    <div>
                      <label className="form-label">First Name</label>
                      <input
                        type="text"
                        className="form-input"
                        value={profileForm.firstName}
                        onChange={(e) => setProfileForm({ ...profileForm, firstName: e.target.value })}
                        placeholder="Enter your first name"
                      />
                    </div>
                    <div>
                      <label className="form-label">Last Name</label>
                      <input
                        type="text"
                        className="form-input"
                        value={profileForm.lastName}
                        onChange={(e) => setProfileForm({ ...profileForm, lastName: e.target.value })}
                        placeholder="Enter your last name"
                      />
                    </div>
                    <div>
                      <label className="form-label">Company</label>
                      <input
                        type="text"
                        className="form-input"
                        value={profileForm.company}
                        onChange={(e) => setProfileForm({ ...profileForm, company: e.target.value })}
                        placeholder="Your company name"
                      />
                    </div>
                    <div>
                      <label className="form-label">Job Title</label>
                      <input
                        type="text"
                        className="form-input"
                        value={profileForm.jobTitle}
                        onChange={(e) => setProfileForm({ ...profileForm, jobTitle: e.target.value })}
                        placeholder="Your job title"
                      />
                    </div>
                  </div>

                  <div className="flex justify-end">
                    <button type="submit" className="btn-primary">
                      <Save className="h-4 w-4 mr-2" />
                      Save Changes
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* Security Tab */}
          {activeTab === 'security' && (
            <div className="space-y-6">
              <div className="card">
                <div className="card-header">
                  <h3 className="text-lg font-semibold text-neutral-900">Change Password</h3>
                </div>
                <div className="card-body">
                  <form onSubmit={handlePasswordSubmit} className="space-y-4">
                    <div>
                      <label className="form-label">Current Password</label>
                      <div className="relative">
                        <input
                          type={showCurrentPassword ? 'text' : 'password'}
                          className="form-input pr-10"
                          value={passwordForm.currentPassword}
                          onChange={(e) => setPasswordForm({ ...passwordForm, currentPassword: e.target.value })}
                          placeholder="Enter current password"
                        />
                        <button
                          type="button"
                          className="absolute inset-y-0 right-0 pr-3 flex items-center"
                          onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                        >
                          {showCurrentPassword ? (
                            <EyeOff className="h-4 w-4 text-neutral-400" />
                          ) : (
                            <Eye className="h-4 w-4 text-neutral-400" />
                          )}
                        </button>
                      </div>
                    </div>
                    
                    <div>
                      <label className="form-label">New Password</label>
                      <div className="relative">
                        <input
                          type={showNewPassword ? 'text' : 'password'}
                          className="form-input pr-10"
                          value={passwordForm.newPassword}
                          onChange={(e) => setPasswordForm({ ...passwordForm, newPassword: e.target.value })}
                          placeholder="Enter new password"
                        />
                        <button
                          type="button"
                          className="absolute inset-y-0 right-0 pr-3 flex items-center"
                          onClick={() => setShowNewPassword(!showNewPassword)}
                        >
                          {showNewPassword ? (
                            <EyeOff className="h-4 w-4 text-neutral-400" />
                          ) : (
                            <Eye className="h-4 w-4 text-neutral-400" />
                          )}
                        </button>
                      </div>
                    </div>
                    
                    <div>
                      <label className="form-label">Confirm New Password</label>
                      <div className="relative">
                        <input
                          type={showConfirmPassword ? 'text' : 'password'}
                          className="form-input pr-10"
                          value={passwordForm.confirmPassword}
                          onChange={(e) => setPasswordForm({ ...passwordForm, confirmPassword: e.target.value })}
                          placeholder="Confirm new password"
                        />
                        <button
                          type="button"
                          className="absolute inset-y-0 right-0 pr-3 flex items-center"
                          onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                        >
                          {showConfirmPassword ? (
                            <EyeOff className="h-4 w-4 text-neutral-400" />
                          ) : (
                            <Eye className="h-4 w-4 text-neutral-400" />
                          )}
                        </button>
                      </div>
                    </div>

                    <div className="flex justify-end">
                      <button type="submit" className="btn-primary">
                        Update Password
                      </button>
                    </div>
                  </form>
                </div>
              </div>

              <div className="card">
                <div className="card-header">
                  <h3 className="text-lg font-semibold text-neutral-900">API Keys</h3>
                </div>
                <div className="card-body">
                  <p className="text-sm text-neutral-600 mb-4">
                    Use API keys to integrate Link Profiler with your applications.
                  </p>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-3 border border-neutral-200 rounded-lg">
                      <div>
                        <div className="font-medium text-sm">Production API Key</div>
                        <div className="text-xs text-neutral-500">lp_prod_••••••••••••••••••••••••••••1234</div>
                      </div>
                      <button className="btn-secondary btn-sm">
                        Regenerate
                      </button>
                    </div>
                  </div>
                  <button className="btn-primary btn-sm mt-4">
                    <Key className="h-4 w-4 mr-2" />
                    Generate New Key
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Notifications Tab */}
          {activeTab === 'notifications' && (
            <div className="card">
              <div className="card-header">
                <h3 className="text-lg font-semibold text-neutral-900">Notification Preferences</h3>
              </div>
              <div className="card-body">
                <form onSubmit={handleNotificationSubmit} className="space-y-6">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium text-sm">Email Notifications</div>
                        <div className="text-xs text-neutral-500">Receive notifications via email</div>
                      </div>
                      <input
                        type="checkbox"
                        className="form-checkbox"
                        checked={notificationSettings.emailNotifications}
                        onChange={(e) => setNotificationSettings({ ...notificationSettings, emailNotifications: e.target.checked })}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium text-sm">Job Completion</div>
                        <div className="text-xs text-neutral-500">Get notified when jobs finish</div>
                      </div>
                      <input
                        type="checkbox"
                        className="form-checkbox"
                        checked={notificationSettings.jobCompletionEmails}
                        onChange={(e) => setNotificationSettings({ ...notificationSettings, jobCompletionEmails: e.target.checked })}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium text-sm">Weekly Reports</div>
                        <div className="text-xs text-neutral-500">Receive weekly performance summaries</div>
                      </div>
                      <input
                        type="checkbox"
                        className="form-checkbox"
                        checked={notificationSettings.weeklyReports}
                        onChange={(e) => setNotificationSettings({ ...notificationSettings, weeklyReports: e.target.checked })}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium text-sm">Security Alerts</div>
                        <div className="text-xs text-neutral-500">Important security notifications</div>
                      </div>
                      <input
                        type="checkbox"
                        className="form-checkbox"
                        checked={notificationSettings.securityAlerts}
                        onChange={(e) => setNotificationSettings({ ...notificationSettings, securityAlerts: e.target.checked })}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium text-sm">Marketing Emails</div>
                        <div className="text-xs text-neutral-500">Product updates and tips</div>
                      </div>
                      <input
                        type="checkbox"
                        className="form-checkbox"
                        checked={notificationSettings.marketingEmails}
                        onChange={(e) => setNotificationSettings({ ...notificationSettings, marketingEmails: e.target.checked })}
                      />
                    </div>
                  </div>

                  <div className="flex justify-end">
                    <button type="submit" className="btn-primary">
                      <Save className="h-4 w-4 mr-2" />
                      Save Preferences
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* Preferences Tab */}
          {activeTab === 'preferences' && (
            <div className="card">
              <div className="card-header">
                <h3 className="text-lg font-semibold text-neutral-900">Application Preferences</h3>
              </div>
              <div className="card-body">
                <form className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label className="form-label">Timezone</label>
                      <select
                        className="form-select"
                        value={profileForm.timezone}
                        onChange={(e) => setProfileForm({ ...profileForm, timezone: e.target.value })}
                      >
                        <option value="UTC">UTC</option>
                        <option value="America/New_York">Eastern Time</option>
                        <option value="America/Chicago">Central Time</option>
                        <option value="America/Denver">Mountain Time</option>
                        <option value="America/Los_Angeles">Pacific Time</option>
                      </select>
                    </div>

                    <div>
                      <label className="form-label">Language</label>
                      <select
                        className="form-select"
                        value={profileForm.language}
                        onChange={(e) => setProfileForm({ ...profileForm, language: e.target.value })}
                      >
                        <option value="en">English</option>
                        <option value="es">Spanish</option>
                        <option value="fr">French</option>
                        <option value="de">German</option>
                      </select>
                    </div>
                  </div>

                  <div className="flex justify-end">
                    <button type="submit" className="btn-primary">
                      <Save className="h-4 w-4 mr-2" />
                      Save Preferences
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Profile;
