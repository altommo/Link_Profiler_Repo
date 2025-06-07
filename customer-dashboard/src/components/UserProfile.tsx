import React, { useState, useEffect } from 'react';
import { User } from '../types'; // Import User type
import { getUserProfile, updateProfile } from '../services/api'; // Import API service

interface UserProfileProps {
  user: User | null; // User can be null if not logged in yet
}

interface ProfileData {
  username: string;
  email: string;
  organization: string;
  subscriptionTier: string;
  apiCallsRemaining: number;
  crawlCreditsRemaining: number;
}

const UserProfile: React.FC<UserProfileProps> = ({ user }) => {
  const [profileData, setProfileData] = useState<ProfileData>({
    username: '',
    email: '',
    organization: '',
    subscriptionTier: '',
    apiCallsRemaining: 0,
    crawlCreditsRemaining: 0,
  });
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        setLoading(true);
        setError(null);
        
        if (user) {
          const data = await getUserProfile(); // Use the imported API service
          setProfileData({
            username: data.username,
            email: data.email,
            organization: 'Acme Corp', // Placeholder, assuming API doesn't return this
            subscriptionTier: 'Premium', // Placeholder
            apiCallsRemaining: 5000, // Placeholder
            crawlCreditsRemaining: 200, // Placeholder
          });
        }
      } catch (err: any) {
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
    setProfileData(prevData => ({
      ...prevData,
      [name]: value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMessage(null);
    setError(null); // Clear previous errors
    try {
      await updateProfile(profileData); // Use the imported API service
      setMessage('Profile updated successfully!');
      setIsEditing(false);
    } catch (err: any) {
      setError('Failed to update profile. Please try again.');
      console.error('Error updating profile:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="text-center text-nasa-light-gray text-xl mt-20">Loading profile...</div>;
  }

  if (error) {
    return <div className="text-center text-red-500 text-xl mt-20">{error}</div>;
  }

  return (
    <div className="p-6">
      <h2 className="text-3xl font-bold text-nasa-cyan mb-4">Your Profile</h2>
      <p className="text-nasa-light-gray mb-6">Manage your account details and subscription information.</p>

      {message && <div className="bg-green-500 text-white p-3 rounded mb-4">{message}</div>}

      <form onSubmit={handleSubmit} className="bg-nasa-gray p-6 rounded-lg shadow-lg border border-nasa-cyan">
        <div className="mb-4">
          <label htmlFor="username" className="block text-nasa-light-gray text-sm font-bold mb-2">Username:</label>
          {isEditing ? (
            <input
              type="text"
              id="username"
              name="username"
              value={profileData.username}
              onChange={handleChange}
              required
              className="form-input"
            />
          ) : (
            <span className="text-nasa-cyan text-lg">{profileData.username}</span>
          )}
        </div>

        <div className="mb-4">
          <label htmlFor="email" className="block text-nasa-light-gray text-sm font-bold mb-2">Email:</label>
          {isEditing ? (
            <input
              type="email"
              id="email"
              name="email"
              value={profileData.email}
              onChange={handleChange}
              required
              className="form-input"
            />
          ) : (
            <span className="text-nasa-cyan text-lg">{profileData.email}</span>
          )}
        </div>

        <div className="mb-4">
          <label className="block text-nasa-light-gray text-sm font-bold mb-2">Organization:</label>
          <span className="text-nasa-cyan text-lg">{profileData.organization}</span>
        </div>

        <div className="mb-4">
          <label className="block text-nasa-light-gray text-sm font-bold mb-2">Subscription Tier:</label>
          <span className="text-nasa-cyan text-lg">{profileData.subscriptionTier}</span>
        </div>

        <div className="mb-4">
          <label className="block text-nasa-light-gray text-sm font-bold mb-2">API Calls Remaining (Monthly):</label>
          <span className="text-nasa-cyan text-lg">{profileData.apiCallsRemaining}</span>
        </div>

        <div className="mb-4">
          <label className="block text-nasa-light-gray text-sm font-bold mb-2">Crawl Credits Remaining:</label>
          <span className="text-nasa-cyan text-lg">{profileData.crawlCreditsRemaining}</span>
        </div>

        <div className="mt-6 space-x-4">
          {isEditing ? (
            <>
              <button type="submit" className="btn-primary" disabled={loading}>
                {loading ? 'Saving...' : 'Save Changes'}
              </button>
              <button type="button" className="btn-secondary" onClick={() => setIsEditing(false)} disabled={loading}>
                Cancel
              </button>
            </>
          ) : (
            <button type="button" className="btn-primary" onClick={() => setIsEditing(true)}>
              Edit Profile
            </button>
          )}
        </div>
      </form>
    </div>
  );
};

export default UserProfile;
