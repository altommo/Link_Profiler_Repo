import React, { useState, useEffect } from 'react';
import { useAuth } from '../hooks/useAuth';

interface ProfileData {
  username: string;
  email: string;
  organization?: string;
  subscriptionTier?: string;
  apiCallsRemaining?: number;
  crawlCreditsRemaining?: number;
}

const UserProfile: React.FC = () => {
  const { user } = useAuth();
  const [profileData, setProfileData] = useState<ProfileData>({
    username: '',
    email: ''
  });
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [message, setMessage] = useState<string>('');

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        setLoading(true);
        setError('');
        
        // Simulate API call with user data
        if (user) {
          setProfileData({
            username: user.username || '',
            email: user.email || '',
            organization: 'Your Organization',
            subscriptionTier: 'Professional',
            apiCallsRemaining: 15000,
            crawlCreditsRemaining: 500
          });
        }
      } catch (err) {
        setError('Failed to fetch profile data. Please try again later.');
        console.error('Error fetching profile:', err);
      } finally {
        setLoading(false);
      }
    };

    if (user) {
      fetchProfile();
    }
  }, [user]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setProfileData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setMessage('');

    try {
      // Simulate API call to update profile
      await new Promise(resolve => setTimeout(resolve, 1000));
      setMessage('Profile updated successfully!');
    } catch (err) {
      setError('Failed to update profile. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (loading && !profileData.username) {
    return (
      <div className="flex items-center justify-center min-h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading profile...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">User Profile</h1>
        <p className="text-gray-600 mt-2">Manage your account settings and preferences</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Account Information */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Account Information</h2>
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-gray-700">
                Username
              </label>
              <input
                type="text"
                id="username"
                name="username"
                value={profileData.username}
                onChange={handleChange}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              />
            </div>

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                Email Address
              </label>
              <input
                type="email"
                id="email"
                name="email"
                value={profileData.email}
                onChange={handleChange}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              />
            </div>

            {message && (
              <div className="text-green-600 text-sm">
                {message}
              </div>
            )}

            {error && (
              <div className="text-red-600 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-md font-medium disabled:opacity-50"
            >
              {loading ? 'Updating...' : 'Update Profile'}
            </button>
          </form>
        </div>

        {/* Account Details */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Account Details</h2>
          
          <div className="space-y-4">
            <div className="flex justify-between">
              <span className="text-gray-600">Organization:</span>
              <span className="font-medium">{profileData.organization || 'Not set'}</span>
            </div>
            
            <div className="flex justify-between">
              <span className="text-gray-600">Subscription:</span>
              <span className="font-medium">{profileData.subscriptionTier || 'Free'}</span>
            </div>
            
            <div className="flex justify-between">
              <span className="text-gray-600">API Calls Remaining:</span>
              <span className="font-medium">{profileData.apiCallsRemaining?.toLocaleString() || '0'}</span>
            </div>
            
            <div className="flex justify-between">
              <span className="text-gray-600">Crawl Credits:</span>
              <span className="font-medium">{profileData.crawlCreditsRemaining || '0'}</span>
            </div>
          </div>

          <div className="mt-6 pt-6 border-t border-gray-200">
            <button className="w-full bg-gray-100 hover:bg-gray-200 text-gray-800 py-2 px-4 rounded-md font-medium">
              Manage Subscription
            </button>
          </div>
        </div>
      </div>

      {/* Usage Analytics */}
      <div className="mt-6 bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Usage Analytics</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-2">API Usage This Month</h3>
            <div className="bg-gray-200 rounded-full h-2">
              <div 
                className="bg-blue-600 h-2 rounded-full" 
                style={{ width: '75%' }}
              ></div>
            </div>
            <p className="text-sm text-gray-600 mt-1">15,000 / 20,000 calls</p>
          </div>
          
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-2">Crawl Credits Used</h3>
            <div className="bg-gray-200 rounded-full h-2">
              <div 
                className="bg-green-600 h-2 rounded-full" 
                style={{ width: '50%' }}
              ></div>
            </div>
            <p className="text-sm text-gray-600 mt-1">500 / 1,000 credits</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UserProfile;